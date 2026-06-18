"""XMPP 消息网关运行时状态管理。"""

from typing import Any, Optional, Protocol

from .config import XmppServerConfig


class _GatewayCapabilityProtocol(Protocol):
    """消息网关能力代理协议。"""

    async def update_state(
        self,
        gateway_name: str,
        *,
        ready: bool,
        platform: str = "",
        account_id: str = "",
        scope: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """向 Host 上报消息网关运行时状态。"""
        ...


class XmppRuntimeStateManager:
    """XMPP 消息网关路由状态上报器。"""

    def __init__(
        self,
        gateway_capability: _GatewayCapabilityProtocol,
        logger: Any,
        gateway_name: str,
    ) -> None:
        """初始化运行时状态管理器。

        Args:
            gateway_capability: SDK 提供的消息网关能力对象。
            logger: 插件日志对象。
            gateway_name: 当前 XMPP 消息网关组件名称。
        """

        self._gateway_capability = gateway_capability
        self._gateway_name = gateway_name
        self._logger = logger
        self._runtime_state_connected: bool = False
        self._reported_account_id: Optional[str] = None
        self._reported_scope: Optional[str] = None

    async def report_connected(self, account_id: str, server_config: XmppServerConfig) -> bool:
        """向 Host 上报当前消息网关连接已就绪。

        Args:
            account_id: 当前 XMPP 连接对应的机器人 JID。
            server_config: 当前生效的 XMPP 服务端配置。

        Returns:
            bool: 若 Host 接受了运行时状态更新，则返回 ``True``。
        """

        normalized_account_id = str(account_id).strip()
        if not normalized_account_id:
            self._logger.warning("runtime_state.report_connected: account_id 为空")
            return False

        scope = server_config.connection_id or None
        if (
            self._runtime_state_connected
            and self._reported_account_id == normalized_account_id
            and self._reported_scope == scope
        ):
            self._logger.debug(
                f"runtime_state 重复上报跳过: account={normalized_account_id} "
                f"scope={scope or '*'}"
            )
            return True

        self._logger.debug(
            f"runtime_state 上报连接就绪: account={normalized_account_id} "
            f"scope={scope or '*'}"
        )
        accepted = False
        try:
            accepted = await self._gateway_capability.update_state(
                gateway_name=self._gateway_name,
                ready=True,
                platform="xmpp",
                account_id=normalized_account_id,
                scope=server_config.connection_id,
                metadata={
                    "host": server_config.host,
                    "port": server_config.port,
                    "jid": server_config.jid,
                },
            )
        except Exception as exc:
            self._logger.warning(f"XMPP 消息网关上报连接就绪状态失败: {exc}")
            return False

        if not accepted:
            self._logger.warning("XMPP 消息网关连接已建立，但 Host 未接受运行时状态更新")
            return False

        self._runtime_state_connected = True
        self._reported_account_id = normalized_account_id
        self._reported_scope = scope
        self._logger.info(
            f"XMPP 消息网关已激活路由: platform=xmpp account_id={normalized_account_id} "
            f"scope={self._reported_scope or '*'}"
        )
        return True

    async def report_disconnected(self) -> None:
        """向 Host 上报当前连接已断开，并撤销消息网关路由。"""

        if not self._runtime_state_connected:
            had_previous = self._reported_account_id is not None
            self._reported_account_id = None
            self._reported_scope = None
            if had_previous:
                self._logger.debug("runtime_state 已处于断开状态，跳过重复上报")
            return

        self._logger.debug("runtime_state 上报连接断开")
        try:
            await self._gateway_capability.update_state(
                gateway_name=self._gateway_name,
                ready=False,
                platform="xmpp",
            )
        except Exception as exc:
            self._logger.warning(f"XMPP 消息网关上报断开状态失败: {exc}")
        finally:
            self._runtime_state_connected = False
            self._reported_account_id = None
            self._reported_scope = None
            self._logger.debug("runtime_state 断开状态已清除")
