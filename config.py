"""XMPP 内置适配器配置模型。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Dict, List, Literal, Optional

import logging

from maibot_sdk import Field, PluginConfigBase
from pydantic import ValidationInfo, field_validator, model_validator

from .constants import (
    DEFAULT_ACTION_TIMEOUT_SEC,
    DEFAULT_CHAT_LIST_TYPE,
    DEFAULT_RECONNECT_DELAY_SEC,
    DEFAULT_XMPP_HOST,
    DEFAULT_XMPP_PORT,
    SUPPORTED_CONFIG_VERSION,
)

LOGGER = logging.getLogger("xmpp_adapter.config")


def _schema_i18n(
    *,
    label_en: str,
    label_ja: str,
    hint_en: Optional[str] = None,
    hint_ja: Optional[str] = None,
    placeholder_en: Optional[str] = None,
    placeholder_ja: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """构造 WebUI 配置项多语言说明，保留外层中文字段兼容旧格式。"""

    i18n: Dict[str, Dict[str, str]] = {
        "en_US": {"label": label_en},
        "ja_JP": {"label": label_ja},
    }
    if hint_en is not None:
        i18n["en_US"]["hint"] = hint_en
    if hint_ja is not None:
        i18n["ja_JP"]["hint"] = hint_ja
    if placeholder_en is not None:
        i18n["en_US"]["placeholder"] = placeholder_en
    if placeholder_ja is not None:
        i18n["ja_JP"]["placeholder"] = placeholder_ja
    return i18n


class XmppPluginOptions(PluginConfigBase):
    """插件级配置。"""

    __ui_label__: ClassVar[str] = "插件设置"
    __ui_order__: ClassVar[int] = 0

    enabled: bool = Field(
        default=False,
        description="是否启用 XMPP 适配器。",
        json_schema_extra={
            "hint": "关闭后插件会保持空闲，不会主动建立 XMPP 连接。",
            "i18n": _schema_i18n(
                label_en="Enable adapter",
                label_ja="アダプターを有効化",
                hint_en="When disabled, the plugin stays idle and will not open an XMPP connection.",
                hint_ja="無効にすると、プラグインは待機状態のままになり、XMPP 接続を開始しません。",
            ),
            "label": "启用适配器",
            "order": 0,
        },
    )
    slixmpp_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="slixmpp 库的日志级别。DEBUG 会输出完整的 XMPP stanza 内容（包括消息正文和 JID），生产环境请保持 INFO 或 WARNING。",
        json_schema_extra={
            "hint": "DEBUG 会输出完整的 XMPP stanza 内容（包括消息正文和 JID），生产环境建议保持 INFO 或 WARNING。",
            "i18n": _schema_i18n(
                label_en="slixmpp log level",
                label_ja="slixmpp ログレベル",
                hint_en="DEBUG prints full XMPP stanza content including message body and JID. Keep INFO or WARNING in production.",
                hint_ja="DEBUG はメッセージ本文や JID を含む完全な XMPP stanza を出力します。本番環境では INFO または WARNING を推奨。",
            ),
            "label": "slixmpp 日志级别",
            "order": 1,
        },
    )
    config_version: str = Field(
        default=SUPPORTED_CONFIG_VERSION,
        description="当前配置结构版本。",
        json_schema_extra={
            "disabled": True,
            "hidden": True,
            "i18n": _schema_i18n(label_en="Config version", label_ja="設定バージョン"),
            "label": "配置版本",
            "order": 99,
        },
    )

    def should_connect(self) -> bool:
        """判断当前配置下是否应当启动连接。

        Returns:
            bool: 若插件连接已启用，则返回 ``True``。
        """

        return self.enabled

    @field_validator("config_version", mode="before")
    @classmethod
    def _normalize_config_version(cls, value: Any) -> str:
        """规范化配置版本字段。

        Args:
            value: 原始配置值。

        Returns:
            str: 去除首尾空白后的配置版本；若为空则回退到当前支持版本。
        """

        normalized_value = _normalize_string(value)
        return normalized_value or SUPPORTED_CONFIG_VERSION

    @field_validator("slixmpp_log_level", mode="before")
    @classmethod
    def _normalize_slixmpp_log_level(cls, value: Any) -> str:
        """规范化日志级别字段。"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized_value = _normalize_string(value).upper()
        if normalized_value not in valid_levels:
            LOGGER.warning(f"无效的 slixmpp_log_level '{value}'，已回退到 'INFO'")
            return "INFO"
        return normalized_value


class XmppServerConfig(PluginConfigBase):
    """XMPP 服务器连接配置。"""

    __ui_label__: ClassVar[str] = "XMPP 连接"
    __ui_order__: ClassVar[int] = 1

    host: str = Field(
        default=DEFAULT_XMPP_HOST,
        description="XMPP 服务器主机地址。",
        json_schema_extra={
            "hint": "通常为运行 XMPP 服务器（如 Prosody、Ejabberd）的宿主机地址。",
            "i18n": _schema_i18n(
                label_en="Host address",
                label_ja="ホストアドレス",
                hint_en="Usually the host running the XMPP server (Prosody, Ejabberd, etc.).",
                hint_ja="通常は XMPP サーバー（Prosody、Ejabberd など）を実行しているホストです。",
                placeholder_en="127.0.0.1",
                placeholder_ja="127.0.0.1",
            ),
            "label": "主机地址",
            "order": 0,
            "placeholder": "127.0.0.1",
        },
    )
    port: int = Field(
        default=DEFAULT_XMPP_PORT,
        description="XMPP 服务器端口。",
        json_schema_extra={
            "hint": "标准 XMPP C2S 端口为 5222。",
            "i18n": _schema_i18n(
                label_en="Port",
                label_ja="ポート",
                hint_en="Standard XMPP C2S port is 5222.",
                hint_ja="標準の XMPP C2S ポートは 5222 です。",
            ),
            "label": "端口",
            "order": 1,
        },
    )
    jid: str = Field(
        default="",
        description="机器人的 JID (Jabber ID)，格式为 user@domain。",
        json_schema_extra={
            "hint": "例如 bot@example.com。",
            "i18n": _schema_i18n(
                label_en="JID (Jabber ID)",
                label_ja="JID（Jabber ID）",
                hint_en="e.g. bot@example.com.",
                hint_ja="例：bot@example.com。",
                placeholder_en="bot@example.com",
                placeholder_ja="bot@example.com",
            ),
            "label": "JID (Jabber ID)",
            "order": 2,
            "placeholder": "bot@example.com",
        },
    )
    password: str = Field(
        default="",
        description="机器人账号密码。",
        json_schema_extra={
            "hint": "XMPP 账号的登录密码。",
            "i18n": _schema_i18n(
                label_en="Password",
                label_ja="パスワード",
                hint_en="Login password for the XMPP account.",
                hint_ja="XMPP アカウントのログインパスワードです。",
                placeholder_en="Enter password",
                placeholder_ja="パスワードを入力",
            ),
            "input_type": "password",
            "label": "密码",
            "order": 3,
            "placeholder": "请输入密码",
        },
    )
    resource: str = Field(
        default="maibot",
        description="XMPP 资源标识。",
        json_schema_extra={
            "hint": "同一 JID 可有多资源同时在线，默认使用 maibot。",
            "i18n": _schema_i18n(
                label_en="Resource",
                label_ja="リソース",
                hint_en="Multiple resources can be online for the same JID. Defaults to maibot.",
                hint_ja="同一 JID で複数のリソースを同時にオンラインにできます。既定では maibot を使用します。",
            ),
            "label": "资源标识",
            "order": 4,
        },
    )
    use_tls: bool = Field(
        default=True,
        description="是否启用 TLS 加密连接。",
        json_schema_extra={
            "hint": "建议保持开启以确保通信安全。",
            "i18n": _schema_i18n(
                label_en="Use TLS",
                label_ja="TLS を使用",
                hint_en="Recommended to keep enabled for secure communication.",
                hint_ja="安全な通信のために有効のままにすることを推奨します。",
            ),
            "label": "启用 TLS",
            "order": 5,
        },
    )
    tls_verify: bool = Field(
        default=False,
        description="是否验证 TLS 证书。启用后将验证服务器证书的有效性和主机名。",
        json_schema_extra={
            "hint": "测试环境可关闭此选项以兼容自签名证书。生产环境建议启用。",
            "i18n": _schema_i18n(
                label_en="Verify TLS certificate",
                label_ja="TLS 証明書を検証",
                hint_en="Disable for self-signed certs in test environments. Enable in production.",
                hint_ja="テスト環境では自己署名証明書のために無効にできます。本番環境では有効にしてください。",
            ),
            "label": "验证 TLS 证书",
            "order": 6,
        },
    )
    heartbeat_interval: float = Field(
        default=0.0,
        description="已废弃：应用层心跳间隔（秒）。适配器现仅依赖传输层断连检测，设为 0 可完全禁用。",
        json_schema_extra={
            "hint": "当前版本不再使用应用层心跳，保留该字段仅为兼容旧配置。",
            "i18n": _schema_i18n(
                label_en="Heartbeat interval (sec) [deprecated]",
                label_ja="ハートビート間隔（秒）[非推奨]",
                hint_en="Application-layer heartbeat is no longer used. Set to 0 to ignore.",
                hint_ja="アプリケーションレイヤーのハートビートは現在使用されていません。0 に設定すると無視されます。",
            ),
            "label": "心跳间隔（秒）[已废弃]",
            "order": 6,
            "step": 1,
        },
    )
    reconnect_delay_sec: float = Field(
        default=DEFAULT_RECONNECT_DELAY_SEC,
        description="连接断开后的重连等待时间，单位为秒。",
        json_schema_extra={
            "hint": "连接断开后会等待该时长再尝试重新连接。",
            "i18n": _schema_i18n(
                label_en="Reconnect delay (sec)",
                label_ja="再接続待機（秒）",
                hint_en="After a disconnect, wait this long before trying to reconnect.",
                hint_ja="接続が切断された後、再接続を試すまでこの時間待機します。",
            ),
            "label": "重连等待（秒）",
            "order": 7,
            "step": 1,
        },
    )
    action_timeout_sec: float = Field(
        default=DEFAULT_ACTION_TIMEOUT_SEC,
        description="调用 XMPP 动作的超时时间，单位为秒。",
        json_schema_extra={
            "hint": "发送消息、查询信息等动作会在超时后报错。",
            "i18n": _schema_i18n(
                label_en="Action timeout (sec)",
                label_ja="アクションタイムアウト（秒）",
                hint_en="Actions such as sending messages or querying info fail after this timeout.",
                hint_ja="メッセージ送信や情報取得などのアクションは、この時間を超えるとエラーになります。",
            ),
            "label": "动作超时（秒）",
            "order": 8,
            "step": 1,
        },
    )
    connection_id: str = Field(
        default="",
        description="可选连接标识，用于区分多条 XMPP 链路。",
        json_schema_extra={
            "hint": "当存在多条 XMPP 连接时，可用它作为路由作用域标识。",
            "i18n": _schema_i18n(
                label_en="Connection ID",
                label_ja="接続識別子",
                hint_en="When multiple XMPP connections exist, use this as the routing scope identifier.",
                hint_ja="複数の XMPP 接続がある場合、ルーティングスコープの識別子として使用できます。",
                placeholder_en="For example: primary",
                placeholder_ja="例：primary",
            ),
            "label": "连接标识",
            "order": 9,
            "placeholder": "例如：primary",
        },
    )
    # ── MUC 自动加入配置 ──
    muc_rooms: List[str] = Field(
        default_factory=list,
        description="可选：上线后自动加入的 MUC（群聊）房间 JID 列表。",
        json_schema_extra={
            "hint": "如需自动加入群聊，请填写完整的房间 JID，例如 room@conference.example.com。留空则不自动加入任何房间。",
            "i18n": _schema_i18n(
                label_en="Auto-join MUC rooms",
                label_ja="自動参加 MUC ルーム",
                hint_en="List of MUC room JIDs to join automatically on login. Leave empty to disable.",
                hint_ja="ログイン時に自動的に参加する MUC ルームの JID リスト。空の場合は自動参加しません。",
                placeholder_en="room@conference.example.com",
                placeholder_ja="room@conference.example.com",
            ),
            "label": "自动加入的 MUC 房间",
            "order": 10,
            "placeholder": "room@conference.example.com",
        },
    )
    muc_nickname: str = Field(
        default="",
        description="在 MUC 房间中使用的昵称，留空则自动使用 JID 的本地部分。",
        json_schema_extra={
            "hint": "例如 MaiBot。若不填，将使用 JID 中 @ 之前的部分。",
            "i18n": _schema_i18n(
                label_en="MUC nickname",
                label_ja="MUC ニックネーム",
                hint_en="Nickname used in MUC rooms. If empty, uses the local part of the JID.",
                hint_ja="MUC ルームで使用するニックネーム。空の場合は JID のローカル部分を使用します。",
                placeholder_en="MaiBot",
                placeholder_ja="MaiBot",
            ),
            "label": "MUC 昵称",
            "order": 11,
            "placeholder": "MaiBot",
        },
    )

    def build_full_jid(self) -> str:
        """构造完整 JID（含 resource）。

        Returns:
            str: 完整的 JID 字符串。
        """
        resource = self.resource.strip() or "maibot"
        return f"{self.jid}/{resource}"

    @field_validator("host", mode="before")
    @classmethod
    def _normalize_host(cls, value: Any) -> str:
        """规范化主机地址字段。"""
        normalized_value = _normalize_string(value)
        return normalized_value or DEFAULT_XMPP_HOST

    @field_validator("port", mode="before")
    @classmethod
    def _normalize_port(cls, value: Any) -> int:
        """规范化端口字段。"""
        return _normalize_positive_int(value, DEFAULT_XMPP_PORT)

    @field_validator("jid", "password", "resource", "connection_id", "muc_nickname", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: Any) -> str:
        """规范化文本字段。"""
        return _normalize_string(value)

    @field_validator("muc_rooms", mode="before")
    @classmethod
    def _normalize_muc_rooms(cls, value: Any) -> List[str]:
        """规范化 MUC 房间列表。"""
        if not isinstance(value, list):
            return []
        cleaned: List[str] = []
        seen = set()
        for item in value:
            text = _normalize_string(item)
            if text and text not in seen:
                seen.add(text)
                cleaned.append(text)
        return cleaned

    @field_validator("heartbeat_interval", mode="before")
    @classmethod
    def _normalize_heartbeat_interval(cls, value: Any) -> float:
        """心跳间隔允许 0（禁用），负数转为 0。"""
        if isinstance(value, (int, float)):
            fval = float(value)
            return max(fval, 0.0)
        if isinstance(value, str):
            try:
                fval = float(value.strip())
                return max(fval, 0.0)
            except ValueError:
                return 0.0
        return 0.0

    @field_validator(
        "reconnect_delay_sec",
        "action_timeout_sec",
        mode="before",
    )
    @classmethod
    def _normalize_positive_float_fields(cls, value: Any, info: ValidationInfo) -> float:
        """规范化正浮点数字段（不包括心跳间隔）。"""
        default_values: Dict[str, float] = {
            "action_timeout_sec": DEFAULT_ACTION_TIMEOUT_SEC,
            "reconnect_delay_sec": DEFAULT_RECONNECT_DELAY_SEC,
        }
        return _normalize_positive_float(value, default_values[str(info.field_name)])


class XmppChatConfig(PluginConfigBase):
    """聊天名单配置。"""

    __ui_label__: ClassVar[str] = "聊天过滤"
    __ui_order__: ClassVar[int] = 2

    enable_chat_list_filter: bool = Field(
        default=True,
        description="是否启用群聊与私聊名单过滤。",
        json_schema_extra={
            "hint": "关闭后将忽略群聊名单和私聊名单，仅保留全局屏蔽用户。",
            "i18n": _schema_i18n(
                label_en="Enable chat list filter",
                label_ja="チャットリストフィルターを有効化",
                hint_en="When disabled, group and private lists are ignored; only global banned users remain.",
                hint_ja="無効にすると、グループ/個人チャットのリストを無視し、全体のブロックユーザーのみを適用します。",
            ),
            "label": "启用聊天名单过滤",
            "order": 0,
        },
    )
    show_dropped_chat_list_messages: bool = Field(
        default=False,
        description="是否显示未通过聊天名单过滤而被丢弃的消息日志。",
        json_schema_extra={
            "hint": "关闭后不会记录群聊/私聊因未通过聊天名单过滤而被丢弃的日志，默认关闭以减少刷屏。",
            "i18n": _schema_i18n(
                label_en="Show dropped chat-list logs",
                label_ja="チャットリストで破棄されたログを表示",
                hint_en="When disabled, dropped group/private chat-list logs are not recorded. Default off to reduce log noise.",
                hint_ja="無効にすると、チャットリストで破棄されたグループ/個人チャットのログを記録しません。ログの増加を抑えるため既定ではオフです。",
            ),
            "label": "显示聊天名单丢弃日志",
            "order": 1,
        },
    )
    group_list_type: Literal["whitelist", "blacklist"] = Field(
        default=DEFAULT_CHAT_LIST_TYPE,
        description="群聊名单模式。",
        json_schema_extra={
            "hint": "白名单模式只接收列表内群聊（MUC），黑名单模式则忽略列表内群聊。",
            "i18n": _schema_i18n(
                label_en="Group list mode",
                label_ja="グループリストモード",
                hint_en="Whitelist mode only accepts listed MUC rooms; blacklist mode ignores listed rooms.",
                hint_ja="ホワイトリストではリスト内の MUC ルームのみ受信し、ブラックリストではリスト内のルームを無視します。",
            ),
            "label": "群聊名单模式",
            "order": 2,
        },
    )
    group_list: List[str] = Field(
        default_factory=list,
        description="群聊名单中的 MUC JID 列表。",
        json_schema_extra={
            "hint": "例如 room@conference.example.com。",
            "i18n": _schema_i18n(
                label_en="Group list",
                label_ja="グループリスト",
                hint_en="e.g. room@conference.example.com.",
                hint_ja="例：room@conference.example.com。",
                placeholder_en="Enter MUC JID",
                placeholder_ja="MUC JID を入力",
            ),
            "label": "群聊名单",
            "order": 3,
            "placeholder": "请输入 MUC JID",
        },
    )
    private_list_type: Literal["whitelist", "blacklist"] = Field(
        default=DEFAULT_CHAT_LIST_TYPE,
        description="私聊名单模式。",
        json_schema_extra={
            "hint": "白名单模式只接收列表内 JID 的私聊，黑名单模式则忽略列表内 JID 的私聊。",
            "i18n": _schema_i18n(
                label_en="Private list mode",
                label_ja="個人チャットリストモード",
                hint_en="Whitelist mode only accepts private chats from listed JIDs; blacklist mode ignores listed JIDs.",
                hint_ja="ホワイトリストではリスト内の JID からの個人チャットのみ受信し、ブラックリストではリスト内の JID を無視します。",
            ),
            "label": "私聊名单模式",
            "order": 4,
        },
    )
    private_list: List[str] = Field(
        default_factory=list,
        description="私聊名单中的 JID 列表。",
        json_schema_extra={
            "hint": "例如 user@example.com。",
            "i18n": _schema_i18n(
                label_en="Private list",
                label_ja="個人チャットリスト",
                hint_en="e.g. user@example.com.",
                hint_ja="例：user@example.com。",
                placeholder_en="Enter JID",
                placeholder_ja="JID を入力",
            ),
            "label": "私聊名单",
            "order": 5,
            "placeholder": "请输入 JID",
        },
    )
    ban_user_id: List[str] = Field(
        default_factory=list,
        description="全局屏蔽的用户 JID 列表。",
        json_schema_extra={
            "hint": "这些用户的消息会在进入 Host 之前被直接丢弃。",
            "i18n": _schema_i18n(
                label_en="Globally blocked users",
                label_ja="全体ブロックユーザー",
                hint_en="Messages from these users are dropped before entering the Host.",
                hint_ja="これらのユーザーからのメッセージは Host に入る前に破棄されます。",
                placeholder_en="Enter JID",
                placeholder_ja="JID を入力",
            ),
            "label": "全局屏蔽用户",
            "order": 6,
            "placeholder": "请输入 JID",
        },
    )

    @field_validator("group_list_type", "private_list_type", mode="before")
    @classmethod
    def _normalize_list_types(cls, value: Any) -> Literal["whitelist", "blacklist"]:
        """规范化名单模式字段。"""
        return _normalize_list_mode(value)

    @field_validator("group_list", "private_list", "ban_user_id", mode="before")
    @classmethod
    def _normalize_id_lists(cls, value: Any) -> List[str]:
        """规范化 ID 列表字段。"""
        return _normalize_string_list(value)


class XmppFilterConfig(PluginConfigBase):
    """消息过滤配置。"""

    __ui_label__: ClassVar[str] = "消息过滤"
    __ui_order__: ClassVar[int] = 3

    ignore_self_message: bool = Field(
        default=True,
        description="是否忽略机器人自身发送的消息。",
        json_schema_extra={
            "hint": "建议保持开启，避免机器人处理自己刚刚发出的消息。",
            "i18n": _schema_i18n(
                label_en="Ignore self messages",
                label_ja="自身のメッセージを無視",
                hint_en="Recommended on to avoid the bot processing messages it just sent.",
                hint_ja="Bot が自分で送信した直後のメッセージを処理しないよう、有効のままにすることを推奨します。",
            ),
            "label": "忽略自身消息",
            "order": 0,
        },
    )
    regex_filter_enabled: bool = Field(
        default=False,
        description="是否启用正则表达式消息过滤。",
        json_schema_extra={
            "hint": "开启后将根据正则表达式规则过滤入站消息。",
            "label": "启用正则过滤",
            "order": 1,
        },
    )
    regex_filter_mode: Literal["blacklist", "whitelist"] = Field(
        default="blacklist",
        description="正则过滤模式。blacklist 匹配则丢弃，whitelist 仅放行匹配的消息。",
        json_schema_extra={
            "hint": "黑名单模式下匹配正则的消息会被丢弃；白名单模式下仅匹配正则的消息会被放行。",
            "label": "正则过滤模式",
            "order": 2,
        },
    )
    regex_filter_patterns: List[str] = Field(
        default_factory=list,
        description="正则表达式列表，支持 Python re 模块语法。",
        json_schema_extra={
            "hint": "每条规则为一个 Python 正则表达式，消息文本将逐条匹配。",
            "label": "正则表达式列表",
            "order": 3,
            "placeholder": r"例如：^广告.*|spam",
        },
    )
    regex_filter_show_dropped: bool = Field(
        default=False,
        description="是否显示未通过正则过滤而被丢弃的消息日志。",
        json_schema_extra={
            "hint": "关闭后不会记录因正则过滤而被丢弃的日志，默认关闭以减少刷屏。",
            "label": "显示正则过滤丢弃日志",
            "order": 4,
        },
    )

    @field_validator("regex_filter_mode", mode="before")
    @classmethod
    def _normalize_regex_filter_mode(cls, value: Any) -> Literal["whitelist", "blacklist"]:
        """规范化正则过滤模式字段。"""
        normalized_value = _normalize_string(value)
        if normalized_value == "whitelist":
            return "whitelist"
        if normalized_value not in ("whitelist", "blacklist"):
            LOGGER.warning(f"无效的 regex_filter_mode 值 '{value}'，已回退到 'blacklist'")
        return "blacklist"

    @field_validator("regex_filter_patterns", mode="before")
    @classmethod
    def _normalize_regex_filter_patterns(cls, value: Any) -> List[str]:
        """规范化正则表达式列表字段。"""
        return _normalize_string_list(value)


class XmppPluginSettings(PluginConfigBase):
    """XMPP 插件完整配置。"""

    plugin: XmppPluginOptions = Field(default_factory=XmppPluginOptions)
    xmpp_server: XmppServerConfig = Field(default_factory=XmppServerConfig)
    chat: XmppChatConfig = Field(default_factory=XmppChatConfig)
    filters: XmppFilterConfig = Field(default_factory=XmppFilterConfig)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_config(cls, raw_config: Any) -> Dict[str, Any]:
        """将旧版配置结构迁移为当前配置模型。"""
        raw_mapping = _as_mapping(raw_config)
        plugin_section = _as_mapping(raw_mapping.get("plugin"))
        server_section = _as_mapping(raw_mapping.get("xmpp_server"))
        chat_section = _as_mapping(raw_mapping.get("chat"))
        filters_section = _as_mapping(raw_mapping.get("filters"))

        return {
            "chat": chat_section,
            "filters": filters_section,
            "xmpp_server": server_section,
            "plugin": plugin_section,
        }

    @classmethod
    def from_mapping(cls, raw_config: Mapping[str, Any], logger: Any) -> "XmppPluginSettings":
        """从 Runner 注入的原始配置字典解析插件配置。"""
        del logger
        return cls.model_validate(dict(raw_config))

    def should_connect(self) -> bool:
        """判断当前配置下是否应当启动连接。"""
        return self.plugin.should_connect()

    def validate_runtime_config(self, logger: Any) -> bool:
        """校验当前配置是否满足启动连接的前提条件。"""
        config_version = self.plugin.config_version
        if not config_version:
            logger.error(f"XMPP 适配器配置缺少 plugin.config_version，当前插件要求版本 {SUPPORTED_CONFIG_VERSION}")
            return False

        if config_version != SUPPORTED_CONFIG_VERSION:
            logger.error(
                f"XMPP 适配器配置版本不兼容: 当前为 {config_version}，当前插件要求 {SUPPORTED_CONFIG_VERSION}"
            )
            return False

        if not self.xmpp_server.jid:
            logger.warning("XMPP 适配器已启用，但 xmpp_server.jid 为空")
            return False

        if not self.xmpp_server.password:
            logger.warning("XMPP 适配器已启用，但 xmpp_server.password 为空")
            return False

        if not self.xmpp_server.host:
            logger.warning("XMPP 适配器已启用，但 xmpp_server.host 为空")
            return False

        if self.xmpp_server.port <= 0:
            logger.warning("XMPP 适配器已启用，但 xmpp_server.port 不是正整数")
            return False

        return True


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _as_mapping(value: Any) -> Dict[str, Any]:
    """将任意值安全转换为字典。"""
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_list_mode(value: Any) -> Literal["whitelist", "blacklist"]:
    """规范化名单模式字符串。"""
    normalized_value = _normalize_string(value)
    if normalized_value == "whitelist":
        return "whitelist"
    if normalized_value == "blacklist":
        return "blacklist"
    return DEFAULT_CHAT_LIST_TYPE


def _normalize_positive_float(value: Any, default: float) -> float:
    """规范化正浮点数配置值。"""
    if isinstance(value, (int, float)) and float(value) > 0:
        return float(value)

    if isinstance(value, str):
        try:
            parsed_value = float(value.strip())
        except ValueError:
            return default
        if parsed_value > 0:
            return parsed_value

    return default


def _normalize_positive_int(value: Any, default: int) -> int:
    """规范化正整数配置值。"""
    if isinstance(value, int) and value > 0:
        return value

    if isinstance(value, str):
        normalized_value = value.strip()
        if normalized_value.isdigit():
            parsed_value = int(normalized_value)
            if parsed_value > 0:
                return parsed_value

    return default


def _normalize_string(value: Any) -> str:
    """规范化字符串配置值。"""
    return "" if value is None else str(value).strip()


def _normalize_string_list(value: Any) -> List[str]:
    """规范化字符串列表配置值。"""
    if not isinstance(value, list):
        return []

    normalized_values: List[str] = []
    seen_values = set()
    for item in value:
        item_text = _normalize_string(item)
        if not item_text or item_text in seen_values:
            continue
        seen_values.add(item_text)
        normalized_values.append(item_text)
    return normalized_values