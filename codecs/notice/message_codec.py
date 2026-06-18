"""XMPP 通知事件编解码器。"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

import time

from ...types import XmppPayload, XmppPayloadDict
from .renderer import XmppNoticeTextRenderer


class XmppNoticeCodec:
    """XMPP 通知事件编码器。"""

    def __init__(self, logger: Any) -> None:
        """初始化通知事件编码器。

        Args:
            logger: 插件日志对象。
        """
        self._logger = logger
        self._renderer = XmppNoticeTextRenderer()

    async def build_notice_message_dict(
        self, payload: XmppPayload, notice_type: str
    ) -> Optional[XmppPayloadDict]:
        """将 XMPP 通知事件转换为 Host 可接受的消息字典。

        Args:
            payload: XMPP 推送的原始通知事件。
            notice_type: 通知类型标识。

        Returns:
            Optional[XmppPayloadDict]: 成功时返回标准 ``MessageDict``；无法识别时返回 ``None``。
        """
        # 安全展开 payload，避免 payload 中的键意外覆盖 notice_type
        safe_payload = dict(payload)
        safe_payload.pop("notice_type", None)  # 排除冲突键
        notice_text = self._renderer.build_notice_text(
            {"notice_type": notice_type, **safe_payload}
        )
        if not notice_text:
            self._logger.debug(f"通知事件被跳过: notice_type={notice_type} (渲染器返回空)")
            return None

        from_jid = str(payload.get("from_jid") or "").strip()
        user_nickname = from_jid.split("@")[0] if "@" in from_jid else from_jid or "系统通知"
        user_info = {
            "user_id": from_jid or "system",
            "user_nickname": user_nickname,
            "user_cardname": None,
        }

        additional_config: Dict[str, Any] = {
            "xmpp_notice_type": notice_type,
        }

        timestamp_seconds = time.time()
        message_id = f"xmpp-notice-{uuid4().hex}"

        self._logger.debug(
            f"通知事件编码完成: notice_type={notice_type} "
            f"from={from_jid} text_len={len(notice_text)}"
        )

        return {
            "message_id": message_id,
            "timestamp": str(float(timestamp_seconds)),
            "platform": "xmpp",
            "message_info": {
                "user_info": user_info,
                "additional_config": additional_config,
            },
            "raw_message": [{"type": "text", "data": notice_text}],
            "is_mentioned": False,
            "is_at": False,
            "is_emoji": False,
            "is_picture": False,
            "is_command": False,
            "is_notify": True,
            "session_id": "",
            "processed_plain_text": notice_text,
            "display_message": notice_text,
        }
