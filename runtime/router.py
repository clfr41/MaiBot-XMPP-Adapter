"""XMPP 事件路由协调器。"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Protocol

from ..config import XmppPluginSettings
from ..types import XmppPayloadDict
from .bundle import XmppRuntimeBundle


class _GatewayCapabilityProtocol(Protocol):
    """插件网关能力协议。"""

    async def route_message(
        self,
        gateway_name: str,
        message: Dict[str, Any],
        *,
        route_metadata: Optional[Dict[str, Any]] = None,
        external_message_id: str = "",
        dedupe_key: str = "",
    ) -> bool:
        """向 Host 注入一条消息。"""
        ...


class XmppEventRouter:
    """协调 XMPP 运行时组件处理各类平台事件。"""

    def __init__(
        self,
        gateway_capability: _GatewayCapabilityProtocol,
        logger: Any,
        gateway_name: str,
        load_settings: Callable[[], XmppPluginSettings],
    ) -> None:
        """初始化事件路由器。

        Args:
            gateway_capability: SDK 提供的消息网关能力对象。
            logger: 插件日志对象。
            gateway_name: 当前消息网关名称。
            load_settings: 返回当前生效插件配置的回调。
        """
        self._gateway_capability = gateway_capability
        self._logger = logger
        self._gateway_name = gateway_name
        self._load_settings = load_settings
        self._runtime: Optional[XmppRuntimeBundle] = None

    def bind_runtime(self, runtime: XmppRuntimeBundle) -> None:
        """绑定当前路由器使用的运行时依赖。

        Args:
            runtime: 已初始化的运行时组件集合。
        """
        self._runtime = runtime

    def reset_caches(self) -> None:
        """重置与路由相关的短期缓存。"""
        pass

    async def handle_transport_payload(self, payload: XmppPayloadDict) -> None:
        """处理来自传输层的消息载荷。"""
        runtime = self._require_runtime()

        msg_type = str(payload.get("type") or "").strip().lower()
        from_jid = str(payload.get("from_jid") or "").strip()
        to_jid = str(payload.get("to_jid") or "").strip()

        self._logger.debug(
            f"路由收到载荷: type={msg_type} from={from_jid} to={to_jid}"
        )

        if msg_type in ("groupchat", "chat"):
            is_group = (msg_type == "groupchat")
            self._logger.debug(
                f"路由处理入站消息: {'群聊' if is_group else '私聊'} "
                f"from={from_jid}"
            )
            await self.handle_inbound_message(payload, is_group=is_group)
        else:
            self._logger.debug(
                f"XMPP 忽略非消息 stanza: type={msg_type} from={from_jid} to={to_jid}"
            )

    async def handle_inbound_message(self, payload: XmppPayloadDict, is_group: bool) -> None:
        """处理单条 XMPP 入站消息并注入 Host。

        Args:
            payload: XMPP 原始消息事件。
            is_group: 是否为群聊消息。
        """
        runtime = self._require_runtime()
        settings = self._load_settings()
        self_id = runtime.transport.bare_jid

        # 提取 MUC 昵称用于自身消息检测
        muc_nickname = (
            settings.xmpp_server.muc_nickname.strip()
            or (settings.xmpp_server.jid.split("@")[0] if "@" in settings.xmpp_server.jid else "")
        )

        # 过滤管道（步骤 1-5: 验证 JID/body、解析、自身消息、聊天名单）
        ctx = runtime.filter_pipeline.run(
            payload, is_group, self_id, settings.filters, settings.chat, muc_nickname
        )
        if ctx is None:
            return

        # 构建标准消息字典（步骤 6）
        try:
            message_dict = await runtime.inbound_codec.build_message_dict(
                payload, ctx.self_id, ctx.sender_jid, ctx.is_group, ctx.group_jid
            )
        except ValueError as exc:
            self._logger.warning(f"XMPP 入站消息格式不受支持，已丢弃: {exc}")
            return

        # 正则过滤（步骤 7）
        plain_text = str(message_dict.get("processed_plain_text") or "").strip()
        if not runtime.filter_pipeline.is_regex_allowed(plain_text, ctx.sender_jid, settings.filters):
            return

        # 注入 Host（步骤 8）
        route_metadata = self._build_route_metadata(ctx.self_id, settings.xmpp_server.connection_id)
        external_message_id = str(payload.get("id") or "").strip()
        self._logger.debug(
            f"入站消息注入 Host: from={ctx.sender_jid} "
            f"group={ctx.group_jid or '(私聊)'} "
            f"msg_id={external_message_id or '(新生成)'}"
        )
        accepted = await self._gateway_capability.route_message(
            gateway_name=self._gateway_name,
            message=message_dict,
            route_metadata=route_metadata,
            external_message_id=external_message_id,
            dedupe_key=external_message_id,
        )
        if not accepted:
            self._logger.debug(f"Host 丢弃了 XMPP 入站消息: {external_message_id or '无消息 ID'}")
        else:
            self._logger.debug(f"XMPP 入站消息成功注入 Host: {external_message_id or '无消息 ID'}")

    async def bootstrap_adapter_runtime_state(self) -> None:
        """在连接建立后激活消息网关路由。"""
        runtime = self._require_runtime()
        settings = self._load_settings()
        logger = self._logger

        self_id = runtime.transport.bare_jid
        if not self_id:
            logger.warning("XMPP 消息网关缺少 bare JID，无法激活路由")
            return

        logger.debug(f"正在激活消息网关路由: self_id={self_id}")

        # 尝试注册机器人账号到 Host，若失败则输出错误并尝试备用 ID
        accepted = await runtime.runtime_state.report_connected(self_id, settings.xmpp_server)
        if not accepted:
            # 使用 connection_id 作为备用 account_id 再试一次
            fallback_id = settings.xmpp_server.connection_id or self_id.split("@")[0]
            logger.warning(
                f"Host 拒绝了 account_id={self_id} 的注册，尝试备用 ID={fallback_id}"
            )
            accepted = await runtime.runtime_state.report_connected(fallback_id, settings.xmpp_server)
            if accepted:
                logger.info(f"使用备用 ID 注册成功: {fallback_id}")
                self_id = fallback_id  # 更新为注册成功的 ID
            else:
                logger.warning(f"备用 ID 注册也失败: {fallback_id}")
        if not accepted:
            logger.error(
                "XMPP 消息网关路由激活失败：Host 未接受机器人账号注册。"
                "请检查发送功能是否正常，若无法发送消息，可能需要在 Host 端预先配置机器人账号"
            )
            return

        logger.info(f"XMPP 消息网关路由已激活: {self_id}")

    async def handle_transport_disconnected(self) -> None:
        """处理传输层断开事件。"""
        logger = self._logger
        logger.debug("传输层断开事件处理开始")
        runtime = self._require_runtime()
        self.reset_caches()
        await runtime.runtime_state.report_disconnected()
        logger.debug("传输层断开事件处理完成")

    def _require_runtime(self) -> XmppRuntimeBundle:
        """返回当前已绑定的运行时依赖。"""
        runtime = self._runtime
        if runtime is None:
            raise RuntimeError("XMPP 运行时尚未初始化")
        return runtime

    @staticmethod
    def _build_route_metadata(self_id: str, connection_id: str) -> Dict[str, Any]:
        """构造注入 Host 时使用的路由元数据。"""
        route_metadata: Dict[str, Any] = {}
        if self_id:
            route_metadata["self_id"] = self_id
        if connection_id:
            route_metadata["connection_id"] = connection_id
        return route_metadata