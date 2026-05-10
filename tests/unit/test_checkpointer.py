"""
pipeline/checkpointer.py 单元测试

测试 PostgresCheckpointer 和 MemoryCheckpointer 的检查点保存、加载、删除等功能。
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finagent.pipeline.checkpointer import (
    Checkpoint,
    CheckpointConfig,
    MemoryCheckpointer,
    PostgresCheckpointer,
)
from finagent.pipeline.pipeline import PipelineState


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _make_state(pipeline_id: str = "pipe-001", stage: str = "scoring") -> PipelineState:
    """创建测试用 PipelineState"""
    return PipelineState(
        pipeline_id=pipeline_id,
        agent_id="test-agent",
        eval_mode="full",
        status="running",
        current_stage=stage,
        tasks=[{"task_id": "t1"}],
        current_task_index=1,
        responses=[],
        task_scores=[],
        evaluation_score=None,
        report=None,
        errors=[],
        retry_count=0,
        started_at="2025-01-01T00:00:00",
        completed_at=None,
        metadata={"key": "value"},
        current_phase="static",
        phase_results={},
    )


# ===========================================================================
# CheckpointConfig 测试
# ===========================================================================


class TestCheckpointConfig:
    """测试 CheckpointConfig"""

    def test_defaults(self):
        config = CheckpointConfig()
        assert config.database_url == "postgresql://localhost/finagent_eval"
        assert config.table_name == "pipeline_checkpoints"
        assert config.max_checkpoints_per_pipeline == 10
        assert config.retention_days == 30

    def test_custom_values(self):
        config = CheckpointConfig(
            database_url="postgresql://localhost/test",
            table_name="custom_table",
            max_checkpoints_per_pipeline=5,
        )
        assert config.database_url == "postgresql://localhost/test"
        assert config.table_name == "custom_table"
        assert config.max_checkpoints_per_pipeline == 5


# ===========================================================================
# Checkpoint 数据类测试
# ===========================================================================


class TestCheckpoint:
    """测试 Checkpoint 数据类"""

    def test_to_dict(self):
        state = _make_state()
        cp = Checkpoint(
            checkpoint_id="cp-001",
            pipeline_id="pipe-001",
            state=state,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            stage="scoring",
        )
        d = cp.to_dict()
        assert d["checkpoint_id"] == "cp-001"
        assert d["pipeline_id"] == "pipe-001"
        assert d["stage"] == "scoring"
        assert d["created_at"] == "2025-01-01T12:00:00"
        assert d["state"]["pipeline_id"] == "pipe-001"


# ===========================================================================
# PostgresCheckpointer 测试（内存回退模式）
# ===========================================================================


class TestPostgresCheckpointerInit:
    """测试 PostgresCheckpointer 初始化"""

    @pytest.mark.asyncio
    async def test_initialize_memory_fallback(self):
        """无 DATABASE_URL 时回退到内存存储"""
        with patch.dict(os.environ, {}, clear=True):
            # 确保没有 DATABASE_URL
            os.environ.pop("DATABASE_URL", None)
            checkpointer = PostgresCheckpointer(CheckpointConfig())
            await checkpointer.initialize()
            assert checkpointer._pool is None
            assert hasattr(checkpointer, '_checkpoints')

    @pytest.mark.asyncio
    async def test_initialize_with_db_url_import_error(self):
        """有 DATABASE_URL 但 asyncpg 不可用时回退"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}):
            with patch.dict("sys.modules", {"asyncpg": None}):
                checkpointer = PostgresCheckpointer(CheckpointConfig())
                await checkpointer.initialize()
                assert checkpointer._pool is None

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """多次初始化不重复"""
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        await checkpointer.initialize()  # 第二次不应报错


class TestPostgresCheckpointerSave:
    """测试检查点保存"""

    @pytest.mark.asyncio
    async def test_save_creates_checkpoint(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        state = _make_state()
        cp = await checkpointer.save(state)

        assert isinstance(cp, Checkpoint)
        assert cp.pipeline_id == "pipe-001"
        assert cp.stage == "scoring"
        assert cp.checkpoint_id  # 应该有 UUID

    @pytest.mark.asyncio
    async def test_save_multiple_checkpoints(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()

        state1 = _make_state(pipeline_id="pipe-001", stage="task_generation")
        state2 = _make_state(pipeline_id="pipe-001", stage="scoring")

        cp1 = await checkpointer.save(state1)
        cp2 = await checkpointer.save(state2)

        assert cp1.checkpoint_id != cp2.checkpoint_id
        assert len(checkpointer._checkpoints["pipe-001"]) == 2

    @pytest.mark.asyncio
    async def test_save_cleanup_old_checkpoints(self):
        """超过最大数量时清理旧检查点"""
        config = CheckpointConfig(max_checkpoints_per_pipeline=3)
        checkpointer = PostgresCheckpointer(config)
        await checkpointer.initialize()

        for i in range(5):
            state = _make_state(stage=f"stage-{i}")
            await checkpointer.save(state)

        assert len(checkpointer._checkpoints["pipe-001"]) == 3


class TestPostgresCheckpointerLoad:
    """测试检查点加载"""

    @pytest.mark.asyncio
    async def test_load_latest(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()

        state1 = _make_state(stage="task_generation")
        state2 = _make_state(stage="scoring")

        await checkpointer.save(state1)
        cp2 = await checkpointer.save(state2)

        loaded = await checkpointer.load("pipe-001")
        assert loaded is not None
        assert loaded.checkpoint_id == cp2.checkpoint_id
        assert loaded.stage == "scoring"

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        loaded = await checkpointer.load("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_by_id(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()

        state = _make_state()
        cp = await checkpointer.save(state)

        loaded = await checkpointer.load_by_id(cp.checkpoint_id)
        assert loaded is not None
        assert loaded.checkpoint_id == cp.checkpoint_id

    @pytest.mark.asyncio
    async def test_load_by_id_nonexistent(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        loaded = await checkpointer.load_by_id("nonexistent-id")
        assert loaded is None


class TestPostgresCheckpointerList:
    """测试检查点列表"""

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()

        for i in range(3):
            state = _make_state(stage=f"stage-{i}")
            await checkpointer.save(state)

        checkpoints = await checkpointer.list_checkpoints("pipe-001")
        assert len(checkpoints) == 3

    @pytest.mark.asyncio
    async def test_list_checkpoints_empty(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        checkpoints = await checkpointer.list_checkpoints("nonexistent")
        assert checkpoints == []


class TestPostgresCheckpointerDelete:
    """测试检查点删除"""

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()

        state = _make_state()
        cp = await checkpointer.save(state)

        result = await checkpointer.delete(cp.checkpoint_id)
        assert result is True
        assert await checkpointer.load_by_id(cp.checkpoint_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        result = await checkpointer.delete("nonexistent-id")
        assert result is False


class TestPostgresCheckpointerClose:
    """测试关闭连接"""

    @pytest.mark.asyncio
    async def test_close_no_pool(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        await checkpointer.close()  # 内存模式，无 pool

    @pytest.mark.asyncio
    async def test_close_with_pool(self):
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        mock_pool = AsyncMock()
        checkpointer._pool = mock_pool
        await checkpointer.close()
        mock_pool.close.assert_called_once()
        # 注意: close() 方法不会将 _pool 设为 None


class TestPostgresCheckpointerCreateTables:
    """测试建表"""

    @pytest.mark.asyncio
    async def test_create_tables_no_pool(self):
        """无连接池时跳过建表"""
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        await checkpointer.create_tables()  # 不应报错

    @pytest.mark.asyncio
    async def test_create_tables_with_pool(self):
        """有连接池时执行建表"""
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()
        mock_pool = AsyncMock()
        checkpointer._pool = mock_pool
        await checkpointer.create_tables()
        mock_pool.execute.assert_called_once()


# ===========================================================================
# MemoryCheckpointer 测试
# ===========================================================================


class TestMemoryCheckpointerInit:
    """测试 MemoryCheckpointer 初始化"""

    def test_init(self):
        checkpointer = MemoryCheckpointer()
        assert checkpointer._checkpoints == {}


class TestMemoryCheckpointerSave:
    """测试内存检查点保存"""

    @pytest.mark.asyncio
    async def test_save(self):
        checkpointer = MemoryCheckpointer()
        state = _make_state()
        cp = await checkpointer.save(state)

        assert isinstance(cp, Checkpoint)
        assert cp.pipeline_id == "pipe-001"
        assert cp.checkpoint_id

    @pytest.mark.asyncio
    async def test_save_multiple_pipelines(self):
        checkpointer = MemoryCheckpointer()
        state1 = _make_state(pipeline_id="pipe-001")
        state2 = _make_state(pipeline_id="pipe-002")

        await checkpointer.save(state1)
        await checkpointer.save(state2)

        assert len(checkpointer._checkpoints) == 2
        assert "pipe-001" in checkpointer._checkpoints
        assert "pipe-002" in checkpointer._checkpoints


class TestMemoryCheckpointerLoad:
    """测试内存检查点加载"""

    @pytest.mark.asyncio
    async def test_load_latest(self):
        checkpointer = MemoryCheckpointer()
        state1 = _make_state(stage="task_generation")
        state2 = _make_state(stage="scoring")

        await checkpointer.save(state1)
        cp2 = await checkpointer.save(state2)

        loaded = await checkpointer.load("pipe-001")
        assert loaded is not None
        assert loaded.checkpoint_id == cp2.checkpoint_id

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        checkpointer = MemoryCheckpointer()
        loaded = await checkpointer.load("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_empty_pipeline(self):
        checkpointer = MemoryCheckpointer()
        loaded = await checkpointer.load("pipe-001")
        assert loaded is None


class TestMemoryCheckpointerList:
    """测试内存检查点列表"""

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        checkpointer = MemoryCheckpointer()
        for i in range(3):
            state = _make_state(stage=f"stage-{i}")
            await checkpointer.save(state)

        checkpoints = await checkpointer.list_checkpoints("pipe-001")
        assert len(checkpoints) == 3

    @pytest.mark.asyncio
    async def test_list_checkpoints_empty(self):
        checkpointer = MemoryCheckpointer()
        checkpoints = await checkpointer.list_checkpoints("pipe-001")
        assert checkpoints == []


class TestMemoryCheckpointerClear:
    """测试内存检查点清空"""

    @pytest.mark.asyncio
    async def test_clear_specific_pipeline(self):
        checkpointer = MemoryCheckpointer()
        state1 = _make_state(pipeline_id="pipe-001")
        state2 = _make_state(pipeline_id="pipe-002")

        await checkpointer.save(state1)
        await checkpointer.save(state2)

        await checkpointer.clear("pipe-001")
        assert "pipe-001" not in checkpointer._checkpoints
        assert "pipe-002" in checkpointer._checkpoints

    @pytest.mark.asyncio
    async def test_clear_all(self):
        checkpointer = MemoryCheckpointer()
        state1 = _make_state(pipeline_id="pipe-001")
        state2 = _make_state(pipeline_id="pipe-002")

        await checkpointer.save(state1)
        await checkpointer.save(state2)

        await checkpointer.clear()
        assert checkpointer._checkpoints == {}

    @pytest.mark.asyncio
    async def test_clear_nonexistent(self):
        checkpointer = MemoryCheckpointer()
        await checkpointer.clear("nonexistent")  # 不应报错


# ===========================================================================
# 跨模块集成测试
# ===========================================================================


class TestCheckpointerIntegration:
    """检查点跨模块集成测试"""

    @pytest.mark.asyncio
    async def test_save_load_roundtrip(self):
        """保存后加载的完整往返测试"""
        checkpointer = PostgresCheckpointer(CheckpointConfig())
        await checkpointer.initialize()

        original_state = _make_state(
            pipeline_id="integration-test",
            stage="agent_execution",
        )
        original_state["tasks"] = [{"task_id": "t1", "query": "test"}]
        original_state["responses"] = [{"task_id": "t1", "output": "answer"}]

        saved = await checkpointer.save(original_state)
        loaded = await checkpointer.load("integration-test")

        assert loaded is not None
        assert loaded.state["pipeline_id"] == "integration-test"
        assert loaded.state["current_stage"] == "agent_execution"
        assert len(loaded.state["tasks"]) == 1
        assert loaded.state["tasks"][0]["task_id"] == "t1"

    @pytest.mark.asyncio
    async def test_memory_checkpointer_roundtrip(self):
        """MemoryCheckpointer 往返测试"""
        checkpointer = MemoryCheckpointer()

        state = _make_state(pipeline_id="mem-test")
        saved = await checkpointer.save(state)
        loaded = await checkpointer.load("mem-test")

        assert loaded is not None
        assert loaded.checkpoint_id == saved.checkpoint_id
        assert loaded.state["pipeline_id"] == "mem-test"
