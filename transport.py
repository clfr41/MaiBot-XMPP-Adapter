"""XMPP 传输层。

基于 slixmpp 库提供 XMPP C2S 连接能力。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, Optional

import asyncio
import contextlib
import ssl

from .config import XmppServerConfig

try:
    import slixmpp

    SLIXMPP_AVAILABLE = True
except ImportError:
    slixmpp = None  # type: ignore[assignment]
    SLIXMPP_AVAILABLE = False


class XmppTransportClient:
    """XMPP 传输层客户端。

    封装 slixmpp，提供与 XMPP 服务器的连接、消息收发与生命周期管理。
    """

    def __init__(
        self,
        logger: Any,
        on_connection_opened: Callable[[], Coroutine[Any, Any, None]],
        on_connection_closed: Callable[[], Coroutine[Any, Any, None]],
        on_payload: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
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

    @classmethod
    def is_available(cls) -> bool:
        return SLIXMPP_AVAILABLE

    def configure(self, server_config: XmppServerConfig) -> None:
        self._server_config = server_config
        self._bare_jid = server_config.jid
        self._full_jid = server_config.build_full_jid()

    @property
    def bare_jid(self) -> str:
        return self._bare_jid

    @property
    def full_jid(self) -> str:
        return self._full_jid

    async def start(self) -> None:
        if not self.is_available():
            raise RuntimeError("XMPP 适配器依赖 slixmpp，但当前环境未安装该依赖")
        if self._server_config is None:
            raise RuntimeError("XMPP 适配器尚未配置 xmpp_server")
        if self._connection_task is not None and not self._connection_task.done():
            return

        self._stop_requested = False
        self._connection_task = asyncio.create_task(
            self._connection_loop(), name="xmpp_adapter.connection"
        )

    async def stop(self) -> None:
        self._stop_requested = True
        connection_task = self._connection_task
        self._connection_task = None

        if self._xmpp_client is not None:
            with contextlib.suppress(Exception):
                self._xmpp_client.disconnect()
            self._xmpp_client = None

        if connection_task is not None:
            connection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connection_task

        await self._notify_connection_closed()

    async def send_message(self, to_jid: str, body: str, message_type: str = "chat") -> Dict[str, Any]:
        xmpp = self._xmpp_client
        if xmpp is None:
            raise RuntimeError("XMPP 未连接")

        try:
            xmpp.send_message(mto=to_jid, mbody=body, mtype=message_type)
            return {"success": True, "external_message_id": None}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def send_presence(self, status: str = "", show: str = "") -> Dict[str, Any]:
        xmpp = self._xmpp_client
        if xmpp is None:
            raise RuntimeError("XMPP 未连接")

        try:
            xmpp.send_presence(pstatus=status, pshow=show)
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def join_muc(self, room_jid: str, nickname: str = "") -> Dict[str, Any]:
        xmpp = self._xmpp_client
        if xmpp is None:
            raise RuntimeError("XMPP 未连接")

        try:
            nick = nickname or (self._bare_jid.split("@")[0] if "@" in self._bare_jid else self._bare_jid)
            muc_plugin = xmpp.plugin["xep_0045"]
            await muc_plugin.join_muc(room_jid, nick)
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _build_xmpp_client(self) -> Any:
        assert slixmpp is not None

        class _AdapterXmppClient(slixmpp.ClientXMPP):
            def __init__(self_innner, jid: str, password: str, transport: "XmppTransportClient") -> None:
                super().__init__(jid, password)
                self_innner._adapter_transport = transport
                self_innner.register_plugin("xep_0030")
                self_innner.register_plugin("xep_0045")
                self_innner.register_plugin("xep_0199")

                self_innner.add_event_handler("session_start", self_innner._on_session_start)
                self_innner.add_event_handler("message", self_innner._on_message)
                self_innner.add_event_handler("disconnected", self_innner._on_disconnected)
                self_innner.add_event_handler("failed_auth", self_innner._on_failed_auth)
                # 监听 presence 和 iq，确保心跳能基于所有入站流量刷新
                self_innner.add_event_handler("presence", self_innner._on_presence_or_iq)
                self_innner.add_event_handler("iq", self_innner._on_presence_or_iq)

            async def _on_session_start(self_innner, event: Any) -> None:
                del event
                transport_obj = self_innner._adapter_transport
                transport_obj._logger.info(
                    f"XMPP 会话已建立: {transport_obj._full_jid}"
                )
                self_innner.send_presence()
                await transport_obj._notify_connection_opened()

            def _on_message(self_innner, msg: Any) -> None:
                transport_obj = self_innner._adapter_transport
                payload = {
                    "from_jid": str(msg["from"]),
                    "to_jid": str(msg["to"]),
                    "type": str(msg["type"]),
                    "body": str(msg["body"]) if msg["body"] else "",
                    "id": str(msg["id"]) if msg["id"] else "",
                    "raw": msg,
                }
                asyncio.create_task(
                    transport_obj._on_payload(payload),
                    name="xmpp_adapter.payload",
                )

            def _on_presence_or_iq(self_innner, stanza: Any) -> None:
                """统一处理 presence 和 iq，只负责刷新心跳，不进入业务流。"""
                transport_obj = self_innner._adapter_transport
                payload = {
                    "from_jid": str(stanza["from"]),
                    "to_jid": str(stanza["to"]),
                    "type": str(stanza["type"]),
                    "body": "",
                    "id": str(stanza["id"]) if stanza["id"] else "",
                    "raw": stanza,
                }
                asyncio.create_task(
                    transport_obj._on_payload(payload),
                    name="xmpp_adapter.heartbeat",
                )

            def _on_disconnected(self_innner, event: Any) -> None:
                del event
                transport_obj = self_innner._adapter_transport
                asyncio.create_task(
                    transport_obj._notify_connection_closed(),
                    name="xmpp_adapter.disconnected",
                )

            def _on_failed_auth(self_innner, event: Any) -> None:
                del event
                transport_obj = self_innner._adapter_transport
                transport_obj._logger.error(
                    f"XMPP 认证失败: {transport_obj._full_jid}"
                )

        return _AdapterXmppClient(self._full_jid, self._server_config.password, self)

    async def _connection_loop(self) -> None:
        while not self._stop_requested:
            server_config = self._server_config
            if server_config is None:
                return

            self._logger.info(
                f"XMPP 适配器开始连接: {server_config.host}:{server_config.port} "
                f"（JID: {server_config.jid}, TLS: {server_config.use_tls}）"
            )

            try:
                xmpp = self._build_xmpp_client()
                self._xmpp_client = xmpp

                # ── TLS 策略 ────────────────────────────────────
                if not server_config.use_tls:
                    # 明文模式：彻底关闭 TLS
                    xmpp.use_ssl = False
                    if hasattr(xmpp, "use_tls"):
                        xmpp.use_tls = False
                elif server_config.port == 5223:
                    # 5223 是旧式直接 TLS 端口（客户端先握手再发 XML）
                    xmpp.use_ssl = True
                # else: 5222 等标准端口，slixmpp 默认走 STARTTLS，
                # 什么都不设置即可。

                # 跳过自签名证书验证（测试环境）
                _ssl_ctx = ssl.create_default_context()
                _ssl_ctx.check_hostname = False
                _ssl_ctx.verify_mode = ssl.CERT_NONE
                xmpp.ssl_context = _ssl_ctx
                # ──────────────────────────────────────────────────

                await xmpp.connect(server_config.host, server_config.port)

                # 挂起直到连接断开
                await xmpp.disconnected

                if not self._connection_active:
                    self._logger.warning(
                        "XMPP 连接未完成会话建立就断开，可能认证失败或服务器拒绝连接"
                    )

            except asyncio.CancelledError:
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
                break

            await asyncio.sleep(server_config.reconnect_delay_sec)

    async def _notify_connection_opened(self) -> None:
        if self._connection_active:
            return
        self._connection_active = True
        try:
            await self._on_connection_opened()
        except Exception as exc:
            self._logger.warning(f"XMPP 适配器连接建立回调失败: {exc}")

    async def _notify_connection_closed(self) -> None:
        if not self._connection_active:
            return
        self._connection_active = False
        try:
            await self._on_connection_closed()
        except Exception as exc:
            self._logger.warning(f"XMPP 适配器断连回调失败: {exc}")

    def _build_reconnect_hint(self, server_config: XmppServerConfig) -> str:
        if self._stop_requested:
            return ""
        return f"；将在 {server_config.reconnect_delay_sec:g} 秒后重连"