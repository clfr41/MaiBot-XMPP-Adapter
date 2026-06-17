"""XMPP API 端点的公共辅助能力。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, TypeAlias

from maibot_sdk import API

from ..types import XmppActionParamsInput, XmppActionResponse, XmppIdInput

if TYPE_CHECKING:
    from ..services import XmppActionService, XmppQueryService


XmppApiIdInput: TypeAlias = XmppIdInput
XmppApiParamsInput: TypeAlias = XmppActionParamsInput


class XmppApiSupportMixin:
    """XMPP API 端点共享辅助逻辑。"""

    _action_service: Optional["XmppActionService"]
    _query_service: Optional["XmppQueryService"]

    def _ensure_runtime_components(self) -> None:
        """确保运行时组件已经初始化。"""
        raise NotImplementedError

    @staticmethod
    def _coerce_int(value: object, field_name: str, expectation: str) -> int:
        """将受支持的输入值转换为整数。"""
        if isinstance(value, bool):
            raise ValueError(f"{field_name} 必须是{expectation}")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            try:
                return int(value)
            except (OverflowError, ValueError) as exc:
                raise ValueError(f"{field_name} 必须是{expectation}") from exc
        if isinstance(value, str):
            normalized_value = value.strip()
            if not normalized_value:
                raise ValueError(f"{field_name} 必须是{expectation}")
            try:
                return int(normalized_value)
            except ValueError as exc:
                raise ValueError(f"{field_name} 必须是{expectation}") from exc
        raise ValueError(f"{field_name} 必须是{expectation}")

    def _require_query_service(self) -> "XmppQueryService":
        """返回当前可用的 XMPP 查询服务。"""
        self._ensure_runtime_components()
        query_service = self._query_service
        if query_service is None:
            raise RuntimeError("XMPP 查询服务尚未初始化")
        return query_service

    def _require_action_service(self) -> "XmppActionService":
        """返回当前可用的 XMPP 动作服务。"""
        self._ensure_runtime_components()
        action_service = self._action_service
        if action_service is None:
            raise RuntimeError("XMPP 动作服务尚未初始化")
        return action_service

    @staticmethod
    def _normalize_positive_int(value: object, field_name: str) -> int:
        """将任意值规范化为正整数。"""
        normalized_value = XmppApiSupportMixin._coerce_int(value, field_name, "正整数")
        if normalized_value <= 0:
            raise ValueError(f"{field_name} 必须是正整数")
        return normalized_value

    @staticmethod
    def _normalize_non_empty_string(value: object, field_name: str) -> str:
        """将任意值规范化为非空字符串。"""
        normalized_value = str(value or "").strip()
        if not normalized_value:
            raise ValueError(f"{field_name} 不能为空")
        return normalized_value

    @staticmethod
    def _normalize_params(params: XmppApiParamsInput) -> Dict[str, Any]:
        """将动作参数规范化为可变字典。"""
        if params is None:
            return {}
        if not isinstance(params, Mapping):
            raise ValueError("params 必须是对象")
        return {str(key): value for key, value in params.items()}

    async def _call_xmpp_action(
        self,
        action_name: str,
        params: XmppApiParamsInput = None,
    ) -> XmppActionResponse:
        """调用 XMPP 动作并返回原始响应。"""
        normalized_action_name = self._normalize_non_empty_string(action_name, "action_name")
        normalized_params = self._normalize_params(params)

        if normalized_action_name == "send_message":
            to_jid = normalized_params.get("to_jid", "")
            body = normalized_params.get("body", "")
            msg_type = normalized_params.get("message_type", "chat")
            return await self._require_action_service().send_message(to_jid, body, msg_type)

        if normalized_action_name == "send_presence":
            status = normalized_params.get("status", "")
            show = normalized_params.get("show", "")
            return await self._require_action_service().send_presence(status, show)

        if normalized_action_name == "join_muc":
            room_jid = normalized_params.get("room_jid", "")
            nickname = normalized_params.get("nickname", "")
            return await self._require_action_service().join_muc(room_jid, nickname)

        raise ValueError(f"未知的 XMPP 动作: {normalized_action_name}")

    @API("adapter.xmpp.action.call", description="调用 XMPP 动作", version="1", public=True)
    async def api_call_action(
        self,
        action_name: str = "",
        params: XmppApiParamsInput = None,
    ) -> XmppActionResponse:
        """调用 XMPP 动作。

        支持的动作:
        - send_message: 发送消息 (to_jid, body, message_type)
        - send_presence: 发送在线状态 (status, show)
        - join_muc: 加入群聊 (room_jid, nickname)

        Args:
            action_name: 动作名称。
            params: 动作参数。

        Returns:
            Dict[str, Any]: 响应字典。
        """
        return await self._call_xmpp_action(action_name, params)
