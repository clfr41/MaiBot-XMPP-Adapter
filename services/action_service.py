"""XMPP 底层动作调用服务。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional

import asyncio

if TYPE_CHECKING:
    from ..transport import XmppTransportClient


class XmppActionService:
    """XMPP 底层动作与资源访问服务。"""

    def __init__(self, logger: Any, transport: "XmppTransportClient") -> None:
        """初始化底层动作服务。

        Args:
            logger: 插件日志对象。
            transport: XMPP 传输层客户端。
        """
        self._logger = logger
        self._transport = transport

    async def send_message(self, to_jid: str, body: str, message_type: str = "chat") -> Dict[str, Any]:
        """发送 XMPP 消息。

        Args:
            to_jid: 目标 JID。
            body: 消息正文。
            message_type: 消息类型 (chat/groupchat)。

        Returns:
            Dict[str, Any]: 发送结果。
        """
        try:
            return await self._transport.send_message(to_jid, body, message_type)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise RuntimeError(f"XMPP 消息发送失败: to={to_jid} error={exc}") from exc

    async def send_presence(self, status: str = "", show: str = "") -> Dict[str, Any]:
        """发送 XMPP presence。

        Args:
            status: 状态文本。
            show: 在线状态。

        Returns:
            Dict[str, Any]: 发送结果。
        """
        return await self._transport.send_presence(status, show)

    async def join_muc(self, room_jid: str, nickname: str = "") -> Dict[str, Any]:
        """加入 MUC 房间。

        Args:
            room_jid: 房间 JID。
            nickname: 昵称。

        Returns:
            Dict[str, Any]: 加入结果。
        """
        return await self._transport.join_muc(room_jid, nickname)
