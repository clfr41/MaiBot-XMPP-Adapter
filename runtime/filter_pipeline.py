"""XMPP 入站消息过滤管道。

将 ``handle_inbound_message`` 中的过滤逻辑抽取为显式管道，
便于单测覆盖和后期新增过滤规则。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..config import XmppChatConfig, XmppFilterConfig
from ..filters import XmppChatFilter, XmppRegexFilter
from ..types import XmppPayloadDict


@dataclass
class InboundMessageContext:
    """过滤管道输出的消息上下文。"""

    sender_jid: str
    group_jid: str
    self_id: str
    from_jid: str
    body: str
    is_group: bool


class XmppInboundFilterPipeline:
    """入站消息过滤管道，按顺序执行各过滤步骤。

    若任一步骤拒绝消息，管道返回 ``None``；否则返回 ``InboundMessageContext``。
    """

    def __init__(
        self,
        logger: Any,
        chat_filter: XmppChatFilter,
        regex_filter: XmppRegexFilter,
    ) -> None:
        """初始化过滤管道。

        Args:
            logger: 日志对象。
            chat_filter: 聊天名单过滤器。
            regex_filter: 正则内容过滤器。
        """
        self._logger = logger
        self._chat_filter = chat_filter
        self._regex_filter = regex_filter

    def run(
        self,
        payload: XmppPayloadDict,
        is_group: bool,
        self_id: str,
        settings_filters: XmppFilterConfig,
        settings_chat: XmppChatConfig,
        muc_nickname: str = "",
    ) -> Optional[InboundMessageContext]:
        """执行完整过滤管道。

        Args:
            payload: XMPP 原始消息事件。
            is_group: 是否为群聊消息。
            self_id: 当前机器人 bare JID。
            settings_filters: 插件过滤配置。
            settings_chat: 插件聊天名单配置。
            muc_nickname: 机器人在 MUC 房间中的昵称，用于 MUC 自身消息检测。

        Returns:
            过滤通过时返回 ``InboundMessageContext``，被拦截时返回 ``None``。
        """
        # ── Step 1: 验证 from_jid ──
        from_jid = str(payload.get("from_jid") or "").strip()
        if not from_jid:
            self._logger.debug("入站消息缺少 from_jid，已跳过")
            return None

        # ── Step 2: 验证 body ──
        body = str(payload.get("body") or "").strip()
        if not body:
            self._logger.debug(
                f"入站消息 body 为空，已跳过: type={payload.get('type')} from={from_jid}"
            )
            return None

        # ── Step 3: 解析发送者 JID ──
        if is_group:
            sender_jid = self._extract_muc_sender(from_jid)
            group_jid = self._extract_bare_jid(from_jid)
            self._logger.debug(
                f"MUC 消息解析: full={from_jid} -> sender={sender_jid} group={group_jid}"
            )
        else:
            sender_jid = self._extract_bare_jid(from_jid)
            group_jid = ""

        # ── Step 4: 自身消息过滤 ──
        if settings_filters.ignore_self_message:
            if is_group:
                # MUC 消息的 sender_jid 是 nickname（如 "maibot"），
                # 需要与配置的 MUC 昵称比较，不能与 bare JID 比较。
                if muc_nickname and sender_jid == muc_nickname:
                    self._logger.debug(
                        f"忽略自身 MUC 消息: sender={sender_jid} == muc_nickname={muc_nickname}"
                    )
                    return None
            else:
                # 私聊消息的 sender_jid 是 bare JID，与自身 JID 比较。
                if self_id and sender_jid == self_id:
                    self._logger.debug(
                        f"忽略自身私聊消息: sender={sender_jid} == self={self_id}"
                    )
                    return None

        # ── Step 5: 聊天名单过滤 ──
        if not self._chat_filter.is_inbound_chat_allowed(sender_jid, group_jid, settings_chat):
            self._logger.debug(
                f"聊天名单过滤拦截消息: sender={sender_jid} group={group_jid or '(私聊)'}"
            )
            return None

        self._logger.debug(f"过滤管道通过: sender={sender_jid} group={group_jid or '(私聊)'}")

        return InboundMessageContext(
            sender_jid=sender_jid,
            group_jid=group_jid,
            self_id=self_id,
            from_jid=from_jid,
            body=body,
            is_group=is_group,
        )

    def is_regex_allowed(
        self,
        plain_text: str,
        sender_jid: str,
        settings_filters: XmppFilterConfig,
    ) -> bool:
        """检查纯文本是否通过正则过滤。

        作为管道的扩展步骤，在消息字典构建后调用。

        Args:
            plain_text: 消息明文。
            sender_jid: 发送者 JID。
            settings_filters: 插件过滤配置。

        Returns:
            bool: 通过时返回 ``True``。
        """
        if not self._regex_filter.is_message_allowed(plain_text, settings_filters):
            self._logger.debug(
                f"正则过滤拦截消息: sender={sender_jid} "
                f"text_len={len(plain_text)} text={plain_text[:50]!r}"
            )
            return False
        return True

    @staticmethod
    def _extract_bare_jid(full_jid: str) -> str:
        """从 full JID 提取 bare JID。"""
        return full_jid.split("/")[0] if "/" in full_jid else full_jid

    @staticmethod
    def _extract_muc_sender(muc_from: str) -> str:
        """从 MUC 消息的 from 字段中提取发送者标识。"""
        if "/" in muc_from:
            return muc_from.split("/", 1)[1]
        return muc_from
