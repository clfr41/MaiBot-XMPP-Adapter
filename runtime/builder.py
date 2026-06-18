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
        logger = self._logger
        logger.debug("XmppRuntimeBuilder.build() 开始构建运行时")

        chat_filter = XmppChatFilter(logger)
        regex_filter = XmppRegexFilter(logger)
        transport = XmppTransportClient(
            logger=logger,
            on_connection_opened=on_connection_opened,
            on_connection_closed=on_connection_closed,
            on_payload=on_payload,
        )
        logger.debug("传输层组件已创建")

        action_service = XmppActionService(logger, transport)
        query_service = XmppQueryService(action_service, logger)
        inbound_codec = XmppInboundCodec(logger, query_service)
        notice_codec = XmppNoticeCodec(logger)
        logger.debug("服务层/编解码组件已创建")

        runtime_state = XmppRuntimeStateManager(
            gateway_capability=self._gateway_capability,
            logger=logger,
            gateway_name=self._gateway_name,
        )
        heartbeat_monitor = XmppHeartbeatMonitor(
            logger=logger,
            on_timeout=on_heartbeat_timeout,
        )
        outbound_codec = XmppOutboundCodec()
        logger.debug("状态管理/心跳组件已创建")

        bundle = XmppRuntimeBundle(
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
        logger.debug("XmppRuntimeBuilder.build() 完成: 运行时组件已组装")
        return bundle
