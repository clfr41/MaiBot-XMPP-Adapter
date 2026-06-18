"""XMPP 出站消息段编码器。

将 Host 消息段转换为 XMPP 纯文本消息。
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping


class XmppOutboundSegmentEncoder:
    """将 Host 消息段转换为 XMPP 文本。"""

    def convert_to_text(self, raw_message: Any) -> str:
        """将 Host 消息段列表转换为 XMPP 消息正文。

        Args:
            raw_message: Host 侧 ``raw_message`` 字段。

        Returns:
            str: 用于 XMPP message body 的纯文本。
        """
        if not isinstance(raw_message, list):
            return ""

        text_parts: List[str] = []
        segment_types = set()
        for item in raw_message:
            if not isinstance(item, Mapping):
                continue

            item_type = str(item.get("type") or "").strip()
            segment_types.add(item_type)

            if item_type == "text":
                text_parts.append(str(item.get("data") or ""))
            elif item_type == "at":
                item_data = item.get("data")
                if isinstance(item_data, Mapping):
                    target_id = str(item_data.get("target_user_id") or "").strip()
                    text_parts.append(f"@{target_id}")
            elif item_type == "image":
                text_parts.append("[图片]")
            elif item_type == "emoji":
                text_parts.append("[动画表情]")
            elif item_type == "voice":
                text_parts.append("[语音]")
            elif item_type == "video":
                text_parts.append("[视频]")
            elif item_type == "file":
                item_data = item.get("data")
                if isinstance(item_data, str):
                    text_parts.append(f"[文件: {item_data}]")
                elif isinstance(item_data, Mapping):
                    file_name = str(item_data.get("name") or item_data.get("file") or "").strip()
                    text_parts.append(f"[文件: {file_name}]" if file_name else "[文件]")
                else:
                    text_parts.append("[文件]")
            elif item_type == "reply":
                text_parts.append("[回复]")
            elif item_type == "forward":
                text_parts.append("[转发]")
            elif item_type == "music":
                text_parts.append("[音乐分享]")
            elif item_type == "dict":
                # DictComponent 降级为占位
                text_parts.append("[卡片消息]")
            else:
                text_parts.append(f"[{item_type}]")

        result = "".join(text_parts)
        return result
