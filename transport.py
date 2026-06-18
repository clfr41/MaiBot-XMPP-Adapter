"""XMPP 传输层。

基于 slixmpp 库提供 XMPP C2S 连接能力，负责连接生命周期管理、
原始 stanza 收发以及上层回调通知。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine, Optional

import asyncio
import contextlib
import ssl
import weakref

from .config import XmppServerConfig

try:
    import slixmpp

    SLIXMPP_AVAILABLE = True
except ImportError:
    slixmpp = None  # type: ignore[assignment]
    SLIXMPP_AVAILABLE = False

# 后台任务静默异常日志前缀
_TASK_EXCEPTION_PREFIX = "XMPP 后台任务异常"


# ---------------------------------------------------------------------------
# 内部 XMPP 客户端（仅在 slixmpp 可用时定义）
# ---------------------------------------------------------------------------

if SLIXMPP_AVAILABLE:

    class _AdapterXmppClient(slixmpp.ClientXMPP):
        """内部 XMPP 客户端，封装会话事件与 stanza 分发。

        继承 slixmpp.ClientXMPP，注册必要插件与事件处理器，
        将 XMPP 事件转换为统一载荷后通过回调通知上层。
        """

        def __init__(
            self,
            jid: str,
            password: str,
            transport: "XmppTransportClient",
        ) -> None:
            super().__init__(jid, password)
            self._adapter_transport = transport
            logger = transport._logger

            # 注册基础插件
            self.register_plugin("xep_0030")  # Service Discovery
            self.register_plugin("xep_0045")  # Multi-User Chat (MUC)
            self.register_plugin("xep_0199")  # XMPP Ping
            logger.debug("XMPP 客户端插件注册完成")

            # 注册事件处理器
            self.add_event_handler("session_start", self._on_session_start)
            self.add_event_handler("message", self._on_message)
            self.add_event_handler("groupchat_message", self._on_groupchat_message)
            self.add_event_handler("muc::*::got_online", self._on_muc_presence)
            self.add_event_handler("disconnected", self._on_disconnected)
            self.add_event_handler("failed_auth", self._on_failed_auth)
            # 注意：presence 和 iq stanza 不是消息，不注册 payload 处理器。
            # 它们不应进入消息处理管道，否则会导致上层收到空消息。
            self.add_event_handler("presence", self._on_non_message_stanza)
            self.add_event_handler("iq", self._on_non_message_stanza)
            logger.debug("XMPP 客户端事件处理器注册完成")

        # ---- 事件处理 ----

        async def _on_session_start(self, event: Any) -> None:
            """会话建立后的初始化逻辑。"""
            del event
            transport = self._adapter_transport
            logger = transport._logger
            logger.info(f"XMPP 会话已建立: {transport._full_jid}")
            self.send_presence()
            await transport._notify_connection_opened()
            await self._auto_join_muc_rooms(transport)
            logger.debug("XMPP 会话初始化完成")

        async def _auto_join_muc_rooms(self, transport: "XmppTransportClient") -> None:
            """根据配置自动加入 MUC 房间。"""
            config = transport._server_config
            if config is None:
                transport._logger.debug("MUC 自动加入: 服务器配置为空，跳过")
                return

            muc_rooms = getattr(config, "muc_rooms", None) or []
            if not muc_rooms:
                transport._logger.debug("未配置 MUC 房间，跳过自动加入")
                return

            muc_nick = (getattr(config, "muc_nickname", "") or "").strip()
            if not muc_nick:
                bare = getattr(config, "jid", "")
                muc_nick = bare.split("@")[0] if "@" in bare else "MaiBot"
                transport._logger.debug(f"MUC 昵称未配置，自动使用 JID 本地部分: {muc_nick}")

            muc_plugin = self.plugin["xep_0045"]
            if muc_plugin is None:
                transport._logger.error("xep_0045 插件不可用，无法加入 MUC 房间")
                return

            total = len(muc_rooms)
            transport._logger.debug(f"MUC 自动加入: 共 {total} 个房间，昵称 {muc_nick}")
            for idx, room in enumerate(muc_rooms, 1):
                room = str(room).strip()
                if not room:
                    transport._logger.debug(f"MUC 自动加入: 第 {idx} 个房间 JID 为空，跳过")
                    continue
                try:
                    transport._logger.info(f"正在加入 MUC 房间 [{idx}/{total}]: {room} (昵称: {muc_nick})")
                    await muc_plugin.join_muc(room, muc_nick)
                    transport._logger.info(f"已自动加入 MUC 房间: {room}")
                except Exception as exc:
                    transport._logger.error(f"加入 MUC 房间 {room} 失败: {exc}")

        def _on_message(self, msg: Any) -> None:
            """处理入站消息（私聊/群聊）。"""
            transport = self._adapter_transport
            msg_type = str(msg["type"])
            msg_id = str(msg["id"]) if msg["id"] else "(无 ID)"
            transport._logger.debug(
                f"收到 XMPP 消息: type={msg_type} id={msg_id} "
                f"from={msg['from']} to={msg['to']}"
            )
            payload = {
                "from_jid": str(msg["from"]),
                "to_jid": str(msg["to"]),
                "type": msg_type,
                "body": str(msg["body"]) if msg["body"] else "",
                "id": msg_id if msg_id != "(无 ID)" else "",
                "raw": msg,
            }
            transport._safe_create_task(
                transport._on_payload(payload),
                name="xmpp_adapter.on_message",
                debug_info=f"msg_type={msg_type} from={payload['from_jid']}",
            )

        def _on_groupchat_message(self, msg: Any) -> None:
            """群聊消息直接复用普通消息处理。"""
            transport = self._adapter_transport
            transport._logger.debug(
                f"收到 XMPP 群聊消息: from={msg['from']} id={msg['id']}"
            )
            self._on_message(msg)

        def _on_muc_presence(self, presence: Any) -> None:
            """MUC 出席事件（仅记录日志）。"""
            transport = self._adapter_transport
            ptype = presence.get("type")
            pfrom = presence.get("from")
            transport._logger.debug(
                f"MUC 出席事件: from={pfrom} type={ptype}"
            )

        def _on_non_message_stanza(self, stanza: Any) -> None:
            """处理非消息类 stanza（presence/iq），仅记录日志，不进入消息管道。"""
            transport = self._adapter_transport
            stanza_type = str(stanza["type"])
            stanza_from = str(stanza["from"])
            stanza_id = str(stanza["id"]) if stanza["id"] else "(无 ID)"
            transport._logger.debug(
                f"收到非消息 stanza: type={stanza_type} id={stanza_id} from={stanza_from} — 已忽略（非消息）"
            )
            # 不发送 payload 到 _on_payload，防止空消息穿透到上层消息处理器

        def _on_disconnected(self, event: Any) -> None:
            """处理连接断开事件。"""
            del event
            transport = self._adapter_transport
            transport._logger.debug("XMPP 连接断开事件触发，通知上层")
            transport._safe_create_task(
                transport._notify_connection_closed(),
                name="xmpp_adapter.on_disconnected",
                debug_info="transport disconnected",
            )

        def _on_failed_auth(self, event: Any) -> None:
            """处理认证失败事件。"""
            del event
            transport = self._adapter_transport
            transport._logger.error(f"XMPP 认证失败: {transport._full_jid}")


# ---------------------------------------------------------------------------
# 传输层客户端
# ---------------------------------------------------------------------------


class XmppTransportClient:
    """XMPP 传输层客户端。

    封装基于 slixmpp 的 XMPP C2S 连接，提供消息收发、Presence 发送、
    MUC 加入等基本操作，并通过回调通知上层连接状态变化。

    使用前必须调用 ``configure()`` 进行参数配置，然后调用 ``start()``
    启动连接。连接断开后会自动按配置的时间间隔重连。
    """

    def __init__(
        self,
        logger: Any,
        on_connection_opened: Callable[[], Coroutine[Any, Any, None]],
        on_connection_closed: Callable[[], Coroutine[Any, Any, None]],
        on_payload: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """初始化传输层客户端。

        Args:
            logger: 日志对象。
            on_connection_opened: 连接建立回调（在会话就绪后调用）。
            on_connection_closed: 连接断开回调。
            on_payload: 收到 XMPP stanza 时的回调，接收统一载荷字典。
        """
        self._logger = logger
        self._on_connection_opened = on_connection_opened
        self._on_connection_closed = on_connection_closed
        self._on_payload = on_payload
        self._server_config: Optional[XmppServerConfig] = None
        self._xmpp_client: Any = None
        self._stop_requested: bool = False
        self._connection_active: bool = False
        self._connection_task: Optional[asyncio.Task[None]] = None
        self._bare_jid: str = ""
        self._full_jid: str = ""
        # 密码副本，仅在该传输层实例生命周期内驻留；stop() 时主动清零
        self._password: str = ""

        # 跟踪所有通过 _safe_create_task 创建的后台任务，
        # 以便在 stop() 时统一清理
        self._pending_tasks: set[asyncio.Task[None]] = set()
        # 任务计数器，用于 debug 标识
        self._task_counter: int = 0

        logger.debug("XmppTransportClient 初始化完成")

    # ---- 公共接口 ----

    @classmethod
    def is_available(cls) -> bool:
        """检查 slixmpp 库是否可用。

        Returns:
            若 slixmpp 已安装则返回 ``True``。
        """
        return SLIXMPP_AVAILABLE

    def configure(self, server_config: XmppServerConfig) -> None:
        """配置服务器连接参数。

        必须在 ``start()`` 之前调用。

        Args:
            server_config: XMPP 服务器连接配置（主机、端口、JID、密码等）。
        """
        self._server_config = server_config
        self._bare_jid = server_config.jid
        self._full_jid = server_config.build_full_jid()
        # 复制密码到传输层本地，避免 config 模型在后续生命周期中持留敏感字段
        self._password = server_config.password
        self._logger.debug(f"传输层已配置: bare_jid={self._bare_jid} full_jid={self._full_jid}")

    @property
    def bare_jid(self) -> str:
        """当前机器人的 bare JID（不含 resource）。"""
        return self._bare_jid

    @property
    def full_jid(self) -> str:
        """当前机器人的完整 JID（含 resource）。"""
        return self._full_jid

    async def start(self) -> None:
        """启动 XMPP 连接。

        创建后台连接任务，该任务会自动处理重连逻辑。
        若已有连接任务正在运行则跳过。

        Raises:
            RuntimeError: slixmpp 未安装或尚未调用 ``configure()``。
        """
        if not self.is_available():
            raise RuntimeError("XMPP 适配器依赖 slixmpp，但当前环境未安装该依赖")
        if self._server_config is None:
            raise RuntimeError("XMPP 适配器尚未配置 xmpp_server")
        if self._connection_task is not None and not self._connection_task.done():
            self._logger.debug("已有连接任务正在运行，跳过重复启动")
            return

        self._stop_requested = False
        self._connection_task = asyncio.create_task(
            self._connection_loop(),
            name="xmpp_adapter.connection",
        )
        self._logger.debug("连接任务已创建")

    async def stop(self) -> None:
        """停止 XMPP 连接并清理资源。

        断开当前连接、取消后台任务，并通知上层连接已关闭。
        幂等操作，可多次调用。
        """
        self._logger.debug("XmppTransportClient.stop() 开始清理")
        self._stop_requested = True

        # 1) 断开主动 XMPP 连接
        if self._xmpp_client is not None:
            with contextlib.suppress(Exception):
                self._logger.debug("正在断开 XMPP 客户端连接")
                self._xmpp_client.disconnect()
            self._xmpp_client = None

        # 2) 取消连接主循环
        connection_task = self._connection_task
        if connection_task is not None and not connection_task.done():
            self._logger.debug("正在取消连接主循环任务")
            connection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connection_task
        self._connection_task = None

        # 3) 清理所有未完成的 stanza 处理任务
        await self._cancel_pending_tasks()

        # 4) 通知上层连接已关闭（防止重复通知由内部守卫处理）
        await self._notify_connection_closed()

        # 5) 清零传输层持有的密码副本
        self._password = ""

        self._logger.debug("XmppTransportClient.stop() 清理完成")

    async def _cancel_pending_tasks(self) -> None:
        """取消并等待所有未完成的后台处理任务。"""
        pending = list(self._pending_tasks)
        if not pending:
            self._logger.debug("无待清理的后台任务")
            return

        count = len(pending)
        self._logger.debug(f"正在清理 {count} 个未完成的后台任务")
        for task in pending:
            if not task.done():
                task.cancel()

        if pending:
            results = await asyncio.gather(*pending, return_exceptions=True)
            cancelled_count = sum(
                1 for r in results if isinstance(r, asyncio.CancelledError)
            )
            self._logger.debug(
                f"后台任务清理完毕: 共 {count} 个，"
                f"其中 {cancelled_count} 个已取消，"
                f"{count - cancelled_count} 个已完成"
            )

        self._pending_tasks.clear()

    async def send_message(
        self,
        to_jid: str,
        body: str,
        message_type: str = "chat",
    ) -> dict[str, Any]:
        """发送 XMPP 消息。

        Args:
            to_jid: 目标 JID。
            body: 消息正文。
            message_type: 消息类型，``"chat"`` 或 ``"groupchat"``。

        Returns:
            包含 ``success`` 和可选的 ``external_message_id`` / ``error`` 的字典。

        Raises:
            RuntimeError: XMPP 尚未连接。
        """
        xmpp = self._xmpp_client
        if xmpp is None:
            self._logger.warning(f"XMPP 未连接，无法发送消息到 {to_jid}")
            raise RuntimeError("XMPP 未连接")

        try:
            xmpp.send_message(mto=to_jid, mbody=body, mtype=message_type)
            self._logger.debug(f"XMPP 消息发送成功: type={message_type} to={to_jid} body_len={len(body)}")
            return {"success": True, "external_message_id": None}
        except Exception as exc:
            self._logger.error(f"XMPP 消息发送失败 (to={to_jid}): {exc}")
            return {"success": False, "error": str(exc)}

    async def send_presence(self, status: str = "", show: str = "") -> dict[str, Any]:
        """发送 XMPP Presence。

        Args:
            status: 状态文本（如 "在线"、"忙碌"）。
            show: 在线状态枚举值，可选 ``away`` / ``chat`` / ``dnd`` / ``xa``。

        Returns:
            包含 ``success`` 和可选的 ``error`` 的字典。

        Raises:
            RuntimeError: XMPP 尚未连接。
        """
        xmpp = self._xmpp_client
        if xmpp is None:
            self._logger.warning("XMPP 未连接，无法发送 presence")
            raise RuntimeError("XMPP 未连接")

        try:
            xmpp.send_presence(pstatus=status, pshow=show)
            self._logger.debug(f"XMPP presence 发送成功: status={status!r} show={show!r}")
            return {"success": True}
        except Exception as exc:
            self._logger.error(f"XMPP presence 发送失败: {exc}")
            return {"success": False, "error": str(exc)}

    async def join_muc(self, room_jid: str, nickname: str = "") -> dict[str, Any]:
        """加入 MUC 房间。

        Args:
            room_jid: 房间 JID（如 room@conference.example.com）。
            nickname: 在房间中使用的昵称；为空时自动使用 JID 本地部分。

        Returns:
            包含 ``success`` 和可选的 ``error`` 的字典。

        Raises:
            RuntimeError: XMPP 尚未连接。
        """
        xmpp = self._xmpp_client
        if xmpp is None:
            self._logger.warning(f"XMPP 未连接，无法加入 MUC 房间 {room_jid}")
            raise RuntimeError("XMPP 未连接")

        try:
            nick = nickname or (
                self._bare_jid.split("@")[0] if "@" in self._bare_jid else self._bare_jid
            )
            muc_plugin = xmpp.plugin["xep_0045"]
            self._logger.info(f"正在加入 MUC 房间: {room_jid} (昵称: {nick})")
            await muc_plugin.join_muc(room_jid, nick)
            self._logger.info(f"MUC 房间加入成功: {room_jid}")
            return {"success": True}
        except Exception as exc:
            self._logger.error(f"加入 MUC 房间 {room_jid} 失败: {exc}")
            return {"success": False, "error": str(exc)}

    # ---- 内部方法 ----

    def _safe_create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str = "xmpp_adapter.task",
        debug_info: str = "",
    ) -> asyncio.Task[Any]:
        """安全地创建后台任务，自动处理异常日志和生命周期追踪。

        创建的任务会被记录在 ``_pending_tasks`` 集合中，
        任务完成后自动移除。在 ``stop()`` 时统一清理。

        Args:
            coro: 要执行的协程。
            name: 任务名称。
            debug_info: 调试辅助信息，用于日志标识（可选）。

        Returns:
            asyncio.Task: 创建的任务对象。
        """
        self._task_counter += 1
        task_id = self._task_counter
        task_name = f"{name}.{task_id}"

        async def _wrapped() -> None:
            try:
                await coro
            except asyncio.CancelledError:
                self._logger.debug(f"后台任务 {task_name} 被取消 [{debug_info}]")
                raise
            except Exception:
                self._logger.exception(
                    f"{_TASK_EXCEPTION_PREFIX}: {task_name} [{debug_info}]"
                )

        task = asyncio.create_task(_wrapped(), name=task_name)
        self._pending_tasks.add(task)
        self._logger.debug(f"创建后台任务 {task_name} [{debug_info}]")

        # 任务完成时自动从集合中移除
        task.add_done_callback(self._pending_tasks.discard)

        return task

    def _build_xmpp_client(self) -> Any:
        """创建并返回 XMPP 客户端实例。

        Returns:
            ``_AdapterXmppClient`` 实例（仅在 slixmpp 可用时）或 ``None``。
        """
        assert slixmpp is not None, "slixmpp 未安装但仍尝试构建客户端"
        assert self._server_config is not None, "尚未调用 configure()"
        return _AdapterXmppClient(
            self._full_jid,
            self._password,
            self,
        )

    def _configure_tls(self, xmpp: Any, config: XmppServerConfig) -> None:
        """配置 TLS/SSL 连接参数。

        slixmpp 支持两种加密模式：
        - STARTTLS (use_tls=True, 端口 5222)：连接建立后升级为 TLS，默认行为
        - 旧式 SSL (use_ssl=True, 端口 5223)：连接建立前即加密

        Args:
            xmpp: slixmpp 客户端实例。
            config: 当前服务器配置。
        """
        if not config.use_tls:
            # 用户显式关闭 TLS → 纯文本连接
            if hasattr(xmpp, "use_tls"):
                xmpp.use_tls = False
            xmpp.ssl_context = None
            self._logger.warning(
                "TLS 已禁用，XMPP 连接将以明文传输，"
                "这存在严重的安全风险，仅建议在隔离的本地网络中使用"
            )
            return

        # TLS 启用
        # slixmpp 默认启用 STARTTLS，所以我们不需要显式设置 use_tls=True
        # 端口 5223 使用旧式 SSL，需要显式设置 use_ssl
        if config.port == 5223:
            xmpp.use_ssl = True
            self._logger.debug("使用旧式 SSL 连接 (端口 5223)")

        ssl_ctx = ssl.create_default_context()
        if config.tls_verify:
            # 严格验证模式 —— 生产环境使用
            # 需要服务器的 CA 证书在系统信任链中
            ssl_ctx.check_hostname = True
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
            self._logger.info(
                "TLS 证书验证已启用，将严格验证服务器证书有效性和主机名"
            )
        else:
            # 跳过验证模式 —— 测试环境自签名证书
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            self._logger.warning(
                "TLS 已启用但跳过证书验证 (CERT_NONE)——"
                "这对中间人攻击没有防护，仅适用于测试环境。"
                "生产环境请设置 tls_verify = true"
            )
        xmpp.ssl_context = ssl_ctx

    async def _connection_loop(self) -> None:
        """连接主循环，包含自动重连逻辑。

        循环在 ``_stop_requested`` 为 ``True`` 时退出。
        """
        while not self._stop_requested:
            server_config = self._server_config
            if server_config is None:
                self._logger.warning("连接循环退出: 服务器配置为空")
                return

            self._logger.info(
                f"XMPP 适配器开始连接: {server_config.host}:{server_config.port} "
                f"(JID: {server_config.jid}, TLS: {server_config.use_tls})"
            )

            try:
                xmpp = self._build_xmpp_client()
                self._xmpp_client = xmpp

                self._configure_tls(xmpp, server_config)
                self._logger.debug(
                    f"正在连接 {server_config.host}:{server_config.port}..."
                )

                connected = await xmpp.connect(
                    server_config.host,
                    server_config.port,
                )
                self._logger.debug(f"xmpp.connect() 返回: {connected}")

                # 等待连接断开（或被取消）
                await xmpp.disconnected

                if not self._connection_active:
                    self._logger.warning(
                        "XMPP 连接未完成会话建立就断开，"
                        "可能认证失败或服务器拒绝连接"
                    )

            except asyncio.CancelledError:
                self._logger.debug("连接循环被取消")
                raise
            except Exception as exc:
                self._logger.warning(
                    f"XMPP 适配器连接失败: {exc}"
                    f"{self._build_reconnect_hint(server_config)}"
                )
            finally:
                self._xmpp_client = None
                await self._notify_connection_closed()

            if self._stop_requested:
                self._logger.debug("连接循环退出: stop_requested 为 True")
                break

            wait_sec = server_config.reconnect_delay_sec
            self._logger.debug(f"将在 {wait_sec:g} 秒后重连...")
            await asyncio.sleep(wait_sec)

    async def _notify_connection_opened(self) -> None:
        """通知上层连接已建立（仅首次触发）。"""
        if self._connection_active:
            self._logger.debug("连接打开通知跳过: 已处于活跃状态")
            return
        self._connection_active = True
        self._logger.info("传输层连接已就绪，通知上层")
        try:
            await self._on_connection_opened()
        except Exception as exc:
            self._logger.warning(f"XMPP 连接建立回调失败: {exc}")

    async def _notify_connection_closed(self) -> None:
        """通知上层连接已断开（仅当连接曾活跃时触发）。"""
        if not self._connection_active:
            return
        self._connection_active = False
        self._logger.info("传输层连接已断开，通知上层")
        try:
            await self._on_connection_closed()
        except Exception as exc:
            self._logger.warning(f"XMPP 断连回调失败: {exc}")

    def _build_reconnect_hint(self, server_config: XmppServerConfig) -> str:
        """构造重连提示文本。"""
        if self._stop_requested:
            return ""
        return f"；将在 {server_config.reconnect_delay_sec:g} 秒后重连"
