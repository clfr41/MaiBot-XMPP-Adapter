"""XMPP 心跳监测 - 已禁用。

当前版本（0.1.0）已移除应用层心跳逻辑，仅保留类接口以兼容其他组件。
所有方法均为空操作，不会创建任何后台任务。
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
        """启动心跳监测（已禁用，不做任何操作）。"""
        pass

    async def stop(self) -> None:
        """停止心跳监测（已禁用，不做任何操作）。"""
        pass

    def touch(self) -> None:
        """刷新心跳时间戳（已禁用，不做任何操作）。"""
        pass