"""
Financial Agent Interface - 异常体系定义

对应需求: FR-001-11
"""


class EvaluationError(Exception):
    """
    评测异常基类。

    所有评测相关的异常都继承此类。
    """

    def __init__(self, message: str, error_code: str = "EVAL_UNKNOWN"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"

    def to_dict(self) -> dict:
        """转换为字典格式，用于 API 响应"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "exception_type": self.__class__.__name__,
        }


class TaskTimeoutError(EvaluationError):
    """
    任务超时异常。

    当评测任务执行时间超过 time_limit_seconds 时抛出。
    """

    def __init__(self, task_id: str, timeout_seconds: int):
        super().__init__(
            message=f"Task {task_id} timed out after {timeout_seconds}s", error_code="EVAL_TIMEOUT"
        )
        self.task_id = task_id
        self.timeout_seconds = timeout_seconds

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update(
            {
                "task_id": self.task_id,
                "timeout_seconds": self.timeout_seconds,
            }
        )
        return result


class AgentExecutionError(EvaluationError):
    """
    Agent 执行异常。

    当被测 Agent 执行过程中发生错误时抛出。
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AGENT_ERROR",
        recoverable: bool = False,
        task_id: str | None = None,
    ):
        super().__init__(message, error_code)
        self.recoverable = recoverable
        self.task_id = task_id

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update(
            {
                "recoverable": self.recoverable,
                "task_id": self.task_id,
            }
        )
        return result


class ToolCallError(EvaluationError):
    """
    工具调用异常。

    当工具调用失败时抛出。
    """

    def __init__(
        self,
        tool_name: str,
        error: str,
        task_id: str | None = None,
    ):
        super().__init__(
            message=f"Tool call failed: {tool_name} - {error}", error_code="TOOL_ERROR"
        )
        self.tool_name = tool_name
        self.error = error
        self.task_id = task_id

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update(
            {
                "tool_name": self.tool_name,
                "error": self.error,
                "task_id": self.task_id,
            }
        )
        return result


class EnvironmentError(EvaluationError):
    """
    评测环境异常。

    当评测环境（MCP 服务器、数据库等）发生错误时抛出。
    """

    def __init__(self, component: str, error: str):
        super().__init__(
            message=f"Environment error: {component} - {error}", error_code="ENV_ERROR"
        )
        self.component = component
        self.error = error

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update(
            {
                "component": self.component,
                "error": self.error,
            }
        )
        return result


class MCPConnectionError(EnvironmentError):
    """
    MCP 服务器连接异常。
    """

    def __init__(self, server_name: str, error: str):
        super().__init__(component=f"MCP Server: {server_name}", error=error)
        self.error_code = "MCP_CONNECTION_ERROR"
        self.server_name = server_name


class DatabaseError(EnvironmentError):
    """
    数据库异常。
    """

    def __init__(self, error: str):
        super().__init__(component="Database", error=error)
        self.error_code = "DB_ERROR"


class ValidationError(EvaluationError):
    """
    数据验证异常。

    当输入数据不符合预期格式时抛出。
    """

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Validation error: {field} - {reason}", error_code="VALIDATION_ERROR"
        )
        self.field = field
        self.reason = reason

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update(
            {
                "field": self.field,
                "reason": self.reason,
            }
        )
        return result


class ScoringError(EvaluationError):
    """
    评分异常。

    当评分过程中发生错误时抛出。
    """

    def __init__(self, dimension: str, reason: str):
        super().__init__(
            message=f"Scoring error in dimension '{dimension}': {reason}",
            error_code="SCORING_ERROR",
        )
        self.dimension = dimension
        self.reason = reason

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update(
            {
                "dimension": self.dimension,
                "reason": self.reason,
            }
        )
        return result


class LLMJudgeError(ScoringError):
    """
    LLM Judge 评分异常。
    """

    def __init__(self, reason: str, model: str | None = None):
        super().__init__(dimension="llm_judge", reason=reason)
        self.error_code = "LLM_JUDGE_ERROR"
        self.model = model

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update(
            {
                "model": self.model,
            }
        )
        return result
