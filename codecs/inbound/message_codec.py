"""XMPP 入站消息编解码。"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple
from uuid import uuid4

import time

from ...services import XmppQueryService
from ...types import XmppPayload, XmppSegment, XmppSegments
from .text import XmppInboundTextMixin


class XmppInboundCodec(XmppInboundTextMixin):
    """XMPP 入站消息编码器。"""

    def __init__(self, logger: Any, query_service: XmppQueryService) -> None:
        """初始化入站消息编码器。

        Args:
            logger: 插件日志对象。
            query_service: XMPP 查询服务。
        """
        self._logger = logger
        self._query_service = query_service

    async def build_message_dict(
        self,
        payload: XmppPayload,
        self_id: str,
        sender_jid: str,
        is_group: bool,
        group_jid: str,
    ) -> Dict[str, Any]:
        """构造 Host 侧可接受的 ``MessageDict``。

        Args:
            payload: XMPP 原始消息事件。
            self_id: 当前机器人 JID (bare)。
            sender_jid: 发送者 JID。
            is_group: 是否为群聊。
            group_jid: 群聊 JID（MUC room）。

        Returns:
            Dict[str, Any]: 规范化后的 ``MessageDict``。
        """
        message_type = "group" if is_group else "private"
        body = str(payload.get("body") or "").strip()
        from_jid = str(payload.get("from_jid") or "").strip()

        # 构造消息段
        raw_message: XmppSegments = []
        if body:
            raw_message.append(self._build_text_segment(body))
        else:
            raw_message.append(self._build_text_segment("[empty]"))

        plain_text = self.build_plain_text(raw_message)
        timestamp_seconds = time.time()

        # 用户昵称使用 sender_jid 作为默认值
        user_nickname = self._extract_display_name(from_jid, is_group)

        additional_config: Dict[str, Any] = {
            "self_id": self_id,
            "xmpp_message_type": message_type,
            "xmpp_from_jid": from_jid,
        }
        if group_jid:
            additional_config["platform_io_target_group_id"] = group_jid
        else:
            additional_config["platform_io_target_user_id"] = sender_jid

        message_info: Dict[str, Any] = {
            "user_info": {
                "user_id": sender_jid,
                "user_nickname": user_nickname,
                "user_cardname": None,
            },
            "additional_config": additional_config,
        }
        if group_jid:
            message_info["group_info"] = {
                "group_id": group_jid,
                "group_name": self._extract_room_name(group_jid),
            }

        message_id = str(payload.get("id") or f"xmpp-{uuid4().hex}").strip()
        return {
            "message_id": message_id,
            "timestamp": str(float(timestamp_seconds)),
            "platform": "xmpp",
            "message_info": message_info,
            "raw_message": raw_message,
            "is_mentioned": self._check_mention(body, self_id),
            "is_at": self._check_mention(body, self_id),
            "is_emoji": False,
            "is_picture": False,
            "is_command": plain_text.startswith("/"),
            "is_notify": False,
            "session_id": "",
            "processed_plain_text": plain_text,
            "display_message": plain_text,
        }

    @staticmethod
    def _build_text_segment(text: str) -> XmppSegment:
        """构造一条纯文本 Host 消息段。"""
        return {"type": "text", "data": text}

    @staticmethod
    def _check_mention(body: str, self_id: str) -> bool:
        """检查消息是否 @ 了机器人。

        在 XMPP 中，@ 通常表现为包含 JID 或昵称。
        此处做简单检查。

        Args:
            body: 消息正文。
            self_id: 机器人 JID。

        Returns:
            bool: 是否被 @。
        """
        if not body or not self_id:
            return False
        local_part = self_id.split("@")[0] if "@" in self_id else self_id
        return local_part.lower() in body.lower() or self_id.lower() in body.lower()

    @staticmethod
    def _extract_display_name(from_jid: str, is_group: bool) -> str:
        """提取显示名。

        Args:
            from_jid: 来源 JID。
            is_group: 是否群聊。

        Returns:
            str: 显示名。
        """
        if is_group and "/" in from_jid:
            # MUC: room@conference/nickname -> nickname
            return from_jid.split("/", 1)[1]
        if "@" in from_jid:
            return from_jid.split("@")[0]
        return from_jid

    @staticmethod
    def _extract_room_name(room_jid: str) -> str:
        """从 MUC JID 提取房间名称。

        Args:
            room_jid: MUC 房间 JID。

        Returns:
            str: 房间名称。
        """
        if "@" in room_jid:
            return room_jid.split("@")[0]
        return room_jid
