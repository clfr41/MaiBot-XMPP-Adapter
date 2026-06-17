"""XMPP 出站消息编解码。"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from .segment_encoder import XmppOutboundSegmentEncoder


class XmppOutboundCodec:
    """XMPP 出站消息编码器。"""

    def __init__(self) -> None:
        """初始化出站消息编码器。"""
        self._segment_encoder = XmppOutboundSegmentEncoder()

    def build_outbound_action(
        self,
        message: Mapping[str, Any],
        route: Mapping[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """为 Host 出站消息构造 XMPP 发送动作。

        Args:
            message: Host 侧标准 ``MessageDict``。
            route: Platform IO 路由信息。

        Returns:
            Tuple[str, Dict[str, Any]]: 动作名称与参数字典。

        Raises:
            ValueError: 当缺少目标 ID 时抛出。
        """
        message_info = message.get("message_info", {})
        if not isinstance(message_info, Mapping):
            message_info = {}

        group_info = message_info.get("group_info", {})
        if not isinstance(group_info, Mapping):
            group_info = {}

        additional_config = message_info.get("additional_config", {})
        if not isinstance(additional_config, Mapping):
            additional_config = {}

        raw_message = message.get("raw_message", [])
        body = self._segment_encoder.convert_to_text(raw_message)

        # 群聊消息
        if target_group_id := str(
            group_info.get("group_id")
            or additional_config.get("platform_io_target_group_id")
            or ""
        ).strip():
            return "send_group_message", {
                "to_jid": target_group_id,
                "body": body,
                "message_type": "groupchat",
            }

        # 私聊消息
        target_user_id = str(
            additional_config.get("platform_io_target_user_id")
            or additional_config.get("target_user_id")
            or route.get("target_user_id")
            or ""
        ).strip()
        if not target_user_id:
            raise ValueError("Outbound message is missing target_user_id")

        return "send_private_message", {
            "to_jid": target_user_id,
            "body": body,
            "message_type": "chat",
        }
