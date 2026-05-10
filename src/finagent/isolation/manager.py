"""
状态隔离管理器核心实现

基于 Checkpointer 实现评测任务间的状态隔离。
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IsolationConfig:
    """隔离配置"""
    # 隔离级别
    isolation_level: str = "task"  # task | session | evaluation

    # 状态TTL（秒）
    state_ttl_seconds: int = 3600  # 1小时

    # 最大并发隔离数
    max_concurrent_isolations: int = 10

    # 是否启用状态快照
    enable_snapshots: bool = True

    # 快照间隔（任务数）
    snapshot_interval: int = 5


@dataclass
class IsolatedState:
    """隔离状态"""
    isolation_id: str
    evaluation_id: str
    task_id: str | None
    state_data: dict
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


class StateIsolationManager:
    """
    状态隔离管理器

    确保并发评测时各任务的状态完全隔离，互不干扰。
    基于 Checkpointer 机制实现状态的持久化和恢复。
    """

    def __init__(self, config: IsolationConfig | None = None):
        self.config = config or IsolationConfig()
        self._isolations: dict[str, IsolatedState] = {}
        self._lock = asyncio.Lock()

    async def create_isolation(
        self,
        evaluation_id: str,
        initial_state: dict | None = None,
    ) -> str:
        """
        创建隔离上下文

        Args:
            evaluation_id: 评测ID
            initial_state: 初始状态

        Returns:
            隔离ID
        """
        async with self._lock:
            # 检查并发限制
            active_count = sum(
                1 for s in self._isolations.values()
                if s.evaluation_id != evaluation_id
            )
            if active_count >= self.config.max_concurrent_isolations:
                raise RuntimeError(
                    f"并发隔离数已达上限 ({self.config.max_concurrent_isolations})"
                )

            isolation_id = str(uuid.uuid4())

            state = IsolatedState(
                isolation_id=isolation_id,
                evaluation_id=evaluation_id,
                task_id=None,
                state_data=initial_state or {},
            )

            self._isolations[isolation_id] = state
            return isolation_id

    async def get_state(self, isolation_id: str) -> dict | None:
        """获取隔离状态"""
        state = self._isolations.get(isolation_id)
        if state is None:
            return None
        return state.state_data.copy()

    async def update_state(
        self,
        isolation_id: str,
        task_id: str | None,
        state_data: dict,
    ):
        """更新隔离状态"""
        async with self._lock:
            state = self._isolations.get(isolation_id)
            if state is None:
                raise ValueError(f"隔离上下文不存在: {isolation_id}")

            state.task_id = task_id
            state.state_data.update(state_data)
            state.updated_at = datetime.now()

    async def snapshot_state(self, isolation_id: str) -> dict | None:
        """创建状态快照"""
        state = self._isolations.get(isolation_id)
        if state is None:
            return None

        snapshot = {
            "isolation_id": state.isolation_id,
            "evaluation_id": state.evaluation_id,
            "task_id": state.task_id,
            "state_data": state.state_data.copy(),
            "snapshot_at": datetime.now().isoformat(),
        }

        state.metadata.setdefault("snapshots", []).append(snapshot)
        return snapshot

    async def restore_snapshot(
        self,
        isolation_id: str,
        snapshot_index: int = -1,
    ) -> dict | None:
        """恢复状态快照"""
        state = self._isolations.get(isolation_id)
        if state is None:
            return None

        snapshots = state.metadata.get("snapshots", [])
        if not snapshots:
            return None

        snapshot = snapshots[snapshot_index]
        state.state_data = snapshot["state_data"].copy()
        state.updated_at = datetime.now()

        return state.state_data.copy()

    async def cleanup_isolation(self, isolation_id: str):
        """清理隔离上下文"""
        async with self._lock:
            self._isolations.pop(isolation_id, None)

    async def cleanup_expired(self):
        """清理过期的隔离上下文"""
        async with self._lock:
            now = datetime.now()
            expired = [
                iso_id for iso_id, state in self._isolations.items()
                if (now - state.updated_at).total_seconds() > self.config.state_ttl_seconds
            ]
            for iso_id in expired:
                del self._isolations[iso_id]
            return len(expired)

    async def list_isolations(
        self,
        evaluation_id: str | None = None,
    ) -> list[dict]:
        """列出隔离上下文"""
        states = list(self._isolations.values())

        if evaluation_id:
            states = [s for s in states if s.evaluation_id == evaluation_id]

        return [
            {
                "isolation_id": s.isolation_id,
                "evaluation_id": s.evaluation_id,
                "task_id": s.task_id,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in states
        ]

    async def get_isolation_stats(self) -> dict:
        """获取隔离统计信息"""
        return {
            "active_isolations": len(self._isolations),
            "max_concurrent": self.config.max_concurrent_isolations,
            "isolation_level": self.config.isolation_level,
            "state_ttl_seconds": self.config.state_ttl_seconds,
        }
