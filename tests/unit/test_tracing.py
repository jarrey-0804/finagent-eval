"""
tracing/langsmith.py 单元测试

测试 LangSmith 追踪封装类、TraceContext 数据类、
TraceEvaluation 装饰器/上下文管理器的功能。
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from finagent.tracing.langsmith import (
    LangSmithTracer,
    TraceContext,
    TraceEvaluation,
)


# ---------------------------------------------------------------------------
# TraceContext 测试
# ---------------------------------------------------------------------------

class TestTraceContext:

    def test_default_values(self):
        """默认值应为 None / 空字典"""
        ctx = TraceContext()
        assert ctx.run_id is None
        assert ctx.parent_run_id is None
        assert ctx.evaluation_id is None
        assert ctx.metadata == {}

    def test_custom_values(self):
        """自定义值应正确存储"""
        ctx = TraceContext(
            run_id="run-123",
            parent_run_id="parent-456",
            evaluation_id="eval-789",
            metadata={"key": "value"},
        )
        assert ctx.run_id == "run-123"
        assert ctx.parent_run_id == "parent-456"
        assert ctx.evaluation_id == "eval-789"
        assert ctx.metadata == {"key": "value"}


# ---------------------------------------------------------------------------
# LangSmithTracer 测试
# ---------------------------------------------------------------------------

class TestLangSmithTracer:

    def test_init_default_params(self):
        """默认参数应从环境变量读取"""
        with patch.dict("os.environ", {}, clear=True):
            tracer = LangSmithTracer()
        assert tracer._project_name == "finagent-eval"
        assert tracer._api_key is None
        assert tracer._api_url is None
        assert tracer.is_enabled is False

    def test_init_custom_params(self):
        """自定义参数应覆盖环境变量"""
        tracer = LangSmithTracer(
            project_name="my-project",
            api_key="key-123",
            api_url="https://api.example.com",
        )
        assert tracer._project_name == "my-project"
        assert tracer._api_key == "key-123"
        assert tracer._api_url == "https://api.example.com"

    def test_init_reads_env_vars(self):
        """应从环境变量读取配置"""
        with patch.dict("os.environ", {
            "LANGSMITH_PROJECT": "env-project",
            "LANGSMITH_API_KEY": "env-key",
            "LANGSMITH_ENDPOINT": "https://env.api.com",
        }):
            tracer = LangSmithTracer()
        assert tracer._project_name == "env-project"
        assert tracer._api_key == "env-key"
        assert tracer._api_url == "https://env.api.com"

    def test_initialize_no_langsmith(self):
        """langsmith 未安装时 initialize 应禁用追踪"""
        with patch("finagent.tracing.langsmith._LANGSMITH_AVAILABLE", False):
            tracer = LangSmithTracer(api_key="test-key")
            tracer.initialize()
        assert tracer.is_enabled is False

    def test_initialize_no_api_key(self):
        """无 API Key 时 initialize 应禁用追踪"""
        with patch("finagent.tracing.langsmith._LANGSMITH_AVAILABLE", True):
            tracer = LangSmithTracer()
            tracer._api_key = None
            tracer.initialize()
        assert tracer.is_enabled is False

    def test_initialize_success(self):
        """成功初始化应启用追踪"""
        mock_client = MagicMock()
        with patch("finagent.tracing.langsmith._LANGSMITH_AVAILABLE", True):
            with patch("finagent.tracing.langsmith.LangSmithClient", return_value=mock_client):
                tracer = LangSmithTracer(api_key="test-key")
                tracer.initialize()
        assert tracer.is_enabled is True
        assert tracer._client is mock_client

    def test_initialize_exception(self):
        """初始化异常应禁用追踪"""
        with patch("finagent.tracing.langsmith._LANGSMITH_AVAILABLE", True):
            with patch("finagent.tracing.langsmith.LangSmithClient", side_effect=Exception("连接失败")):
                tracer = LangSmithTracer(api_key="test-key")
                tracer.initialize()
        assert tracer.is_enabled is False

    def test_start_evaluation_run_disabled(self):
        """追踪禁用时 start_evaluation_run 应返回 None"""
        tracer = LangSmithTracer()
        tracer._enabled = False
        result = tracer.start_evaluation_run("eval-001", "agent-1", "full")
        assert result is None

    def test_start_evaluation_run_enabled(self):
        """追踪启用时应返回 run_id"""
        mock_client = MagicMock()
        mock_run = MagicMock()
        mock_client.create_run.return_value = mock_run
        tracer = LangSmithTracer(api_key="key")
        tracer._enabled = True
        tracer._client = mock_client

        run_id = tracer.start_evaluation_run("eval-001", "agent-1", "full")
        assert run_id is not None
        mock_client.create_run.assert_called_once()
        assert run_id in tracer._runs

    def test_start_evaluation_run_exception(self):
        """start_evaluation_run 异常应返回 None"""
        mock_client = MagicMock()
        mock_client.create_run.side_effect = Exception("API 错误")
        tracer = LangSmithTracer(api_key="key")
        tracer._enabled = True
        tracer._client = mock_client

        run_id = tracer.start_evaluation_run("eval-001", "agent-1", "full")
        assert run_id is None

    def test_start_task_run_disabled(self):
        """追踪禁用时 start_task_run 应返回 None"""
        tracer = LangSmithTracer()
        tracer._enabled = False
        result = tracer.start_task_run(None, "task-001", "accuracy")
        assert result is None

    def test_start_task_run_enabled(self):
        """追踪启用时应返回 run_id"""
        mock_client = MagicMock()
        mock_run = MagicMock()
        mock_client.create_run.return_value = mock_run
        tracer = LangSmithTracer(api_key="key")
        tracer._enabled = True
        tracer._client = mock_client

        run_id = tracer.start_task_run("parent-123", "task-001", "accuracy")
        assert run_id is not None
        mock_client.create_run.assert_called_once()
        call_kwargs = mock_client.create_run.call_args
        assert call_kwargs.kwargs.get("parent_run_id") == "parent-123"

    def test_end_run_disabled(self):
        """追踪禁用时 end_run 应不执行"""
        mock_client = MagicMock()
        tracer = LangSmithTracer()
        tracer._enabled = False
        tracer._client = mock_client
        tracer.end_run("run-123")  # 不应抛出
        mock_client.update_run.assert_not_called()

    def test_end_run_none_run_id(self):
        """run_id 为 None 时 end_run 应不执行"""
        mock_client = MagicMock()
        tracer = LangSmithTracer()
        tracer._enabled = True
        tracer._client = mock_client
        tracer.end_run(None)
        mock_client.update_run.assert_not_called()

    def test_end_run_success(self):
        """正常结束 run 应调用 update_run 并移除缓存"""
        mock_client = MagicMock()
        tracer = LangSmithTracer()
        tracer._enabled = True
        tracer._client = mock_client
        tracer._runs["run-123"] = MagicMock()

        tracer.end_run("run-123", outputs={"score": 85.0})
        mock_client.update_run.assert_called_once()
        assert "run-123" not in tracer._runs

    def test_end_run_with_error(self):
        """带错误结束 run 应传递 error 参数"""
        mock_client = MagicMock()
        tracer = LangSmithTracer()
        tracer._enabled = True
        tracer._client = mock_client
        tracer._runs["run-123"] = MagicMock()

        tracer.end_run("run-123", error="执行超时")
        mock_client.update_run.assert_called_once()
        call_kwargs = mock_client.update_run.call_args
        assert call_kwargs.kwargs.get("error") == "执行超时"

    def test_log_evaluation_score_disabled(self):
        """追踪禁用时 log_evaluation_score 应不执行"""
        mock_client = MagicMock()
        tracer = LangSmithTracer()
        tracer._enabled = False
        tracer._client = mock_client
        tracer.log_evaluation_score("run-123", "accuracy", 85.0)
        mock_client.create_feedback.assert_not_called()

    def test_log_evaluation_score_success(self):
        """正常记录评分应调用 create_feedback"""
        mock_client = MagicMock()
        tracer = LangSmithTracer()
        tracer._enabled = True
        tracer._client = mock_client

        tracer.log_evaluation_score("run-123", "accuracy", 85.0, details={"detail": "ok"})
        mock_client.create_feedback.assert_called_once()
        call_kwargs = mock_client.create_feedback.call_args
        assert call_kwargs.kwargs.get("key") == "accuracy"
        assert call_kwargs.kwargs.get("score") == 85.0

    def test_get_run_url_disabled(self):
        """追踪禁用时 get_run_url 应返回 None"""
        tracer = LangSmithTracer()
        tracer._enabled = False
        assert tracer.get_run_url("run-123") is None

    def test_get_run_url_none_run_id(self):
        """run_id 为 None 时应返回 None"""
        tracer = LangSmithTracer()
        tracer._enabled = True
        assert tracer.get_run_url(None) is None

    def test_get_run_url_default_endpoint(self):
        """默认 API URL 应使用 smith.langchain.com"""
        tracer = LangSmithTracer()
        tracer._enabled = True
        tracer._api_url = None
        tracer._project_name = "test-project"

        url = tracer.get_run_url("run-123")
        assert "smith.langchain.com" in url
        assert "test-project" in url
        assert "run=run-123" in url

    def test_get_run_url_custom_endpoint(self):
        """自定义 API URL 应正确处理"""
        tracer = LangSmithTracer()
        tracer._enabled = True
        tracer._api_url = "https://custom.api.com/api"
        tracer._project_name = "my-project"

        url = tracer.get_run_url("run-456")
        assert "/api" not in url  # /api 应被移除
        assert "custom.api.com" in url
        assert "my-project" in url

    def test_get_run_url_trailing_slash(self):
        """尾部斜杠应被移除"""
        tracer = LangSmithTracer()
        tracer._enabled = True
        tracer._api_url = "https://api.example.com/"
        tracer._project_name = "proj"

        url = tracer.get_run_url("run-789")
        assert "example.com/o" in url


# ---------------------------------------------------------------------------
# TraceEvaluation 测试
# ---------------------------------------------------------------------------

class TestTraceEvaluation:

    def test_context_manager_success(self):
        """上下文管理器正常退出时应记录完成状态"""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.start_evaluation_run.return_value = "run-001"
        mock_tracer.end_run = MagicMock()

        with TraceEvaluation(mock_tracer, "eval-001", "agent-1", "full") as te:
            assert te.context.run_id == "run-001"
            assert te.context.evaluation_id == "eval-001"

        mock_tracer.end_run.assert_called_once()
        call_kwargs = mock_tracer.end_run.call_args
        assert call_kwargs.kwargs.get("outputs") == {"status": "completed"}
        assert call_kwargs.kwargs.get("error") is None

    def test_context_manager_exception(self):
        """上下文管理器异常时应记录错误但不吞掉异常"""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.start_evaluation_run.return_value = "run-001"
        mock_tracer.end_run = MagicMock()

        with pytest.raises(ValueError, match="测试错误"):
            with TraceEvaluation(mock_tracer, "eval-001", "agent-1", "full"):
                raise ValueError("测试错误")

        mock_tracer.end_run.assert_called_once()
        call_kwargs = mock_tracer.end_run.call_args
        assert call_kwargs.kwargs.get("outputs") == {"status": "error"}
        assert "测试错误" in call_kwargs.kwargs.get("error", "")

    def test_decorator_sync_function(self):
        """作为装饰器用于同步函数"""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.start_evaluation_run.return_value = "run-001"
        mock_tracer.end_run = MagicMock()

        @TraceEvaluation(mock_tracer, "eval-001", "agent-1", "full")
        def my_eval():
            return "result"

        result = my_eval()
        assert result == "result"
        mock_tracer.start_evaluation_run.assert_called_once()
        mock_tracer.end_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator_async_function(self):
        """作为装饰器用于异步函数"""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.start_evaluation_run.return_value = "run-001"
        mock_tracer.end_run = MagicMock()

        @TraceEvaluation(mock_tracer, "eval-001", "agent-1", "full")
        async def my_async_eval():
            return "async-result"

        result = await my_async_eval()
        assert result == "async-result"
        mock_tracer.start_evaluation_run.assert_called_once()
        mock_tracer.end_run.assert_called_once()

    def test_task_run_context_manager_success(self):
        """task_run 上下文管理器正常退出应结束子 run"""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.start_task_run.return_value = "child-run-001"
        mock_tracer.end_run = MagicMock()

        te = TraceEvaluation(mock_tracer, "eval-001", "agent-1", "full")
        te._run_id = "parent-run-001"

        with te.task_run("task-001", "accuracy") as child_ctx:
            assert child_ctx.run_id == "child-run-001"
            assert child_ctx.parent_run_id == "parent-run-001"
            assert child_ctx.metadata["task_id"] == "task-001"
            assert child_ctx.metadata["dimension"] == "accuracy"

        mock_tracer.end_run.assert_called_once_with(run_id="child-run-001")

    def test_task_run_context_manager_exception(self):
        """task_run 上下文管理器异常应记录错误并重新抛出"""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.start_task_run.return_value = "child-run-001"
        mock_tracer.end_run = MagicMock()

        te = TraceEvaluation(mock_tracer, "eval-001", "agent-1", "full")
        te._run_id = "parent-run-001"

        with pytest.raises(RuntimeError, match="子任务失败"):
            with te.task_run("task-001", "accuracy"):
                raise RuntimeError("子任务失败")

        mock_tracer.end_run.assert_called_once()
        call_kwargs = mock_tracer.end_run.call_args
        assert "子任务失败" in call_kwargs.kwargs.get("error", "")

    def test_log_score_delegates_to_tracer(self):
        """log_score 应委托给 tracer.log_evaluation_score"""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.log_evaluation_score = MagicMock()

        te = TraceEvaluation(mock_tracer, "eval-001", "agent-1", "full")
        te._run_id = "parent-run-001"

        te.log_score("accuracy", 85.0, details={"test": True})
        mock_tracer.log_evaluation_score.assert_called_once_with(
            run_id="parent-run-001",
            metric_name="accuracy",
            score=85.0,
            details={"test": True},
        )

    def test_log_score_custom_run_id(self):
        """log_score 使用自定义 run_id 时应覆盖默认值"""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.log_evaluation_score = MagicMock()

        te = TraceEvaluation(mock_tracer, "eval-001", "agent-1", "full")
        te._run_id = "parent-run-001"

        te.log_score("accuracy", 85.0, run_id="custom-run-999")
        mock_tracer.log_evaluation_score.assert_called_once_with(
            run_id="custom-run-999",
            metric_name="accuracy",
            score=85.0,
            details=None,
        )
