"""XMPP 消息与互动 API 端点。"""

from __future__ import annotations

from typing import Any, Dict

from maibot_sdk import API

from .support import XmppApiParamsInput, XmppApiSupportMixin


class XmppMessageApiMixin(XmppApiSupportMixin):
    """XMPP 消息相关 API。"""

    @API("adapter.xmpp.message.send_message", description="发送 XMPP 消息", version="1", public=True)
    async def api_send_message(
        self,
        to_jid: object = "",
        body: object = "",
        message_type: str = "chat",
    ) -> Dict[str, Any]:
        """发送 XMPP 消息。

        Args:
            to_jid: 目标 JID。
            body: 消息正文。
            message_type: 消息类型 (chat/groupchat)。

        Returns:
            Dict[str, Any]: 发送结果。
        """
        to_jid_str = str(to_jid or "").strip()
        body_str = str(body or "")
        return await self._require_action_service().send_message(
            to_jid=to_jid_str,
            body=body_str,
            message_type=message_type,
        )

    @API("adapter.xmpp.message.send_presence", description="发送 XMPP 在线状态", version="1", public=True)
    async def api_send_presence(
        self,
        status: str = "",
        show: str = "",
    ) -> Dict[str, Any]:
        """发送 XMPP presence。

        Args:
            status: 状态文本。
            show: 在线状态 (away, chat, dnd, xa)。

        Returns:
            Dict[str, Any]: 发送结果。
        """
        return await self._require_action_service().send_presence(
            status=str(status or "").strip(),
            show=str(show or "").strip(),
        )

    @API("adapter.xmpp.message.join_muc", description="加入 XMPP 群聊 (MUC)", version="1", public=True)
    async def api_join_muc(
        self,
        room_jid: object = "",
        nickname: str = "",
    ) -> Dict[str, Any]:
        """加入 MUC 房间。

        Args:
            room_jid: 房间 JID。
            nickname: 在房间中的昵称。

        Returns:
            Dict[str, Any]: 加入结果。
        """
        return await self._require_action_service().join_muc(
            room_jid=str(room_jid or "").strip(),
            nickname=nickname,
        )

    @API("adapter.xmpp.message.send_msg", description="调用 send_msg 动作", version="1", public=True)
    async def api_action_send_msg(self, params: XmppApiParamsInput = None) -> Dict[str, Any]:
        """调用 XMPP 的 ``send_msg`` 动作。"""
        return await self._call_xmpp_action("send_message", params)
