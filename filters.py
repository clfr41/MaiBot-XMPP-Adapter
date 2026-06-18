"""XMPP 入站消息过滤。"""

from __future__ import annotations

import re
from typing import Any, Collection, List, Pattern

from .config import XmppChatConfig, XmppFilterConfig


class XmppRegexFilter:
    """XMPP 正则表达式消息内容过滤器。

    通过配置的正则表达式列表对消息纯文本进行匹配，
    支持黑名单（匹配则丢弃）和白名单（仅放行匹配）两种模式。
    """

    def __init__(self, logger: Any) -> None:
        """初始化正则表达式过滤器。

        Args:
            logger: 插件日志对象。
        """
        self._logger = logger
        self._compiled_patterns: List[Pattern[str]] = []
        self._source_patterns: List[str] = []

    def reload_patterns(self, patterns: List[str]) -> None:
        """根据正则表达式列表重新编译。

        无效的正则表达式会被记录警告并跳过。

        Args:
            patterns: 正则表达式字符串列表。
        """
        compiled: List[Pattern[str]] = []
        source: List[str] = []
        invalid_count = 0
        for pattern_text in patterns:
            try:
                compiled.append(re.compile(pattern_text))
                source.append(pattern_text)
            except re.error as exc:
                invalid_count += 1
                self._logger.warning(
                    f"XMPP 正则过滤器忽略无效正则表达式 '{pattern_text}': {exc}"
                )
        self._compiled_patterns = compiled
        self._source_patterns = source
        self._logger.debug(
            f"XMPP 正则过滤器已加载 {len(compiled)} / {len(patterns)} 条规则"
            f"{f' ({invalid_count} 条无效)' if invalid_count else ''}: {source}"
        )

    def is_message_allowed(self, plain_text: str, filter_config: XmppFilterConfig) -> bool:
        """检查消息文本是否通过正则表达式过滤。

        Args:
            plain_text: 消息纯文本内容。
            filter_config: 当前生效的消息过滤配置。

        Returns:
            bool: 若消息允许继续进入 Host，则返回 ``True``。
        """
        if not filter_config.regex_filter_enabled:
            return True

        if not self._compiled_patterns:
            if filter_config.regex_filter_mode == "whitelist":
                self._log_regex_rejection(
                    filter_config.regex_filter_show_dropped,
                    "XMPP 白名单正则过滤器无有效规则，所有消息被丢弃 "
                    f"(text_len={len(plain_text)})",
                )
                return False
            self._logger.debug(
                "XMPP 黑名单正则过滤器无有效规则，放行所有消息"
            )
            return True

        matched = self._matches_any_pattern(plain_text)
        mode = filter_config.regex_filter_mode

        if mode == "blacklist" and matched:
            self._log_regex_rejection(
                filter_config.regex_filter_show_dropped,
                f"XMPP 消息匹配黑名单正则，消息被丢弃: {plain_text!r}",
            )
            return False

        if mode == "whitelist" and not matched:
            self._log_regex_rejection(
                filter_config.regex_filter_show_dropped,
                f"XMPP 消息未匹配白名单正则，消息被丢弃: {plain_text!r}",
            )
            return False

        self._logger.debug(
            f"XMPP 正则过滤通过: mode={mode} matched={matched} "
            f"text_len={len(plain_text)}"
        )
        return True

    def _matches_any_pattern(self, text: str) -> bool:
        """判断文本是否匹配任意一条已编译的正则表达式。"""
        for idx, pattern in enumerate(self._compiled_patterns):
            if pattern.search(text):
                self._logger.debug(f"正则匹配成功: 规则 #{idx} pattern={self._source_patterns[idx]!r}")
                return True
        return False

    def _log_regex_rejection(self, enabled: bool, message: str) -> None:
        """按配置决定是否记录正则过滤丢弃日志。"""
        if enabled:
            self._logger.warning(message)


class XmppChatFilter:
    """XMPP 聊天名单过滤器。"""

    def __init__(self, logger: Any) -> None:
        """初始化聊天名单过滤器。

        Args:
            logger: 插件日志对象。
        """
        self._logger = logger

    def is_inbound_chat_allowed(
        self,
        sender_jid: str,
        group_jid: str,
        chat_config: XmppChatConfig,
    ) -> bool:
        """检查入站消息是否通过聊天名单过滤。

        Args:
            sender_jid: 发送者 JID (bare)。
            group_jid: MUC JID；私聊时为空字符串。
            chat_config: 当前生效的聊天配置。

        Returns:
            bool: 若消息允许继续进入 Host，则返回 ``True``。
        """
        # 全局禁止名单检查（优先级最高）
        if sender_jid in chat_config.ban_user_id:
            self._logger.warning(
                f"XMPP 用户 {sender_jid} 在全局禁止名单中，消息被丢弃"
            )
            return False

        if not chat_config.enable_chat_list_filter:
            self._logger.debug(
                f"聊天名单过滤已关闭，放行: sender={sender_jid} "
                f"group={group_jid or '(私聊)'}"
            )
            return True

        if group_jid:
            if not self._is_id_allowed_by_list_policy(
                group_jid, chat_config.group_list_type, chat_config.group_list
            ):
                self._log_chat_list_rejection(
                    chat_config.show_dropped_chat_list_messages,
                    f"XMPP 群聊 {group_jid} 未通过聊天名单过滤，消息被丢弃 "
                    f"(mode={chat_config.group_list_type})",
                )
                return False
            self._logger.debug(
                f"聊天名单过滤通过: group={group_jid} mode={chat_config.group_list_type}"
            )
            return True

        # 私聊
        if not self._is_id_allowed_by_list_policy(
            sender_jid,
            chat_config.private_list_type,
            chat_config.private_list,
        ):
            self._log_chat_list_rejection(
                chat_config.show_dropped_chat_list_messages,
                f"XMPP 私聊用户 {sender_jid} 未通过聊天名单过滤，消息被丢弃 "
                f"(mode={chat_config.private_list_type})",
            )
            return False

        self._logger.debug(
            f"聊天名单过滤通过: sender={sender_jid} mode={chat_config.private_list_type}"
        )
        return True

    def _log_chat_list_rejection(self, enabled: bool, message: str) -> None:
        """按配置决定是否记录聊天名单过滤丢弃日志。"""
        if enabled:
            self._logger.warning(message)

    @staticmethod
    def _is_id_allowed_by_list_policy(
        target_id: str, list_type: str, configured_ids: Collection[str]
    ) -> bool:
        """根据白名单或黑名单规则判断目标 ID 是否允许通过。"""
        if list_type == "whitelist":
            return target_id in configured_ids
        return target_id not in configured_ids
