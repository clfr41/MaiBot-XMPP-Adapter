"""XMPP 运行时组件容器。"""

from __future__ import annotations

from dataclasses import dataclass

from ..codecs.inbound import XmppInboundCodec
from ..codecs.notice import XmppNoticeCodec
from ..codecs.outbound import XmppOutboundCodec
from ..filters import XmppChatFilter, XmppRegexFilter
from ..runtime_state import XmppRuntimeStateManager
from ..services import XmppActionService
from ..transport import XmppTransportClient
from .filter_pipeline import XmppInboundFilterPipeline


@dataclass
class XmppRuntimeBundle:
    """XMPP 运行时依赖集合。"""

    action_service: XmppActionService
    chat_filter: XmppChatFilter
    filter_pipeline: XmppInboundFilterPipeline
    inbound_codec: XmppInboundCodec
    notice_codec: XmppNoticeCodec
    outbound_codec: XmppOutboundCodec
    regex_filter: XmppRegexFilter
    runtime_state: XmppRuntimeStateManager
    transport: XmppTransportClient
