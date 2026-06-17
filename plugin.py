"""内置 XMPP 适配器插件。

当前实现承担完整的 XMPP 消息网关职责：
1. 作为客户端连接 XMPP 服务器（基于 slixmpp）。
2. 将入站消息与通知事件转换为 Host 侧结构。
3. 将 Host 出站消息转换为 XMPP stanza 并发送。
4. 通过公开 API 暴露 XMPP 平台专属查询与管理动作。
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict, Optional, cast

from maibot_sdk import MaiBotPlugin, MessageGateway, PluginConfigBase

from .apis import (
    XmppAccountApiMixin,
    XmppMessageApiMixin,
    XmppSystemApiMixin,
)
from .config import XmppPluginSettings
from .constants import XMPP_GATEWAY_NAME
from .runtime import XmppEventRouter, XmppRuntimeBuilder, XmppRuntimeBundle
from .services import XmppActionService, XmppQueryService


class XmppAdapterPlugin(
    XmppAccountApiMixin,
    XmppMessageApiMixin,
    XmppSystemApiMixin,
    MaiBotPlugin,
):
    """XMPP 消息网关插件。"""

    config_model: ClassVar[type[PluginConfigBase] | None] = XmppPluginSettings

    def __init__(self) -> None:
        super().__init__()
        self._action_service: Optional[XmppActionService] = None
        self._query_service: Optional[XmppQueryService] = None
        self._event_router: Optional[XmppEventRouter] = None
        self._runtime_bundle: Optional[XmppRuntimeBundle] = None

    async def on_load(self) -> None:
        # 开启 slixmpp 详细日志，便于排查连接故障
        logging.getLogger("slixmpp").setLevel(logging.DEBUG)
        await self._restart_connection_if_needed()

    async def on_unload(self) -> None:
        await self._stop_connection()

    async def on_config_update(self, scope: str, config_data: Dict[str, Any], version: str) -> None:
        if scope != "self":
            return

        self.set_plugin_config(config_data)
        if version:
            self.ctx.logger.debug(f"XMPP 适配器收到配置更新通知: {version}")
        await self._restart_connection_if_needed()

    @MessageGateway(
        name=XMPP_GATEWAY_NAME,
        route_type="duplex",
        platform="xmpp",
        protocol="xmpp",
        description="XMPP 双工消息网关",
    )
    async def handle_xmpp_gateway(
        self,
        message: Dict[str, Any],
        route: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        del metadata
        del kwargs

        runtime_bundle = self._require_runtime_bundle()
        try:
            action_name, params = runtime_bundle.outbound_codec.build_outbound_action(message, route or {})
            response = await self._dispatch_outbound_action(runtime_bundle, action_name, params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        if not response.get("success", False):
            return {
                "success": False,
                "error": str(response.get("error") or "XMPP send failed"),
            }

        return {
            "success": True,
            "external_message_id": response.get("external_message_id"),
            "metadata": {
                "action": action_name,
                "adapter_callbacks": [],
            },
        }

    async def _dispatch_outbound_action(
        self,
        runtime_bundle: XmppRuntimeBundle,
        action_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        transport = runtime_bundle.transport
        to_jid = str(params.get("to_jid") or "").strip()
        body = str(params.get("body") or "")
        message_type = str(params.get("message_type") or "chat").strip()

        if action_name in ("send_group_message", "send_private_message"):
            return await transport.send_message(to_jid, body, message_type)

        if action_name == "send_presence":
            status = str(params.get("status") or "")
            show = str(params.get("show") or "")
            return await transport.send_presence(status, show)

        if action_name == "join_muc":
            nickname = str(params.get("nickname") or "")
            return await transport.join_muc(to_jid, nickname)

        raise ValueError(f"未知的 XMPP 出站动作: {action_name}")

    def _ensure_runtime_components(self) -> None:
        if self._event_router is None:
            self._event_router = XmppEventRouter(
                gateway_capability=self.ctx.gateway,
                logger=self.ctx.logger,
                gateway_name=XMPP_GATEWAY_NAME,
                load_settings=self._load_settings,
            )

        if self._runtime_bundle is None:
            runtime_builder = XmppRuntimeBuilder(
                gateway_capability=self.ctx.gateway,
                logger=self.ctx.logger,
                gateway_name=XMPP_GATEWAY_NAME,
            )
            self._runtime_bundle = runtime_builder.build(
                on_connection_opened=self._event_router.bootstrap_adapter_runtime_state,
                on_connection_closed=self._event_router.handle_transport_disconnected,
                on_payload=self._event_router.handle_transport_payload,
                on_heartbeat_timeout=self._event_router.handle_heartbeat_timeout,
            )
            self._event_router.bind_runtime(self._runtime_bundle)
            self._bind_runtime_aliases(self._runtime_bundle)

    def _bind_runtime_aliases(self, runtime_bundle: XmppRuntimeBundle) -> None:
        self._action_service = runtime_bundle.action_service
        self._query_service = runtime_bundle.query_service

    def _load_settings(self) -> XmppPluginSettings:
        return cast(XmppPluginSettings, self.config)

    async def _restart_connection_if_needed(self) -> None:
        self._ensure_runtime_components()
        runtime_bundle = self._require_runtime_bundle()
        settings = self._load_settings()

        await self._stop_connection()
        if not settings.should_connect():
            self.ctx.logger.info("XMPP 适配器保持空闲状态，因为插件或配置未启用")
            return
        if not settings.validate_runtime_config(self.ctx.logger):
            return
        if not runtime_bundle.transport.is_available():
            self.ctx.logger.error("XMPP 适配器依赖 slixmpp，但当前环境未安装该依赖")
            return

        if not settings.chat.enable_chat_list_filter:
            self.ctx.logger.info(
                "XMPP 聊天名单过滤已关闭：将忽略 group_list 与 private_list，仅保留 ban_user_id"
            )

        runtime_bundle.regex_filter.reload_patterns(settings.filters.regex_filter_patterns)
        if settings.filters.regex_filter_enabled and settings.filters.regex_filter_patterns:
            self.ctx.logger.info(
                f"XMPP 正则消息过滤已启用: 模式={settings.filters.regex_filter_mode}，"
                f"规则数={len(settings.filters.regex_filter_patterns)}"
            )

        runtime_bundle.transport.configure(settings.xmpp_server)
        await runtime_bundle.transport.start()

    async def _stop_connection(self) -> None:
        runtime_bundle = self._runtime_bundle
        if runtime_bundle is None:
            return

        await runtime_bundle.transport.stop()
        if self._event_router is not None:
            self._event_router.reset_caches()

    def _require_runtime_bundle(self) -> XmppRuntimeBundle:
        self._ensure_runtime_components()
        runtime_bundle = self._runtime_bundle
        if runtime_bundle is None:
            raise RuntimeError("XMPP 运行时尚未初始化")
        return runtime_bundle


def create_plugin() -> XmppAdapterPlugin:
    return XmppAdapterPlugin()