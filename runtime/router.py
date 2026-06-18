"""XMPP 事件路由协调器。"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Protocol

import asyncio

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
        runtime.heartbeat_monitor.touch()

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
        from_jid = str(payload.get("from_jid") or "").strip()
        if not from_jid:
            self._logger.debug("入站消息缺少 from_jid，已跳过")
            return

        # 防御性过滤：无 body 的空消息（如 typing indicator / chat state notification）
        body = str(payload.get("body") or "").strip()
        if not body:
            self._logger.debug(
                f"入站消息 body 为空，已跳过: type={payload.get('type')} from={from_jid}"
            )
            return

        # 解析发送者 bare JID 和群 JID
        if is_group:
            # MUC 消息: from="room@conference.example.com/nick"
            sender_jid = self._extract_muc_sender(from_jid)
            group_jid = self._extract_bare_jid(from_jid)
            self._logger.debug(
                f"MUC 消息解析: full={from_jid} -> sender={sender_jid} group={group_jid}"
            )
        else:
            sender_jid = self._extract_bare_jid(from_jid)
            group_jid = ""

        if self_id and sender_jid == self_id and settings.filters.ignore_self_message:
            self._logger.debug(f"忽略自身消息: sender={sender_jid} == self={self_id}")
            return

        if not runtime.chat_filter.is_inbound_chat_allowed(sender_jid, group_jid, settings.chat):
            self._logger.debug(
                f"聊天名单过滤拦截消息: sender={sender_jid} group={group_jid or '(私聊)'}"
            )
            return

        try:
            message_dict = await runtime.inbound_codec.build_message_dict(
                payload, self_id, sender_jid, is_group, group_jid
            )
        except ValueError as exc:
            self._logger.warning(f"XMPP 入站消息格式不受支持，已丢弃: {exc}")
            return

        plain_text = str(message_dict.get("processed_plain_text") or "").strip()
        if not runtime.regex_filter.is_message_allowed(plain_text, settings.filters):
            self._logger.debug(
                f"正则过滤拦截消息: sender={sender_jid} "
                f"text_len={len(plain_text)} text={plain_text[:50]!r}"
            )
            return

        route_metadata = self._build_route_metadata(self_id, settings.xmpp_server.connection_id)
        external_message_id = str(payload.get("id") or "").strip()
        self._logger.debug(
            f"入站消息注入 Host: from={sender_jid} "
            f"group={group_jid or '(私聊)'} "
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

        logger.debug("XMPP 消息网关路由注册成功，启用心跳监控")
        await runtime.heartbeat_monitor.start(self_id, settings.xmpp_server.heartbeat_interval)
        # 立即刷新心跳时间戳，避免刚启动就触发超时
        runtime.heartbeat_monitor.touch()
        logger.info(f"XMPP 消息网关路由已激活: {self_id}")

    async def handle_transport_disconnected(self) -> None:
        """处理传输层断开事件。"""
        logger = self._logger
        logger.debug("传输层断开事件处理开始")
        runtime = self._require_runtime()
        await runtime.heartbeat_monitor.stop()
        self.reset_caches()
        await runtime.runtime_state.report_disconnected()
        logger.debug("传输层断开事件处理完成")

    async def handle_heartbeat_timeout(self, self_id: str) -> None:
        """处理 XMPP 心跳长时间未更新的情况。

        Args:
            self_id: 当前机器人 JID。
        """
        runtime = self._require_runtime()
        if self_id:
            self._logger.warning(f"XMPP Bot {self_id} 心跳超时，暂时将消息网关标记为未就绪")
        else:
            self._logger.warning("XMPP 心跳超时，暂时将消息网关标记为未就绪")
        await runtime.runtime_state.report_disconnected()

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

    @staticmethod
    def _extract_bare_jid(full_jid: str) -> str:
        """从 full JID 提取 bare JID。

        Args:
            full_jid: 完整 JID (可能含 resource)。

        Returns:
            str: bare JID。
        """
        return full_jid.split("/")[0] if "/" in full_jid else full_jid

    @staticmethod
    def _extract_muc_sender(muc_from: str) -> str:
        """从 MUC 消息的 from 字段中提取发送者的 bare JID。

        MUC 消息的 from 格式为: room@conference.example.com/nickname
        但 XMPP 会在消息体内通过 occupant_id 或类似字段标识真实 JID。
        这里做 best-effort 提取。

        Args:
            muc_from: MUC 消息的 from 字段。

        Returns:
            str: 发送者标识。
        """
        if "/" in muc_from:
            return muc_from.split("/", 1)[1]
        return muc_from