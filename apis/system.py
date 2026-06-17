"""XMPP 系统 API 端点。"""

from __future__ import annotations

from typing import Any, Dict

from maibot_sdk import API

from .support import XmppApiSupportMixin


class XmppSystemApiMixin(XmppApiSupportMixin):
    """XMPP 系统相关 API。"""

    @API("adapter.xmpp.system.get_status", description="获取适配器状态", version="1", public=True)
    async def api_get_status(self) -> Dict[str, Any]:
        """获取适配器连接状态。

        Returns:
            Dict[str, Any]: 状态信息。
        """
        try:
            info = await self._require_query_service().get_self_info()
            return {"success": True, "connected": True, **info}
        except Exception as exc:
            return {"success": True, "connected": False, "error": str(exc)}
