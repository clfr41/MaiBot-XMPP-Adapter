"""XMPP 适配器内部共享类型。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Optional, TypeAlias

from typing_extensions import NotRequired, TypedDict


class XmppIncomingSegment(TypedDict):
    """XMPP 入站消息段结构。"""

    type: str
    data: Mapping[str, Any]


class XmppHostMessageSegment(TypedDict):
    """适配器转换后写入 Host 的消息段结构。"""

    type: str
    data: Any
    hash: NotRequired[str]
    binary_data_base64: NotRequired[str]


XmppActionParams: TypeAlias = Mapping[str, Any]
XmppActionParamsInput: TypeAlias = Optional[Mapping[str, Any]]
XmppActionResponse: TypeAlias = Dict[str, Any]
XmppIdInput: TypeAlias = int | str
XmppMutablePayload: TypeAlias = MutableMapping[str, Any]
XmppOptionalIdInput: TypeAlias = int | str | None
XmppPayload: TypeAlias = Mapping[str, Any]
XmppPayloadDict: TypeAlias = Dict[str, Any]
XmppPayloadList: TypeAlias = List[Dict[str, Any]]
XmppIncomingSegments: TypeAlias = List[XmppIncomingSegment]
XmppSegment: TypeAlias = XmppHostMessageSegment
XmppSegments: TypeAlias = List[XmppHostMessageSegment]
