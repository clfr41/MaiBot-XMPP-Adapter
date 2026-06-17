"""XMPP 通知编解码公共辅助函数。"""

from __future__ import annotations

from typing import Any, Optional


def normalize_optional_string(value: Any) -> Optional[str]:
    """将任意值规范化为可选字符串。

    Args:
        value: 待规范化的值。

    Returns:
        Optional[str]: 规范化后的字符串；若值为空则返回 ``None``。
    """
    if value is None:
        return None
    normalized_value = str(value).strip()
    return normalized_value if normalized_value else None
