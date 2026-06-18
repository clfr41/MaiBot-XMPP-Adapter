"""内置 XMPP 适配器插件。

当前实现承担完整的 XMPP 消息网关职责：
1. 作为客户端连接 XMPP 服务器（基于 slixmpp）。
2. 将入站消息与通知事件转换为 Host 侧结构。
3. 将 Host 出站消息转换为 XMPP stanza 并发送。
4. 通过公开 API 暴露 XMPP 平台专属查询与管理动作。
"""

from __future__ import annotations

import asyncio
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
from .services import XmppActionService


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
        self._event_router: Optional[XmppEventRouter] = None
        self._runtime_bundle: Optional[XmppRuntimeBundle] = None

    async def on_load(self) -> None:
        """插件加载时初始化连接。"""
        self.ctx.logger.debug("XMPP 适配器 on_load 触发")
        # 根据配置设置 slixmpp 日志级别，DEBUG 会输出完整 stanza 内容
        settings = self._load_settings()
        level_name = settings.plugin.slixmpp_log_level
        log_level = getattr(logging, level_name.upper(), logging.WARNING)
        logging.getLogger("slixmpp").setLevel(log_level)
        self.ctx.logger.debug(f"slixmpp 日志级别已设为: {level_name}")
        await self._restart_connection_if_needed()
        self.ctx.logger.debug("XMPP 适配器 on_load 完成")

    async def on_unload(self) -> None:
        """插件卸载时清理连接。"""
        self.ctx.logger.debug("XMPP 适配器 on_unload 触发")
        await self._stop_connection()
        self.ctx.logger.debug("XMPP 适配器 on_unload 完成")

    async def on_config_update(self, scope: str, config_data: Dict[str, Any], version: str) -> None:
        """配置更新时重连。"""
        if scope != "self":
            self.ctx.logger.debug(f"XMPP 适配器忽略非自身配置更新: scope={scope}")
            return

        self.ctx.logger.debug(f"XMPP 适配器收到自身配置更新通知: version={version}")
        self.set_plugin_config(config_data)
        if version:
            self.ctx.logger.debug(f"XMPP 适配器配置版本标识: {version}")
        await self._restart_connection_if_needed()
        self.ctx.logger.debug("XMPP 适配器配置更新处理完成")

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
        action_name = "unknown"

        try:
            action_name, params = runtime_bundle.outbound_codec.build_outbound_action(
                message, route or {}
            )
            self.ctx.logger.debug(
                f"网关出站动作: action={action_name} "
                f"params_to={params.get('to_jid', '')[:64]}"
            )
            response = await self._dispatch_outbound_action(
                action_name, params
            )
        except ValueError as exc:
            # 参数解析/校验错误，属于预期内的业务异常
            self.ctx.logger.warning(f"XMPP 出站动作参数错误: {exc}")
            return {"success": False, "error": str(exc)}
        except RuntimeError as exc:
            # 连接未就绪等运行时状态错误
            self.ctx.logger.warning(f"XMPP 出站动作运行时错误: {exc}")
            return {"success": False, "error": str(exc)}
        except asyncio.CancelledError:
            # 任务取消 — 让上层传播，不吞没
            raise
        except Exception as exc:
            # 未知异常兜底，记录完整堆栈
            self.ctx.logger.exception(f"XMPP 出站动作未知异常 (action={action_name}): {exc}")
            return {"success": False, "error": f"XMPP 内部错误: {exc}"}

        if not response.get("success", False):
            error_detail = str(response.get("error") or "XMPP send failed")
            self.ctx.logger.warning(
                f"XMPP 出站动作执行失败 (action={action_name}): {error_detail}"
            )
            return {
                "success": False,
                "error": error_detail,
            }

        ext_msg_id = response.get("external_message_id")
        self.ctx.logger.debug(
            f"XMPP 出站动作成功: action={action_name} "
            f"external_message_id={ext_msg_id}"
        )
        return {
            "success": True,
            "external_message_id": ext_msg_id,
            "metadata": {
                "action": action_name,
                "adapter_callbacks": [],
            },
        }

    async def _dispatch_outbound_action(
        self,
        action_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        action_service = self._require_action_service()
        to_jid = str(params.get("to_jid") or "").strip()
        body = str(params.get("body") or "")
        message_type = str(params.get("message_type") or "chat").strip()

        self.ctx.logger.debug(
            f"分发出站动作: action={action_name} to={to_jid} "
            f"type={message_type} body_len={len(body)}"
        )

        if action_name in ("send_group_message", "send_private_message"):
            return await action_service.send_message(to_jid, body, message_type)

        if action_name == "send_presence":
            status = str(params.get("status") or "")
            show = str(params.get("show") or "")
            return await action_service.send_presence(status, show)

        if action_name == "join_muc":
            nickname = str(params.get("nickname") or "")
            return await action_service.join_muc(to_jid, nickname)

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
            )
            self._event_router.bind_runtime(self._runtime_bundle)
            self._bind_runtime_aliases(self._runtime_bundle)

    def _bind_runtime_aliases(self, runtime_bundle: XmppRuntimeBundle) -> None:
        self._action_service = runtime_bundle.action_service

    def _load_settings(self) -> XmppPluginSettings:
        return cast(XmppPluginSettings, self.config)

    async def _restart_connection_if_needed(self) -> None:
        """检查配置并重启 XMPP 连接。"""
        self.ctx.logger.debug("_restart_connection_if_needed 开始")
        self._ensure_runtime_components()
        runtime_bundle = self._require_runtime_bundle()
        settings = self._load_settings()

        await self._stop_connection()
        if not settings.should_connect():
            self.ctx.logger.info("XMPP 适配器保持空闲状态，因为插件或配置未启用")
            return
        if not settings.validate_runtime_config(self.ctx.logger):
            self.ctx.logger.warning("XMPP 适配器运行时配置校验失败，跳过连接")
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
        elif settings.filters.regex_filter_enabled:
            self.ctx.logger.debug("XMPP 正则过滤已启用但规则列表为空")

        self.ctx.logger.debug(
            f"配置传输层: host={settings.xmpp_server.host}:{settings.xmpp_server.port} "
            f"jid={settings.xmpp_server.jid}"
        )
        runtime_bundle.transport.configure(settings.xmpp_server)
        await runtime_bundle.transport.start()
        self.ctx.logger.debug("_restart_connection_if_needed 完成")

    async def _stop_connection(self) -> None:
        """停止当前 XMPP 连接。"""
        self.ctx.logger.debug("_stop_connection 开始")
        runtime_bundle = self._runtime_bundle
        if runtime_bundle is None:
            self.ctx.logger.debug("runtime_bundle 为空，跳过停止连接")
            return

        await runtime_bundle.transport.stop()
        if self._event_router is not None:
            self._event_router.reset_caches()
        self.ctx.logger.debug("_stop_connection 完成")

    def _require_runtime_bundle(self) -> XmppRuntimeBundle:
        self._ensure_runtime_components()
        runtime_bundle = self._runtime_bundle
        if runtime_bundle is None:
            raise RuntimeError("XMPP 运行时尚未初始化")
        return runtime_bundle


def create_plugin() -> XmppAdapterPlugin:
    return XmppAdapterPlugin()