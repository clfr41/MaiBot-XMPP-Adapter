"""XMPP 入站纯文本与二进制辅助。"""

from __future__ import annotations

from typing import Any, Mapping

import base64

from ...types import XmppSegments


class XmppInboundTextMixin:
    """封装入站纯文本与二进制辅助逻辑。"""

    # 日志对象，子类（XmppInboundCodec）在 __init__ 中设置
    _logger: Any

    def build_plain_text(self, raw_message: XmppSegments) -> str:
        """从标准消息段中提取可展示的纯文本。

        Args:
            raw_message: 标准化后的消息段列表。

        Returns:
            str: 用于 Host 展示和命令判断的纯文本内容。
        """
        plain_text_parts: list[str] = []
        for item in raw_message:
            if not isinstance(item, Mapping):
                self._logger.debug(f"build_plain_text 跳过非 Mapping 项: {type(item)}")
                continue
            item_type = str(item.get("type") or "").strip()
            item_data = item.get("data")
            if item_type == "text":
                plain_text_parts.append(str(item_data or ""))
            elif item_type == "at" and isinstance(item_data, Mapping):
                at_target_name = str(
                    item_data.get("target_user_nickname")
                    or item_data.get("target_user_id")
                    or ""
                ).strip()
                if at_target_name:
                    plain_text_parts.append(f"@{at_target_name}")
            elif item_type in {"image", "emoji", "voice"}:
                plain_text_parts.append(f"[{item_type}]")
            else:
                self._logger.debug(
                    f"build_plain_text 遇到未处理的段类型: {item_type}"
                )

        plain_text = "".join(part for part in plain_text_parts if part).strip()
        result = plain_text or "[empty]"
        self._logger.debug(
            f"build_plain_text: {len(raw_message)} 段 -> {len(result)} 字符"
        )
        return result

    @staticmethod
    def _encode_binary(binary_data: bytes) -> str:
        """将二进制内容编码为 Base64 字符串。"""
        return base64.b64encode(binary_data).decode("utf-8")

    @staticmethod
    def _decode_binary(binary_base64: str) -> bytes:
        """将 Base64 字符串解码为二进制内容。"""
        return base64.b64decode(binary_base64)
