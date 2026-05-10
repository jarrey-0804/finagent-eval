"""
API 集成测试

测试 API 层的认证中间件、限流中间件、数据模型和指标采集集成。
所有测试均为自包含，不依赖 FastAPI 应用实例。
"""

import asyncio
import time
from datetime import datetime, timedelta

import pytest

from finagent.api.middleware.auth import JWTAuthMiddleware
from finagent.api.middleware.ratelimit import RateLimitConfig, RateLimitMiddleware, RateLimitResult
from finagent.monitor.metrics import MetricsCollector


# ============================================================================
# 1. JWT 认证中间件测试
# ============================================================================


class TestJWTAuthMiddleware:
    """JWT 认证中间件测试套件"""

    def setup_method(self):
        """每个测试方法前初始化中间件"""
        self.middleware = JWTAuthMiddleware(
            secret_key="test-secret-key-for-eval",
            algorithm="HS256",
            token_expiry_hours=24,
            exempt_paths=["/health", "/api/v1/info", "/docs", "/openapi.json"],
        )

    def test_generate_and_verify_valid_token(self):
        """测试有效 token 的生成和验证"""
        token = self.middleware.generate_token(user_id="user-001", role="admin")
        assert token is not None
        assert isinstance(token, str)

        # token 格式应为 header.payload.signature
        parts = token.split(".")
        assert len(parts) == 3

        payload = self.middleware.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "user-001"
        assert payload["role"] == "admin"
        assert "iat" in payload
        assert "exp" in payload

    def test_token_with_extra_claims(self):
        """测试带额外声明的 token"""
        extra = {"department": "finance", "permissions": ["read", "write"]}
        token = self.middleware.generate_token(
            user_id="user-002", role="analyst", extra_claims=extra
        )
        payload = self.middleware.verify_token(token)
        assert payload is not None
        assert payload["department"] == "finance"
        assert payload["permissions"] == ["read", "write"]

    def test_expired_token_rejection(self):
        """测试过期 token 被拒绝"""
        # 创建一个已过期的中间件实例（过期时间设为负数）
        expired_middleware = JWTAuthMiddleware(
            secret_key="test-secret-key-for-eval",
            token_expiry_hours=-1,  # 已过期
        )
        token = expired_middleware.generate_token(user_id="user-003", role="user")
        payload = expired_middleware.verify_token(token)
        assert payload is None, "过期 token 应返回 None"

    def test_invalid_token_rejection_malformed(self):
        """测试格式错误的 token 被拒绝"""
        # 不是三段式
        assert self.middleware.verify_token("invalid.token") is None
        assert self.middleware.verify_token("not-even-a-token") is None
        assert self.middleware.verify_token("") is None
        assert self.middleware.verify_token("a.b.c.d") is None

    def test_invalid_token_rejection_wrong_signature(self):
        """测试签名错误的 token 被拒绝"""
        # 用不同的密钥生成 token
        other_middleware = JWTAuthMiddleware(secret_key="different-secret-key")
        token = other_middleware.generate_token(user_id="user-004", role="user")

        # 用当前中间件验证（密钥不同，签名应不匹配）
        payload = self.middleware.verify_token(token)
        assert payload is None, "错误签名的 token 应返回 None"

    def test_invalid_token_rejection_tampered_payload(self):
        """测试 payload 被篡改的 token 被拒绝"""
        token = self.middleware.generate_token(user_id="user-005", role="admin")
        header_b64, payload_b64, signature_b64 = token.split(".")

        # 篡改 payload（修改 base64 内容）
        import base64
        import json

        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64_padded = payload_b64 + "=" * padding
        else:
            payload_b64_padded = payload_b64
        payload_data = json.loads(base64.urlsafe_b64decode(payload_b64_padded))
        payload_data["role"] = "superadmin"
        tampered_b64 = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()

        tampered_token = f"{header_b64}.{tampered_b64}.{signature_b64}"
        assert self.middleware.verify_token(tampered_token) is None

    def test_exempt_paths(self):
        """测试免认证路径"""
        # 默认免认证路径
        assert self.middleware.is_exempt("/health") is True
        assert self.middleware.is_exempt("/api/v1/info") is True
        assert self.middleware.is_exempt("/docs") is True
        assert self.middleware.is_exempt("/openapi.json") is True

        # 非免认证路径
        assert self.middleware.is_exempt("/api/v1/evaluations") is False
        assert self.middleware.is_exempt("/api/v1/agents") is False
        assert self.middleware.is_exempt("/api/v1/reports") is False

    def test_exempt_path_prefix_matching(self):
        """测试免认证路径的前缀匹配"""
        middleware = JWTAuthMiddleware(
            exempt_paths=["/health", "/api/v1/public"]
        )
        assert middleware.is_exempt("/health") is True
        assert middleware.is_exempt("/health/check") is True
        assert middleware.is_exempt("/api/v1/public/data") is True
        assert middleware.is_exempt("/api/v1/private") is False

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self):
        """测试使用有效 token 进行认证"""
        token = self.middleware.generate_token(user_id="user-100", role="admin")
        success, user_info = await self.middleware.authenticate(token, "/api/v1/evaluations")
        assert success is True
        assert user_info is not None
        assert user_info["sub"] == "user-100"
        assert user_info["role"] == "admin"

    @pytest.mark.asyncio
    async def test_authenticate_exempt_path_without_token(self):
        """测试免认证路径无需 token"""
        success, user_info = await self.middleware.authenticate(None, "/health")
        assert success is True
        assert user_info == {"role": "anonymous"}

    @pytest.mark.asyncio
    async def test_authenticate_protected_path_without_token(self):
        """测试受保护路径无 token 时认证失败"""
        success, user_info = await self.middleware.authenticate(None, "/api/v1/evaluations")
        assert success is False
        assert user_info is None

    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_token(self):
        """测试使用无效 token 进行认证"""
        success, user_info = await self.middleware.authenticate(
            "invalid.token.here", "/api/v1/evaluations"
        )
        assert success is False
        assert user_info is None

    @pytest.mark.asyncio
    async def test_authenticate_with_expired_token(self):
        """测试使用过期 token 进行认证"""
        expired_middleware = JWTAuthMiddleware(
            secret_key="test-secret-key-for-eval",
            token_expiry_hours=-1,
        )
        token = expired_middleware.generate_token(user_id="user-expired", role="user")
        success, user_info = await expired_middleware.authenticate(token, "/api/v1/evaluations")
        assert success is False
        assert user_info is None

    def test_different_secret_keys_produce_different_tokens(self):
        """测试不同密钥产生不同 token"""
        m1 = JWTAuthMiddleware(secret_key="key-one")
        m2 = JWTAuthMiddleware(secret_key="key-two")

        token1 = m1.generate_token(user_id="user", role="admin")
        token2 = m2.generate_token(user_id="user", role="admin")

        assert token1 != token2

        # 交叉验证应失败
        assert m1.verify_token(token2) is None
        assert m2.verify_token(token1) is None


# ============================================================================
# 2. 限流中间件测试
# ============================================================================


class TestRateLimitMiddleware:
    """限流中间件测试套件"""

    def test_rate_limit_allows_within_threshold(self):
        """测试在阈值内允许请求"""
        config = RateLimitConfig(max_requests=5, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        for i in range(5):
            result = middleware.check_rate_limit("ip-192.168.1.1")
            assert result.allowed is True, f"第 {i+1} 个请求应被允许"
            assert result.remaining >= 0
            middleware.record_request("ip-192.168.1.1")

    def test_rate_limit_blocks_after_threshold(self):
        """测试超过阈值后阻止请求"""
        config = RateLimitConfig(max_requests=3, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        # 发送 3 个请求
        for _ in range(3):
            middleware.record_request("ip-10.0.0.1")

        # 第 4 个请求应被拒绝
        result = middleware.check_rate_limit("ip-10.0.0.1")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None
        assert result.retry_after > 0

    def test_rate_limit_remaining_decrements(self):
        """测试剩余请求计数递减"""
        config = RateLimitConfig(max_requests=5, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        for i in range(5):
            result = middleware.check_rate_limit("user-123")
            expected_remaining = 4 - i
            assert result.remaining == expected_remaining, (
                f"第 {i+1} 个请求后剩余应为 {expected_remaining}，实际为 {result.remaining}"
            )
            middleware.record_request("user-123")

    def test_rate_limit_different_keys(self):
        """测试不同限流键互不影响"""
        config = RateLimitConfig(max_requests=2, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        # 用 key1 发送 2 个请求
        middleware.record_request("ip-1.1.1.1")
        middleware.record_request("ip-1.1.1.1")

        # key1 应被限流
        assert middleware.check_rate_limit("ip-1.1.1.1").allowed is False

        # key2 应不受影响
        assert middleware.check_rate_limit("ip-2.2.2.2").allowed is True

        # key3 (user_id) 应不受影响
        assert middleware.check_rate_limit("user-alice").allowed is True

        # key4 (endpoint) 应不受影响
        assert middleware.check_rate_limit("endpoint-/api/v1/evaluations").allowed is True

    def test_rate_limit_window_expiration(self):
        """测试时间窗口过期后限流重置"""
        config = RateLimitConfig(max_requests=2, window_seconds=10)
        middleware = RateLimitMiddleware(config)

        base_time = 1000.0

        # 在窗口内发送 2 个请求
        middleware.record_request("ip-3.3.3.3", now=base_time)
        middleware.record_request("ip-3.3.3.3", now=base_time + 1)

        # 应被限流
        assert middleware.check_rate_limit("ip-3.3.3.3", now=base_time + 5).allowed is False

        # 窗口过期后（超过 10 秒），应重新允许
        assert middleware.check_rate_limit("ip-3.3.3.3", now=base_time + 15).allowed is True

    def test_rate_limit_partial_window_expiration(self):
        """测试部分窗口过期后计数减少"""
        config = RateLimitConfig(max_requests=5, window_seconds=10)
        middleware = RateLimitMiddleware(config)

        base_time = 2000.0

        # 在窗口内发送 4 个请求
        for i in range(4):
            middleware.record_request("ip-4.4.4.4", now=base_time + i)

        # 第 5 个应允许
        assert middleware.check_rate_limit("ip-4.4.4.4", now=base_time + 4).allowed is True

        # 记录第 5 个
        middleware.record_request("ip-4.4.4.4", now=base_time + 4)

        # 第 6 个应被拒绝
        assert middleware.check_rate_limit("ip-4.4.4.4", now=base_time + 4).allowed is False

        # 等待前 2 个请求过期
        assert middleware.check_rate_limit("ip-4.4.4.4", now=base_time + 12).allowed is True

    def test_rate_limit_result_fields(self):
        """测试限流结果字段完整性"""
        config = RateLimitConfig(max_requests=10, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        result = middleware.check_rate_limit("test-key")
        assert isinstance(result, RateLimitResult)
        assert result.allowed is True
        assert result.remaining == 9
        assert result.reset_at > 0
        assert result.retry_after is None
        assert result.limit == 10

    def test_rate_limit_blocked_result_fields(self):
        """测试被限流时的结果字段"""
        config = RateLimitConfig(max_requests=1, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        middleware.record_request("test-key", now=100.0)
        result = middleware.check_rate_limit("test-key", now=100.0)

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None
        assert result.retry_after > 0
        assert result.limit == 1

    def test_get_usage(self):
        """测试获取使用情况"""
        config = RateLimitConfig(max_requests=10, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        now = time.time()
        for i in range(3):
            middleware.record_request("usage-key", now=now + i)

        usage = middleware.get_usage("usage-key")
        assert usage["key"] == "usage-key"
        assert usage["requests_in_window"] == 3
        assert usage["max_requests"] == 10
        assert usage["window_seconds"] == 60
        assert abs(usage["utilization"] - 0.3) < 1e-9

    def test_cleanup_expired_keys(self):
        """测试清理过期数据"""
        config = RateLimitConfig(max_requests=10, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        middleware.record_request("old-key", now=100.0)
        middleware.record_request("new-key", now=time.time())

        # 清理超过 1 小时的数据
        middleware.cleanup(max_age=3600)

        # old-key 应被清理（如果当前时间远大于 100 + 3600）
        # new-key 应保留
        usage = middleware.get_usage("new-key")
        assert usage["requests_in_window"] >= 1

    def test_reset_specific_key(self):
        """测试重置特定键的限流"""
        config = RateLimitConfig(max_requests=2, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        middleware.record_request("key-a")
        middleware.record_request("key-a")
        middleware.record_request("key-b")

        # key-a 应被限流
        assert middleware.check_rate_limit("key-a").allowed is False

        # 重置 key-a
        middleware.reset("key-a")

        # key-a 应重新允许
        assert middleware.check_rate_limit("key-a").allowed is True

        # key-b 不受影响
        assert middleware.check_rate_limit("key-b").allowed is True

    def test_reset_all_keys(self):
        """测试重置所有限流"""
        config = RateLimitConfig(max_requests=1, window_seconds=60)
        middleware = RateLimitMiddleware(config)

        middleware.record_request("key-x")
        middleware.record_request("key-y")

        assert middleware.check_rate_limit("key-x").allowed is False
        assert middleware.check_rate_limit("key-y").allowed is False

        middleware.reset()

        assert middleware.check_rate_limit("key-x").allowed is True
        assert middleware.check_rate_limit("key-y").allowed is True

    def test_rate_limit_ip_key_strategy(self):
        """测试基于 IP 的限流策略"""
        config = RateLimitConfig(max_requests=3, window_seconds=60, key_func="ip")
        middleware = RateLimitMiddleware(config)

        # 不同 IP 独立计数
        for _ in range(3):
            middleware.record_request("192.168.1.100")

        assert middleware.check_rate_limit("192.168.1.100").allowed is False
        assert middleware.check_rate_limit("192.168.1.200").allowed is True

    def test_rate_limit_user_key_strategy(self):
        """测试基于用户 ID 的限流策略"""
        config = RateLimitConfig(max_requests=2, window_seconds=60, key_func="user_id")
        middleware = RateLimitMiddleware(config)

        middleware.record_request("user-alice")
        middleware.record_request("user-alice")

        assert middleware.check_rate_limit("user-alice").allowed is False
        assert middleware.check_rate_limit("user-bob").allowed is True

    def test_rate_limit_endpoint_key_strategy(self):
        """测试基于端点的限流策略"""
        config = RateLimitConfig(max_requests=2, window_seconds=60, key_func="endpoint")
        middleware = RateLimitMiddleware(config)

        middleware.record_request("/api/v1/evaluations")
        middleware.record_request("/api/v1/evaluations")

        assert middleware.check_rate_limit("/api/v1/evaluations").allowed is False
        assert middleware.check_rate_limit("/api/v1/reports").allowed is True


# ============================================================================
# 3. API 数据模型测试（依赖 pydantic，不依赖 fastapi）
# ============================================================================


class TestAPISchemas:
    """API 数据模型测试套件"""

    def test_evaluation_request_schema(self):
        """测试评测请求模型"""
        from finagent.api.schemas import EvaluationRequest

        req = EvaluationRequest(
            agent_id="agent-001",
            agent_type="langgraph",
            eval_mode="quick",
            task_count=10,
        )
        assert req.agent_id == "agent-001"
        assert req.agent_type == "langgraph"
        assert req.eval_mode == "quick"
        assert req.task_count == 10
        assert req.agent_config == {}
        assert req.dimensions is None

    def test_evaluation_request_defaults(self):
        """测试评测请求默认值"""
        from finagent.api.schemas import EvaluationRequest

        req = EvaluationRequest(agent_id="agent-002")
        assert req.agent_type == "langgraph"
        assert req.eval_mode == "full"
        assert req.agent_config == {}
        assert req.dimensions is None
        assert req.task_count is None
        assert req.endpoint_url is None
        assert req.headers is None

    def test_evaluation_response_schema(self):
        """测试评测响应模型"""
        from finagent.api.schemas import EvaluationResponse

        resp = EvaluationResponse(
            evaluation_id="eval-001",
            status="running",
            message="Evaluation started",
        )
        assert resp.evaluation_id == "eval-001"
        assert resp.status == "running"
        assert resp.created_at is not None

    def test_evaluation_result_summary(self):
        """测试评测结果摘要模型"""
        from finagent.api.schemas import EvaluationResultSummary

        summary = EvaluationResultSummary(
            overall_score=85.5,
            overall_rating="A",
            total_tasks=20,
            passed_tasks=17,
            pass_rate=0.85,
            veto_count=1,
        )
        assert summary.overall_score == 85.5
        assert summary.overall_rating == "A"
        assert summary.pass_rate == 0.85
        assert summary.veto_count == 1

    def test_agent_registration_request(self):
        """测试 Agent 注册请求模型"""
        from finagent.api.schemas import AgentRegistrationRequest

        req = AgentRegistrationRequest(
            agent_id="agent-reg-001",
            agent_name="FinanceAgent",
            agent_type="langgraph",
            description="A financial analysis agent",
            endpoint_url="http://localhost:8000",
        )
        assert req.agent_id == "agent-reg-001"
        assert req.agent_name == "FinanceAgent"
        assert req.config == {}

    def test_error_response_schema(self):
        """测试错误响应模型"""
        from finagent.api.schemas import ErrorResponse

        err = ErrorResponse(
            error="ValidationError",
            message="Invalid agent_id format",
            details={"field": "agent_id", "reason": "must be alphanumeric"},
        )
        assert err.error == "ValidationError"
        assert err.message == "Invalid agent_id format"
        assert err.details["field"] == "agent_id"
        assert err.timestamp is not None

    def test_pagination_params(self):
        """测试分页参数模型"""
        from finagent.api.schemas import PaginationParams

        params = PaginationParams(page=2, page_size=50)
        assert params.page == 2
        assert params.page_size == 50

    def test_pagination_params_defaults(self):
        """测试分页参数默认值"""
        from finagent.api.schemas import PaginationParams

        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20

    def test_pagination_params_validation(self):
        """测试分页参数验证"""
        from finagent.api.schemas import PaginationParams
        from pydantic import ValidationError

        # page < 1 应失败
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

        # page_size > 100 应失败
        with pytest.raises(ValidationError):
            PaginationParams(page_size=200)

    def test_adversarial_test_request(self):
        """测试对抗性测试请求模型"""
        from finagent.api.schemas import AdversarialTestRequest

        req = AdversarialTestRequest(agent_id="agent-adv-001")
        assert req.agent_id == "agent-adv-001"
        assert len(req.levels) == 4
        assert len(req.attack_types) == 4
        assert req.attacks_per_level == 10

    def test_report_request(self):
        """测试报告请求模型"""
        from finagent.api.schemas import ReportRequest

        req = ReportRequest(evaluation_id="eval-001", format="markdown")
        assert req.evaluation_id == "eval-001"
        assert req.format == "markdown"
        assert req.include_details is True

    def test_dataset_info(self):
        """测试数据集信息模型"""
        from finagent.api.schemas import DatasetInfo

        info = DatasetInfo(
            name="bizfinbench",
            description="Business finance benchmark dataset",
            task_count=50,
        )
        assert info.name == "bizfinbench"
        assert info.version == "1.0"


# ============================================================================
# 4. 指标采集集成测试
# ============================================================================


class TestMetricsCollectionIntegration:
    """指标采集集成测试 — 验证评测生命周期中的指标记录"""

    def setup_method(self):
        """每个测试方法前初始化采集器"""
        self.metrics = MetricsCollector()

    def teardown_method(self):
        """每个测试方法后清理"""
        self.metrics.reset()

    def test_record_evaluation_lifecycle(self):
        """测试评测生命周期指标记录"""
        agent_id = "test-agent-001"
        eval_mode = "quick"

        # 记录评测开始
        self.metrics.record_evaluation_start(agent_id, eval_mode)

        # 验证计数器递增
        total = self.metrics.get_counter(
            "finagent_evaluations_total",
            labels={"agent_id": agent_id, "mode": eval_mode},
        )
        assert total == 1.0

        # 验证活跃评测数
        active = self.metrics.get_gauge("finagent_evaluations_active")
        assert active == 1.0

        # 记录评测完成
        self.metrics.record_evaluation_complete(
            agent_id=agent_id,
            eval_mode=eval_mode,
            success=True,
            duration_s=12.5,
        )

        # 活跃数应减少
        active = self.metrics.get_gauge("finagent_evaluations_active")
        assert active == 0.0

        # 完成计数器应递增
        completed = self.metrics.get_counter(
            "finagent_evaluations_completed_total",
            labels={"agent_id": agent_id, "mode": eval_mode, "status": "success"},
        )
        assert completed == 1.0

        # 耗时应被记录
        stats = self.metrics.get_histogram_stats(
            "finagent_evaluation_duration_seconds",
            labels={"agent_id": agent_id, "mode": eval_mode},
        )
        assert stats["count"] == 1
        assert stats["avg"] == 12.5

    def test_record_evaluation_failure(self):
        """测试评测失败时的指标记录"""
        agent_id = "test-agent-002"
        eval_mode = "full"

        self.metrics.record_evaluation_start(agent_id, eval_mode)
        self.metrics.record_evaluation_complete(
            agent_id=agent_id,
            eval_mode=eval_mode,
            success=False,
            duration_s=5.0,
        )

        completed = self.metrics.get_counter(
            "finagent_evaluations_completed_total",
            labels={"agent_id": agent_id, "mode": eval_mode, "status": "failure"},
        )
        assert completed == 1.0

        # 成功计数应为 0
        success_count = self.metrics.get_counter(
            "finagent_evaluations_completed_total",
            labels={"agent_id": agent_id, "mode": eval_mode, "status": "success"},
        )
        assert success_count == 0.0

    def test_record_llm_call_metrics(self):
        """测试 LLM 调用指标记录"""
        model = "gpt-4"

        self.metrics.record_llm_call(
            model=model,
            latency_ms=250.0,
            tokens=1500,
            cost_usd=0.045,
        )

        # 调用计数
        calls = self.metrics.get_counter(
            "finagent_llm_calls_total", labels={"model": model}
        )
        assert calls == 1.0

        # 延迟记录
        latency_stats = self.metrics.get_histogram_stats(
            "finagent_llm_latency_ms", labels={"model": model}
        )
        assert latency_stats["count"] == 1
        assert latency_stats["avg"] == 250.0

        # Token 计数
        tokens = self.metrics.get_counter(
            "finagent_llm_tokens_total", labels={"model": model}
        )
        assert tokens == 1500.0

        # 成本计数
        cost = self.metrics.get_counter(
            "finagent_llm_cost_usd_total", labels={"model": model}
        )
        assert cost == 0.045

    def test_record_multiple_llm_calls(self):
        """测试多次 LLM 调用的指标聚合"""
        model = "claude-3-opus"

        for latency in [100.0, 200.0, 300.0, 400.0, 500.0]:
            self.metrics.record_llm_call(
                model=model, latency_ms=latency, tokens=500, cost_usd=0.01
            )

        calls = self.metrics.get_counter(
            "finagent_llm_calls_total", labels={"model": model}
        )
        assert calls == 5.0

        stats = self.metrics.get_histogram_stats(
            "finagent_llm_latency_ms", labels={"model": model}
        )
        assert stats["count"] == 5
        assert stats["min"] == 100.0
        assert stats["max"] == 500.0
        assert stats["avg"] == 300.0
        assert stats["p50"] == 300.0

    def test_record_mcp_tool_call(self):
        """测试 MCP 工具调用指标记录"""
        self.metrics.record_mcp_call(
            server="yahoo_finance", tool="get_stock_price", success=True
        )

        success_calls = self.metrics.get_counter(
            "finagent_mcp_tool_calls_total",
            labels={"server": "yahoo_finance", "tool": "get_stock_price", "status": "success"},
        )
        assert success_calls == 1.0

        # 失败调用
        self.metrics.record_mcp_call(
            server="yahoo_finance", tool="get_stock_price", success=False
        )

        failure_calls = self.metrics.get_counter(
            "finagent_mcp_tool_calls_total",
            labels={"server": "yahoo_finance", "tool": "get_stock_price", "status": "failure"},
        )
        assert failure_calls == 1.0

    def test_record_mcp_health(self):
        """测试 MCP 健康状态记录"""
        self.metrics.record_mcp_health("yahoo_finance", healthy=True)
        self.metrics.record_mcp_health("sec_edgar", healthy=False)

        assert self.metrics.get_gauge(
            "finagent_mcp_server_up", labels={"server": "yahoo_finance"}
        ) == 1.0

        assert self.metrics.get_gauge(
            "finagent_mcp_server_up", labels={"server": "sec_edgar"}
        ) == 0.0

    def test_full_evaluation_lifecycle_with_metrics(self):
        """测试完整评测生命周期（含 LLM 和 MCP 调用）的指标"""
        agent_id = "lifecycle-agent"
        eval_mode = "full"

        # 1. 评测开始
        self.metrics.record_evaluation_start(agent_id, eval_mode)

        # 2. 模拟 LLM 调用
        self.metrics.record_llm_call("gpt-4", 200.0, 1000, 0.03)
        self.metrics.record_llm_call("gpt-4", 150.0, 800, 0.024)

        # 3. 模拟 MCP 工具调用
        self.metrics.record_mcp_call("yahoo_finance", "get_stock_price", True)
        self.metrics.record_mcp_call("sec_edgar", "search_filings", True)
        self.metrics.record_mcp_call("yahoo_finance", "get_stock_price", False)

        # 4. MCP 健康检查
        self.metrics.record_mcp_health("yahoo_finance", True)
        self.metrics.record_mcp_health("sec_edgar", True)

        # 5. 评测完成
        self.metrics.record_evaluation_complete(agent_id, eval_mode, True, 30.0)

        # 验证所有指标
        all_metrics = self.metrics.get_all_metrics()

        # 应有计数器
        assert len(all_metrics["counters"]) > 0

        # 应有仪表值
        assert all_metrics["gauges"].get("finagent_evaluations_active") == 0.0

        # 应有直方图数据
        assert len(all_metrics["histograms"]) > 0

        # Prometheus 格式导出应包含关键指标
        prom_output = self.metrics.render_prometheus()
        assert "finagent_evaluations_total" in prom_output
        assert "finagent_llm_calls_total" in prom_output
        assert "finagent_mcp_tool_calls_total" in prom_output
        assert "finagent_evaluation_duration_seconds" in prom_output

    def test_metrics_reset(self):
        """测试指标重置"""
        self.metrics.record_evaluation_start("agent-reset", "quick")
        self.metrics.record_llm_call("gpt-4", 100.0, 500, 0.01)

        assert len(self.metrics.get_all_metrics()["counters"]) > 0

        self.metrics.reset()

        all_metrics = self.metrics.get_all_metrics()
        assert len(all_metrics["counters"]) == 0
        assert len(all_metrics["gauges"]) == 0
        assert len(all_metrics["histograms"]) == 0

    def test_metrics_labels_isolation(self):
        """测试不同标签的指标隔离"""
        self.metrics.record_evaluation_start("agent-a", "quick")
        self.metrics.record_evaluation_start("agent-b", "full")

        count_a = self.metrics.get_counter(
            "finagent_evaluations_total",
            labels={"agent_id": "agent-a", "mode": "quick"},
        )
        count_b = self.metrics.get_counter(
            "finagent_evaluations_total",
            labels={"agent_id": "agent-b", "mode": "full"},
        )

        assert count_a == 1.0
        assert count_b == 1.0

    def test_concurrent_evaluations_active_gauge(self):
        """测试并发评测时活跃数仪表值"""
        self.metrics.record_evaluation_start("agent-c1", "quick")
        self.metrics.record_evaluation_start("agent-c2", "quick")
        self.metrics.record_evaluation_start("agent-c3", "quick")

        assert self.metrics.get_gauge("finagent_evaluations_active") == 3.0

        self.metrics.record_evaluation_complete("agent-c1", "quick", True, 10.0)
        assert self.metrics.get_gauge("finagent_evaluations_active") == 2.0

        self.metrics.record_evaluation_complete("agent-c2", "quick", False, 5.0)
        assert self.metrics.get_gauge("finagent_evaluations_active") == 1.0

        self.metrics.record_evaluation_complete("agent-c3", "quick", True, 15.0)
        assert self.metrics.get_gauge("finagent_evaluations_active") == 0.0

        # 活跃数不应降为负数
        self.metrics.record_evaluation_complete("agent-c3", "quick", True, 1.0)
        assert self.metrics.get_gauge("finagent_evaluations_active") == 0.0
