"""XMPP 通知事件渲染器。"""

from __future__ import annotations

from typing import Any, Mapping


class XmppNoticeTextRenderer:
    """根据通知载荷生成可读文本。"""

    def build_notice_text(self, payload: Mapping[str, Any]) -> str:
        """根据 XMPP 通知事件生成可读文本。

        Args:
            payload: 原始通知事件。

        Returns:
            str: 生成的可读通知文本。
        """
        notice_type = str(payload.get("notice_type") or "").strip()
        if notice_type == "presence":
            return self._build_presence_text(payload)
        if notice_type == "muc_join":
            return self._build_muc_join_text(payload)
        if notice_type == "muc_leave":
            return self._build_muc_leave_text(payload)
        return f"[notice] {notice_type}"

    def _build_presence_text(self, payload: Mapping[str, Any]) -> str:
        """构造 presence 变化文本。"""
        from_jid = str(payload.get("from_jid") or "").strip()
        show = str(payload.get("show") or "").strip()
        status = str(payload.get("status") or "").strip()
        status_map = {
            "away": "离开",
            "chat": "闲聊中",
            "dnd": "请勿打扰",
            "xa": "长期离开",
        }
        show_text = status_map.get(show, "在线")
        name = from_jid.split("@")[0] if "@" in from_jid else from_jid
        text = f"{name} 状态变更为: {show_text}"
        if status:
            text += f"（{status}）"
        return text

    def _build_muc_join_text(self, payload: Mapping[str, Any]) -> str:
        """构造 MUC 加入文本。"""
        from_jid = str(payload.get("from_jid") or "").strip()
        room_jid = str(payload.get("room_jid") or "").strip()
        room_name = room_jid.split("@")[0] if "@" in room_jid else room_jid
        name = from_jid.split("/")[-1] if "/" in from_jid else from_jid.split("@")[0]
        return f"{name} 加入了群聊 {room_name}"

    def _build_muc_leave_text(self, payload: Mapping[str, Any]) -> str:
        """构造 MUC 离开文本。"""
        from_jid = str(payload.get("from_jid") or "").strip()
        room_jid = str(payload.get("room_jid") or "").strip()
        room_name = room_jid.split("@")[0] if "@" in room_jid else room_jid
        name = from_jid.split("/")[-1] if "/" in from_jid else from_jid.split("@")[0]
        return f"{name} 离开了群聊 {room_name}"
