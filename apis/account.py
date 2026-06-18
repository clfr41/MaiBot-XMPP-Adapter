"""XMPP 账号与用户侧 API 端点。"""

from __future__ import annotations

from typing import Any, Dict

from maibot_sdk import API

from .support import XmppApiSupportMixin


class XmppAccountApiMixin(XmppApiSupportMixin):
    """XMPP 账号与资料相关 API。"""

    @API("adapter.xmpp.account.get_self_info", description="获取机器人自身信息", version="1", public=True)
    async def api_get_self_info(self) -> Dict[str, Any]:
        """获取当前机器人 JID 等信息。

        Returns:
            Dict[str, Any]: 包含 jid 和 full_jid。
        """
        return await self._require_action_service().get_self_info()
