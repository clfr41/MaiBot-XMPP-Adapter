"""XMPP 查询服务。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .action_service import XmppActionService


class XmppQueryService:
    """XMPP 查询与管理动作服务。"""

    def __init__(self, action_service: XmppActionService, logger: Any) -> None:
        """初始化查询服务。

        Args:
            action_service: XMPP 底层动作服务。
            logger: 插件日志对象。
        """
        self._action_service = action_service
        self._logger = logger

    async def send_message(self, to_jid: str, body: str, message_type: str = "chat") -> Dict[str, Any]:
        """发送 XMPP 消息。

        Args:
            to_jid: 目标 JID。
            body: 消息正文。
            message_type: 消息类型。

        Returns:
            Dict[str, Any]: 发送结果。
        """
        self._logger.debug(
            f"查询服务: send_message to={to_jid} type={message_type} body_len={len(body)}"
        )
        return await self._action_service.send_message(to_jid, body, message_type)

    async def send_presence(self, status: str = "", show: str = "") -> Dict[str, Any]:
        """发送 XMPP presence。"""
        self._logger.debug(f"查询服务: send_presence status={status!r} show={show!r}")
        return await self._action_service.send_presence(status, show)

    async def join_muc(self, room_jid: str, nickname: str = "") -> Dict[str, Any]:
        """加入 MUC 房间。"""
        self._logger.debug(f"查询服务: join_muc room={room_jid} nickname={nickname}")
        return await self._action_service.join_muc(room_jid, nickname)

    async def get_self_info(self) -> Dict[str, Any]:
        """获取当前机器人信息。

        Returns:
            Dict[str, Any]: 包含 jid 等字段。
        """
        transport = self._action_service.transport
        result = {
            "jid": transport.bare_jid,
            "full_jid": transport.full_jid,
        }
        self._logger.debug(f"查询服务: get_self_info -> {result}")
        return result
