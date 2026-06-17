"""XMPP 运行时组件构建器。"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Coroutine

from ..codecs.inbound import XmppInboundCodec
from ..codecs.notice import XmppNoticeCodec
from ..codecs.outbound import XmppOutboundCodec
from ..filters import XmppChatFilter, XmppRegexFilter
from ..heartbeat_monitor import XmppHeartbeatMonitor
from ..runtime_state import XmppRuntimeStateManager
from ..services import XmppActionService, XmppQueryService
from ..transport import XmppTransportClient
from .bundle import XmppRuntimeBundle


class XmppRuntimeBuilder:
    """按固定依赖图构建 XMPP 运行时组件。"""

    def __init__(self, gateway_capability: Any, logger: Any, gateway_name: str) -> None:
        """初始化运行时构建器。

        Args:
            gateway_capability: SDK 提供的消息网关能力对象。
            logger: 插件日志对象。
            gateway_name: 当前消息网关名称。
        """
        self._gateway_capability = gateway_capability
        self._logger = logger
        self._gateway_name = gateway_name

    def build(
        self,
        on_connection_opened: Callable[[], Coroutine[Any, Any, None]],
        on_connection_closed: Callable[[], Coroutine[Any, Any, None]],
        on_payload: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
        on_heartbeat_timeout: Callable[[str], Awaitable[None]],
    ) -> XmppRuntimeBundle:
        """创建一套完整的运行时组件。

        Args:
            on_connection_opened: 连接建立回调。
            on_connection_closed: 连接断开回调。
            on_payload: 非 echo 载荷回调。
            on_heartbeat_timeout: 心跳超时回调。

        Returns:
            XmppRuntimeBundle: 已完成依赖注入的运行时组件集合。
        """
        chat_filter = XmppChatFilter(self._logger)
        regex_filter = XmppRegexFilter(self._logger)
        transport = XmppTransportClient(
            logger=self._logger,
            on_connection_opened=on_connection_opened,
            on_connection_closed=on_connection_closed,
            on_payload=on_payload,
        )
        action_service = XmppActionService(self._logger, transport)
        query_service = XmppQueryService(action_service, self._logger)
        inbound_codec = XmppInboundCodec(self._logger, query_service)
        notice_codec = XmppNoticeCodec(self._logger)
        runtime_state = XmppRuntimeStateManager(
            gateway_capability=self._gateway_capability,
            logger=self._logger,
            gateway_name=self._gateway_name,
        )
        heartbeat_monitor = XmppHeartbeatMonitor(
            logger=self._logger,
            on_timeout=on_heartbeat_timeout,
        )
        outbound_codec = XmppOutboundCodec()

        return XmppRuntimeBundle(
            action_service=action_service,
            chat_filter=chat_filter,
            heartbeat_monitor=heartbeat_monitor,
            inbound_codec=inbound_codec,
            notice_codec=notice_codec,
            outbound_codec=outbound_codec,
            query_service=query_service,
            regex_filter=regex_filter,
            runtime_state=runtime_state,
            transport=transport,
        )
