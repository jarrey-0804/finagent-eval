"""
REST API 模块

提供评测系统的REST API接口。
"""

__all__ = [
    "create_app",
    "AppConfig",
    "EvaluationRouter",
    "AgentRouter",
    "TaskRouter",
    "ReportRouter",
    "EvaluationRequest",
    "EvaluationResponse",
    "AgentRegistrationRequest",
    "TaskGenerationRequest",
    "ReportRequest",
]


def __getattr__(name):
    if name in __all__:
        if name in ("create_app", "AppConfig"):
            from .app import AppConfig, create_app
            return create_app if name == "create_app" else AppConfig
        if name in ("EvaluationRouter", "AgentRouter", "TaskRouter", "ReportRouter"):
            from .routes import (
                AgentRouter,
                EvaluationRouter,
                ReportRouter,
                TaskRouter,
            )
            return {
                "EvaluationRouter": EvaluationRouter,
                "AgentRouter": AgentRouter,
                "TaskRouter": TaskRouter,
                "ReportRouter": ReportRouter,
            }[name]
        if name in ("EvaluationRequest", "EvaluationResponse",
                     "AgentRegistrationRequest", "TaskGenerationRequest",
                     "ReportRequest"):
            from .schemas import (
                AgentRegistrationRequest,
                EvaluationRequest,
                EvaluationResponse,
                ReportRequest,
                TaskGenerationRequest,
            )
            return {
                "EvaluationRequest": EvaluationRequest,
                "EvaluationResponse": EvaluationResponse,
                "AgentRegistrationRequest": AgentRegistrationRequest,
                "TaskGenerationRequest": TaskGenerationRequest,
                "ReportRequest": ReportRequest,
            }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
