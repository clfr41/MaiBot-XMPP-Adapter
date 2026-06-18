"""XMPP 心跳监测 - **已禁用**。

当前版本（0.1.0）已移除应用层心跳逻辑，仅保留类接口以兼容其他组件。
所有方法均为空操作，不会创建任何后台任务。

如果未来版本需要重新启用心跳检测，请：
1. 实现 ``_check_task`` 后台定时检查逻辑
2. 在 ``start()`` 中根据 ``default_interval_sec > 0`` 决定是否启动
3. 在 ``stop()`` 中取消并清理 ``_check_task``
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

import asyncio


class XmppHeartbeatMonitor:
    """XMPP 心跳状态监测器（已禁用）。

    原本负责定期检查心跳时间戳，超时后通知上层组件。
    现已被禁用，所有方法调用均为无操作。
    """

    def __init__(
        self,
        logger: Any,
        on_timeout: Callable[[str], Awaitable[None]],
    ) -> None:
        self._logger = logger
        self._on_timeout = on_timeout
        self._self_id: str = ""
        self._interval_sec: float = 30.0
        self._check_task: Optional[asyncio.Task[None]] = None

    async def start(self, self_id: str, default_interval_sec: float) -> None:
        """启动心跳监测（已禁用，不做任何操作）。

        Args:
            self_id: 机器人 JID。
            default_interval_sec: 心跳间隔（秒），当前版本忽略此参数。
        """
        self._logger.debug(
            f"XMPP 心跳监测已禁用，跳过启动 (self_id={self_id}, "
            f"interval={default_interval_sec})"
        )

    async def stop(self) -> None:
        """停止心跳监测（已禁用，不做任何操作）。"""
        self._logger.debug("XMPP 心跳监测已禁用，跳过停止")

    def touch(self) -> None:
        """刷新心跳时间戳（已禁用，不做任何操作）。"""
        pass
