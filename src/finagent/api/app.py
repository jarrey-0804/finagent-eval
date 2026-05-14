"""
FastAPI 应用核心

提供REST API服务的主应用。
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..interface.exceptions import EvaluationError
from ..pipeline.checkpointer import CheckpointConfig, PostgresCheckpointer
from .middleware.auth import JWTAuthMiddleware
from .middleware.ratelimit import RateLimitConfig, RateLimitMiddleware
from .middleware.responsetime import ResponseTimeConfig, ResponseTimeMiddleware, ResponseTimeTracker


@dataclass
class AppConfig:
    """应用配置"""

    title: str = "金融AI Agent评测系统 API"
    version: str = "1.0.0"
    description: str = "提供金融AI Agent的标准化评测服务"

    # 数据库配置
    database_url: str = "postgresql://localhost/finagent_eval"

    # CORS配置
    cors_origins: list[str] | None = None
    cors_methods: list[str] | None = None

    # 响应时间配置
    response_timeout_ms: float = 5000.0  # 单请求硬超时 5s
    p95_threshold_ms: float = 500.0  # P95 告警阈值 500ms (SRS NFR-P-03)
    enable_response_timeout: bool = True  # 是否启用超时强制中断

    # 调试模式
    debug: bool = False

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["*"]
        if self.cors_methods is None:
            self.cors_methods = ["*"]


# 全局状态
class AppState:
    """应用状态"""

    checkpointer: PostgresCheckpointer | None = None
    pipelines: dict = {}


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    config = app.state.config
    app_state.checkpointer = PostgresCheckpointer(
        CheckpointConfig(database_url=config.database_url)
    )
    await app_state.checkpointer.initialize()

    yield

    # 关闭时清理
    if app_state.checkpointer:
        await app_state.checkpointer.close()


def create_app(config: AppConfig | None = None) -> FastAPI:
    """创建FastAPI应用"""

    config = config or AppConfig()

    app = FastAPI(
        title=config.title,
        version=config.version,
        description=config.description,
        lifespan=lifespan,
    )

    # 存储配置
    app.state.config = config

    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins or [],
        allow_credentials=True,
        allow_methods=config.cors_methods or [],
        allow_headers=["*"],
    )

    # 添加JWT认证中间件
    jwt_auth = JWTAuthMiddleware(
        exempt_paths=["/health", "/docs", "/openapi.json", "/metrics"],
    )

    @app.middleware("http")
    async def jwt_auth_middleware(request: Request, call_next):
        token = (
            request.headers.get("Authorization", "").replace("Bearer ", "")
            if request.headers.get("Authorization")
            else None
        )
        authenticated, user_info = await jwt_auth.authenticate(token, request.url.path)
        if not authenticated:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "message": "无效或缺失的认证令牌"},
            )
        request.state.user = user_info
        response = await call_next(request)
        return response

    # 添加响应时间监控中间件 (NFR-P-03: P95 < 500ms)
    rt_config = ResponseTimeConfig(
        timeout_ms=config.response_timeout_ms,
        p95_threshold_ms=config.p95_threshold_ms,
        enable_timeout=config.enable_response_timeout,
    )
    rt_tracker = ResponseTimeTracker(rt_config)
    rt_middleware = ResponseTimeMiddleware(rt_tracker)
    app.state.response_time_tracker = rt_tracker

    @app.middleware("http")
    async def response_time_middleware(request: Request, call_next):
        return await rt_middleware(request, call_next)

    # 添加限流中间件 (滑动窗口: 100请求/60秒)
    rl_config = RateLimitConfig(max_requests=100, window_seconds=60, burst_size=10)
    rl_middleware = RateLimitMiddleware(rl_config)
    app.state.rate_limiter = rl_middleware

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # 豁免健康检查和文档路径
        if request.url.path in ("/health", "/ready", "/live", "/docs", "/openapi.json", "/metrics"):
            return await call_next(request)
        # 获取限流键（优先使用用户ID，否则使用IP）
        key = (
            getattr(request.state, "user", {}).get("user_id", None)
            if hasattr(request.state, "user")
            else None
        )
        if not key:
            key = request.client.host if request.client else "unknown"
        result = rl_middleware.check_rate_limit(key)
        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求频率超过限制，请稍后重试",
                    "retry_after": result.retry_after,
                },
                headers={"Retry-After": str(int(result.retry_after)) if result.retry_after is not None else "0"},
            )
        rl_middleware.record_request(key)
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        return response

    # 注册路由
    from .routes import register_routes

    register_routes(app)

    # WebSocket 实时评测进度
    from .websocket import manager as ws_manager

    @app.websocket("/ws/evaluation/{evaluation_id}")
    async def evaluation_websocket(websocket: WebSocket, evaluation_id: str):
        await websocket.accept()
        await ws_manager.connect(evaluation_id, websocket)
        try:
            while True:
                # Keep connection alive, receive any client messages
                data = await websocket.receive_text()
                # Client can send "ping" to keep alive
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            await ws_manager.disconnect(evaluation_id, websocket)

    # 注册异常处理器
    @app.exception_handler(EvaluationError)
    async def evaluation_exception_handler(
        request: Request,
        exc: EvaluationError,
    ):
        return JSONResponse(
            status_code=400,
            content={
                "error": exc.__class__.__name__,
                "message": str(exc),
                "details": exc.details if hasattr(exc, "details") else None,
            },
        )

    # 全局异常处理器 - 捕获所有未处理的异常
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误，请稍后重试",
                "details": str(exc) if app.state.config.debug else None,
            },
        )

    # 健康检查端点
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": config.version}

    # 就绪检查端点：检查数据库连通性
    @app.get("/ready")
    async def readiness_check():
        try:
            if app_state.checkpointer is not None:
                # 尝试简单的数据库连通性检查
                await app_state.checkpointer.initialize()
                return {"status": "ready"}
            return {"status": "not_ready", "reason": "checkpointer not initialized"}
        except Exception:
            return {"status": "not_ready"}

    # 存活检查端点：进程存活即返回200
    @app.get("/live")
    async def liveness_check():
        return {"status": "alive"}

    # API信息端点
    @app.get("/api/v1/info")
    async def api_info():
        return {
            "name": config.title,
            "version": config.version,
            "endpoints": {
                "evaluation": "/api/v1/evaluation",
                "agents": "/api/v1/agents",
                "tasks": "/api/v1/tasks",
                "reports": "/api/v1/reports",
            },
        }

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    config: AppConfig | None = None,
):
    """运行API服务器"""
    app = create_app(config)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
