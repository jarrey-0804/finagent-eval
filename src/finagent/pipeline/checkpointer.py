"""
检查点模块

实现评测流水线的状态持久化和恢复功能。
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .pipeline import PipelineState

logger = logging.getLogger(__name__)


class CheckpointConfig(BaseModel):
    """检查点配置"""

    # 数据库配置
    database_url: str = Field(
        default="postgresql://localhost/finagent_eval",
        description="PostgreSQL数据库连接URL"
    )

    # 检查点表名
    table_name: str = Field(
        default="pipeline_checkpoints",
        description="检查点表名"
    )

    # 保留策略
    max_checkpoints_per_pipeline: int = Field(
        default=10,
        description="每个流水线保留的最大检查点数"
    )

    retention_days: int = Field(
        default=30,
        description="检查点保留天数"
    )


@dataclass
class Checkpoint:
    """检查点"""
    checkpoint_id: str
    pipeline_id: str
    state: PipelineState
    created_at: datetime
    stage: str

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "pipeline_id": self.pipeline_id,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "stage": self.stage,
        }


class PostgresCheckpointer:
    """PostgreSQL检查点管理器"""

    def __init__(self, config: CheckpointConfig):
        self.config = config
        self._pool = None

    async def initialize(self):
        """初始化数据库连接"""
        database_url = os.environ.get("DATABASE_URL", "")
        if database_url:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(
                    database_url,
                    min_size=2,
                    max_size=10,
                )
                logger.info("PostgresCheckpointer: PostgreSQL 连接池已初始化")
                return
            except ImportError:
                logger.warning(
                    "PostgresCheckpointer: asyncpg 未安装，回退到内存存储"
                )
            except Exception as exc:
                logger.warning(
                    "PostgresCheckpointer: PostgreSQL 连接失败，回退到内存存储: %s",
                    exc,
                )
        # 回退到内存存储
        self._checkpoints: dict[str, list[Checkpoint]] = {}
        logger.info("PostgresCheckpointer: 使用内存存储模式")

    async def close(self):
        """关闭数据库连接"""
        if self._pool:
            await self._pool.close()

    async def save(self, state: PipelineState) -> Checkpoint:
        """保存检查点"""
        import uuid

        checkpoint = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            pipeline_id=state["pipeline_id"],
            state=state,
            created_at=datetime.now(),
            stage=state["current_stage"],
        )

        # 模拟保存到数据库
        pipeline_id = state["pipeline_id"]
        if pipeline_id not in self._checkpoints:
            self._checkpoints[pipeline_id] = []

        self._checkpoints[pipeline_id].append(checkpoint)

        # 清理旧检查点
        await self._cleanup_old_checkpoints(pipeline_id)

        return checkpoint

    async def load(self, pipeline_id: str) -> Checkpoint | None:
        """加载最新检查点"""
        checkpoints = self._checkpoints.get(pipeline_id, [])
        if checkpoints:
            return checkpoints[-1]
        return None

    async def load_by_id(self, checkpoint_id: str) -> Checkpoint | None:
        """根据ID加载检查点"""
        for checkpoints in self._checkpoints.values():
            for cp in checkpoints:
                if cp.checkpoint_id == checkpoint_id:
                    return cp
        return None

    async def list_checkpoints(self, pipeline_id: str) -> list[Checkpoint]:
        """列出流水线的所有检查点"""
        return self._checkpoints.get(pipeline_id, [])

    async def delete(self, checkpoint_id: str) -> bool:
        """删除检查点"""
        for _pipeline_id, checkpoints in self._checkpoints.items():
            for i, cp in enumerate(checkpoints):
                if cp.checkpoint_id == checkpoint_id:
                    checkpoints.pop(i)
                    return True
        return False

    async def _cleanup_old_checkpoints(self, pipeline_id: str):
        """清理旧检查点"""
        checkpoints = self._checkpoints.get(pipeline_id, [])
        max_count = self.config.max_checkpoints_per_pipeline

        while len(checkpoints) > max_count:
            checkpoints.pop(0)  # 删除最旧的

    async def create_tables(self):
        """创建数据库表"""
        if self._pool is None:
            logger.debug("PostgresCheckpointer: 无数据库连接，跳过建表")
            return

        try:
            # 读取迁移 SQL 文件
            migration_path = Path(__file__).resolve().parents[3] / "config" / "migrations" / "001_init_schema.sql"
            if migration_path.exists():
                ddl_sql = migration_path.read_text(encoding="utf-8")
            else:
                # 回退到内联 DDL
                ddl_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.config.table_name} (
                    checkpoint_id VARCHAR(36) PRIMARY KEY,
                    pipeline_id VARCHAR(36) NOT NULL,
                    state JSONB NOT NULL,
                    stage VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_{self.config.table_name}_pipeline_id
                    ON {self.config.table_name}(pipeline_id);
                CREATE INDEX IF NOT EXISTS idx_{self.config.table_name}_created_at
                    ON {self.config.table_name}(created_at);
                """

            await self._pool.execute(ddl_sql)
            logger.info("PostgresCheckpointer: 数据库表已创建/确认")
        except Exception as exc:
            logger.error("PostgresCheckpointer: 创建数据库表失败: %s", exc)


class MemoryCheckpointer:
    """内存检查点管理器（用于测试）"""

    def __init__(self):
        self._checkpoints: dict[str, list[Checkpoint]] = {}

    async def save(self, state: PipelineState) -> Checkpoint:
        """保存检查点"""
        import uuid

        checkpoint = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            pipeline_id=state["pipeline_id"],
            state=state,
            created_at=datetime.now(),
            stage=state["current_stage"],
        )

        pipeline_id = state["pipeline_id"]
        if pipeline_id not in self._checkpoints:
            self._checkpoints[pipeline_id] = []

        self._checkpoints[pipeline_id].append(checkpoint)
        return checkpoint

    async def load(self, pipeline_id: str) -> Checkpoint | None:
        """加载最新检查点"""
        checkpoints = self._checkpoints.get(pipeline_id, [])
        return checkpoints[-1] if checkpoints else None

    async def list_checkpoints(self, pipeline_id: str) -> list[Checkpoint]:
        """列出所有检查点"""
        return self._checkpoints.get(pipeline_id, [])

    async def clear(self, pipeline_id: str | None = None):
        """清空检查点"""
        if pipeline_id:
            self._checkpoints.pop(pipeline_id, None)
        else:
            self._checkpoints.clear()
