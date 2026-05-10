"""
生产级检查点管理器

支持 PostgreSQL 持久化的状态检查点，用于生产环境的状态隔离和断点续跑。
当 DATABASE_URL 未设置时，自动回退到内存存储。
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CheckpointData(BaseModel):
    """检查点数据"""
    checkpoint_id: str
    evaluation_id: str
    task_index: int
    state_data: dict
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductionCheckpointer:
    """
    生产级检查点管理器

    支持 PostgreSQL 持久化，提供断点续跑能力。
    当 database_url 为空或连接失败时，自动回退到内存存储。

    数据库表结构对应 config/migrations/001_init_schema.sql 中的 checkpoints 表：
        id           UUID        PRIMARY KEY
        evaluation_id UUID       NOT NULL
        thread_id    VARCHAR(255) NOT NULL
        checkpoint   JSONB       NOT NULL
        parent_id    UUID        (可空)
        created_at   TIMESTAMPTZ NOT NULL
    """

    def __init__(self, database_url: str = ""):
        """
        初始化检查点管理器。

        Args:
            database_url: PostgreSQL 连接 URL。
                          如果为空字符串，则自动从环境变量 DATABASE_URL 读取。
                          如果仍未获取到，则回退到内存存储。
        """
        # 确定数据库 URL
        self._raw_url = database_url or os.environ.get("DATABASE_URL", "")
        self._use_postgres = bool(self._raw_url)

        # PostgreSQL 连接池
        self._pool: Any = None
        self._initialized = False

        # 内存回退存储
        self._checkpoints: dict[str, list[CheckpointData]] = {}

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def initialize(self):
        """初始化数据库连接池（PostgreSQL 模式）或标记内存模式就绪。"""
        if self._initialized:
            return

        if self._use_postgres:
            try:
                import asyncpg

                self._pool = await asyncpg.create_pool(
                    self._raw_url,
                    min_size=2,
                    max_size=10,
                )
                self._initialized = True
                logger.info("ProductionCheckpointer: PostgreSQL 连接池已初始化")
            except Exception as exc:
                logger.warning(
                    "ProductionCheckpointer: PostgreSQL 连接失败，回退到内存存储: %s",
                    exc,
                )
                self._use_postgres = False
                self._pool = None
                self._initialized = True
        else:
            self._initialized = True
            logger.info("ProductionCheckpointer: 使用内存存储模式")

    async def close(self):
        """关闭数据库连接池。"""
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception as exc:
                logger.warning("ProductionCheckpointer: 关闭连接池时出错: %s", exc)
            self._pool = None
        self._initialized = False

    # ------------------------------------------------------------------
    # 核心 CRUD
    # ------------------------------------------------------------------

    async def save_checkpoint(
        self,
        evaluation_id: str,
        task_index: int,
        state_data: dict,
        metadata: dict | None = None,
    ) -> str:
        """
        保存检查点。

        Args:
            evaluation_id: 评测 ID（对应 checkpoints.evaluation_id）
            task_index: 当前任务索引
            state_data: 状态数据（序列化为 JSONB 存入 checkpoint 列）
            metadata: 可选元数据

        Returns:
            检查点 ID
        """
        checkpoint_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        meta = metadata or {}

        checkpoint = CheckpointData(
            checkpoint_id=checkpoint_id,
            evaluation_id=evaluation_id,
            task_index=task_index,
            state_data=state_data,
            metadata=meta,
            created_at=now,
        )

        if self._use_postgres and self._pool is not None:
            try:
                await self._pool.execute(
                    """
                    INSERT INTO checkpoints (id, evaluation_id, thread_id, checkpoint, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    checkpoint_id,
                    evaluation_id,
                    f"eval_{evaluation_id}",
                    json.dumps({
                        "task_index": task_index,
                        "state_data": state_data,
                        "metadata": meta,
                    }),
                    now,
                )
                return checkpoint_id
            except Exception as exc:
                logger.error(
                    "ProductionCheckpointer: 保存检查点到 PostgreSQL 失败，回退到内存: %s",
                    exc,
                )
                # 回退到内存

        # 内存存储
        if evaluation_id not in self._checkpoints:
            self._checkpoints[evaluation_id] = []
        self._checkpoints[evaluation_id].append(checkpoint)
        return checkpoint_id

    async def load_latest_checkpoint(
        self,
        evaluation_id: str,
    ) -> CheckpointData | None:
        """加载指定评测的最新检查点。"""
        if self._use_postgres and self._pool is not None:
            try:
                row = await self._pool.fetchrow(
                    """
                    SELECT id, evaluation_id, thread_id, checkpoint, created_at
                    FROM checkpoints
                    WHERE evaluation_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    evaluation_id,
                )
                if row is None:
                    return None
                return self._row_to_checkpoint(row)
            except Exception as exc:
                logger.error(
                    "ProductionCheckpointer: 从 PostgreSQL 加载检查点失败，回退到内存: %s",
                    exc,
                )

        # 内存存储
        checkpoints = self._checkpoints.get(evaluation_id, [])
        return checkpoints[-1] if checkpoints else None

    async def load_checkpoint_at_task(
        self,
        evaluation_id: str,
        task_index: int,
    ) -> CheckpointData | None:
        """加载指定评测在特定任务索引处的检查点。"""
        if self._use_postgres and self._pool is not None:
            try:
                row = await self._pool.fetchrow(
                    """
                    SELECT id, evaluation_id, thread_id, checkpoint, created_at
                    FROM checkpoints
                    WHERE evaluation_id = $1
                      AND checkpoint->>'task_index' = $2
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    evaluation_id,
                    str(task_index),
                )
                if row is None:
                    return None
                return self._row_to_checkpoint(row)
            except Exception as exc:
                logger.error(
                    "ProductionCheckpointer: 从 PostgreSQL 加载检查点失败，回退到内存: %s",
                    exc,
                )

        # 内存存储
        checkpoints = self._checkpoints.get(evaluation_id, [])
        for cp in checkpoints:
            if cp.task_index == task_index:
                return cp
        return None

    async def list_checkpoints(
        self,
        evaluation_id: str,
    ) -> list[dict]:
        """列出指定评测的所有检查点（摘要信息）。"""
        if self._use_postgres and self._pool is not None:
            try:
                rows = await self._pool.fetch(
                    """
                    SELECT id, checkpoint, created_at
                    FROM checkpoints
                    WHERE evaluation_id = $1
                    ORDER BY created_at ASC
                    """,
                    evaluation_id,
                )
                return [
                    {
                        "checkpoint_id": str(row["id"]),
                        "task_index": row["checkpoint"].get("task_index", -1),
                        "created_at": row["created_at"].isoformat(),
                        "metadata": row["checkpoint"].get("metadata", {}),
                    }
                    for row in rows
                ]
            except Exception as exc:
                logger.error(
                    "ProductionCheckpointer: 从 PostgreSQL 列出检查点失败，回退到内存: %s",
                    exc,
                )

        # 内存存储
        checkpoints = self._checkpoints.get(evaluation_id, [])
        return [
            {
                "checkpoint_id": cp.checkpoint_id,
                "task_index": cp.task_index,
                "created_at": cp.created_at.isoformat(),
                "metadata": cp.metadata,
            }
            for cp in checkpoints
        ]

    async def delete_checkpoints(self, evaluation_id: str) -> bool:
        """
        删除指定评测的所有检查点。

        Returns:
            是否成功删除（PostgreSQL 模式下反映实际删除行数；内存模式始终返回 True）。
        """
        if self._use_postgres and self._pool is not None:
            try:
                result = await self._pool.execute(
                    "DELETE FROM checkpoints WHERE evaluation_id = $1",
                    evaluation_id,
                )
                # asyncpg execute 返回 "DELETE N" 字符串
                deleted = int(result.split()[-1]) if result else 0
                return deleted > 0
            except Exception as exc:
                logger.error(
                    "ProductionCheckpointer: 从 PostgreSQL 删除检查点失败，回退到内存: %s",
                    exc,
                )

        # 内存存储
        removed = evaluation_id in self._checkpoints
        self._checkpoints.pop(evaluation_id, None)
        return removed

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    async def cleanup_old_checkpoints(
        self,
        max_per_evaluation: int = 50,
    ):
        """清理旧检查点，每个评测最多保留 max_per_evaluation 条。"""
        if self._use_postgres and self._pool is not None:
            try:
                # 先查出所有有超量检查点的 evaluation_id
                eval_ids = await self._pool.fetch(
                    """
                    SELECT evaluation_id
                    FROM checkpoints
                    GROUP BY evaluation_id
                    HAVING COUNT(*) > $1
                    """,
                    max_per_evaluation,
                )
                for record in eval_ids:
                    eid = str(record["evaluation_id"])
                    await self._pool.execute(
                        """
                        DELETE FROM checkpoints
                        WHERE id IN (
                            SELECT id FROM checkpoints
                            WHERE evaluation_id = $1
                            ORDER BY created_at ASC
                            OFFSET $2
                        )
                        """,
                        eid,
                        max_per_evaluation,
                    )
            except Exception as exc:
                logger.error(
                    "ProductionCheckpointer: 清理 PostgreSQL 旧检查点失败: %s", exc
                )

        # 内存存储清理
        for _eval_id, checkpoints in self._checkpoints.items():
            while len(checkpoints) > max_per_evaluation:
                checkpoints.pop(0)

    async def get_resume_info(
        self,
        evaluation_id: str,
    ) -> dict | None:
        """获取断点续跑信息。"""
        latest = await self.load_latest_checkpoint(evaluation_id)

        if latest is None:
            return None

        return {
            "evaluation_id": evaluation_id,
            "last_task_index": latest.task_index,
            "resume_from_task": latest.task_index + 1,
            "state_data": latest.state_data,
            "checkpoint_id": latest.checkpoint_id,
            "checkpoint_time": latest.created_at.isoformat(),
        }

    async def create_tables(self):
        """创建数据库表（仅在 PostgreSQL 模式下有效）。"""
        if not (self._use_postgres and self._pool is not None):
            return

        try:
            await self._pool.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_checkpoints (
                    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                    evaluation_id UUID       NOT NULL,
                    thread_id    VARCHAR(255) NOT NULL,
                    checkpoint   JSONB       NOT NULL DEFAULT '{}',
                    parent_id    UUID        REFERENCES evaluation_checkpoints(id) ON DELETE SET NULL,
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_ec_evaluation_id
                    ON evaluation_checkpoints(evaluation_id);
                CREATE INDEX IF NOT EXISTS idx_ec_thread_id
                    ON evaluation_checkpoints(thread_id);
                CREATE INDEX IF NOT EXISTS idx_ec_created_at
                    ON evaluation_checkpoints(created_at DESC);
                """
            )
            logger.info("ProductionCheckpointer: 数据库表已创建/确认")
        except Exception as exc:
            logger.error("ProductionCheckpointer: 创建数据库表失败: %s", exc)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_checkpoint(row: Any) -> CheckpointData:
        """将 asyncpg Record 行转换为 CheckpointData。"""
        checkpoint_json = row["checkpoint"]
        if isinstance(checkpoint_json, str):
            checkpoint_json = json.loads(checkpoint_json)

        return CheckpointData(
            checkpoint_id=str(row["id"]),
            evaluation_id=str(row["evaluation_id"]),
            task_index=checkpoint_json.get("task_index", -1),
            state_data=checkpoint_json.get("state_data", {}),
            metadata=checkpoint_json.get("metadata", {}),
            created_at=row["created_at"],
        )
