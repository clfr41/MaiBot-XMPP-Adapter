"""XMPP 适配器内部共享类型。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, TypeAlias

from typing_extensions import NotRequired, TypedDict


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
XmppPayload: TypeAlias = Mapping[str, Any]
XmppPayloadDict: TypeAlias = Dict[str, Any]
XmppSegment: TypeAlias = XmppHostMessageSegment
XmppSegments: TypeAlias = List[XmppHostMessageSegment]
