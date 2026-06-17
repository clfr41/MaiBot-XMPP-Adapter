"""XMPP 运行时组件容器。"""

from __future__ import annotations

from dataclasses import dataclass

from ..codecs.inbound import XmppInboundCodec
from ..codecs.notice import XmppNoticeCodec
from ..codecs.outbound import XmppOutboundCodec
from ..filters import XmppChatFilter, XmppRegexFilter
from ..heartbeat_monitor import XmppHeartbeatMonitor
from ..runtime_state import XmppRuntimeStateManager
from ..services import XmppActionService, XmppQueryService
from ..transport import XmppTransportClient


@dataclass
class XmppRuntimeBundle:
    """XMPP 运行时依赖集合。"""

    action_service: XmppActionService
    chat_filter: XmppChatFilter
    heartbeat_monitor: XmppHeartbeatMonitor
    inbound_codec: XmppInboundCodec
    notice_codec: XmppNoticeCodec
    outbound_codec: XmppOutboundCodec
    query_service: XmppQueryService
    regex_filter: XmppRegexFilter
    runtime_state: XmppRuntimeStateManager
    transport: XmppTransportClient
