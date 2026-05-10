"""
通用工具审计器

框架无关的工具调用审计，记录和分析Agent的工具使用行为。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .._compat import StrEnum


class AuditLevel(StrEnum):
    """审计级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ToolCallStatus(StrEnum):
    """工具调用状态"""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    INVALID_INPUT = "invalid_input"


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    record_id: str
    evaluation_id: str
    task_id: str
    agent_id: str

    # 工具信息
    tool_name: str
    tool_category: str | None = None  # mcp | internal | external

    # 调用信息
    input_args: dict = field(default_factory=dict)
    output_result: Any = None
    status: ToolCallStatus = ToolCallStatus.SUCCESS
    error_message: str | None = None

    # 性能信息
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    duration_ms: float = 0.0

    # 审计信息
    audit_level: AuditLevel = AuditLevel.INFO
    audit_notes: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "evaluation_id": self.evaluation_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "tool_category": self.tool_category,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "audit_level": self.audit_level.value,
            "audit_notes": self.audit_notes,
        }


@dataclass
class AuditReport:
    """审计报告"""
    evaluation_id: str
    agent_id: str
    total_calls: int
    success_count: int
    failure_count: int
    timeout_count: int
    total_duration_ms: float
    avg_duration_ms: float
    tool_usage_stats: dict[str, dict]
    issues: list[dict]
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_calls if self.total_calls > 0 else 0.0


class AuditConfig:
    """审计配置"""

    def __init__(
        self,
        max_records: int = 10000,
        enable_persistence: bool = False,
        audit_sensitive_args: bool = True,
        sensitive_fields: list[str] | None = None,
    ):
        self.max_records = max_records
        self.enable_persistence = enable_persistence
        self.audit_sensitive_args = audit_sensitive_args
        self.sensitive_fields = sensitive_fields or [
            "api_key", "password", "token", "secret",
            "api_key", "access_key", "private_key",
        ]


class UniversalToolAuditor:
    """
    通用工具审计器

    框架无关的工具调用审计，支持：
    - 工具调用记录
    - 敏感参数过滤
    - 性能监控
    - 异常检测
    - 审计报告生成
    """

    def __init__(self, config: AuditConfig | None = None):
        self.config = config or AuditConfig()
        self._records: list[ToolCallRecord] = []

    def record_call(
        self,
        evaluation_id: str,
        task_id: str,
        agent_id: str,
        tool_name: str,
        input_args: dict,
        output_result: Any = None,
        status: ToolCallStatus = ToolCallStatus.SUCCESS,
        error_message: str | None = None,
        duration_ms: float = 0.0,
        tool_category: str | None = None,
    ) -> ToolCallRecord:
        """记录工具调用"""
        import uuid

        # 过滤敏感参数
        filtered_args = self._filter_sensitive_args(input_args)

        record = ToolCallRecord(
            record_id=str(uuid.uuid4()),
            evaluation_id=evaluation_id,
            task_id=task_id,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_category=tool_category,
            input_args=filtered_args,
            output_result=self._truncate_output(output_result),
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
        )

        # 自动审计检查
        self._auto_audit(record)

        self._records.append(record)

        # 限制记录数
        if len(self._records) > self.config.max_records:
            self._records = self._records[-self.config.max_records:]

        return record

    def get_records(
        self,
        evaluation_id: str | None = None,
        task_id: str | None = None,
        tool_name: str | None = None,
        status: ToolCallStatus | None = None,
    ) -> list[ToolCallRecord]:
        """查询审计记录"""
        records = self._records

        if evaluation_id:
            records = [r for r in records if r.evaluation_id == evaluation_id]
        if task_id:
            records = [r for r in records if r.task_id == task_id]
        if tool_name:
            records = [r for r in records if r.tool_name == tool_name]
        if status:
            records = [r for r in records if r.status == status]

        return records

    def generate_report(
        self,
        evaluation_id: str,
        agent_id: str | None = None,
    ) -> AuditReport:
        """生成审计报告"""
        records = self._collect_audit_records(evaluation_id, agent_id)
        total, success, failure, timeout = self._calculate_status_counts(records)
        total_duration, avg_duration = self._calculate_duration_stats(records, total)
        tool_stats = self._build_tool_usage_stats(records)
        issues = self._collect_issues(records)

        return AuditReport(
            evaluation_id=evaluation_id,
            agent_id=agent_id or "unknown",
            total_calls=total,
            success_count=success,
            failure_count=failure,
            timeout_count=timeout,
            total_duration_ms=total_duration,
            avg_duration_ms=avg_duration,
            tool_usage_stats=tool_stats,
            issues=issues,
        )

    def _collect_audit_records(
        self,
        evaluation_id: str,
        agent_id: str | None,
    ) -> list[ToolCallRecord]:
        """收集并过滤审计记录。

        根据 evaluation_id 和可选的 agent_id 筛选审计记录。

        Args:
            evaluation_id: 评估ID
            agent_id: 可选的Agent ID，用于进一步过滤

        Returns:
            过滤后的审计记录列表
        """
        records = self.get_records(evaluation_id=evaluation_id)
        if agent_id:
            records = [r for r in records if r.agent_id == agent_id]
        return records

    def _calculate_status_counts(
        self,
        records: list[ToolCallRecord],
    ) -> tuple[int, int, int, int]:
        """计算各状态的调用计数。

        Args:
            records: 审计记录列表

        Returns:
            包含 (总数, 成功数, 失败数, 超时数) 的元组
        """
        total = len(records)
        success = sum(1 for r in records if r.status == ToolCallStatus.SUCCESS)
        failure = sum(1 for r in records if r.status == ToolCallStatus.FAILURE)
        timeout = sum(1 for r in records if r.status == ToolCallStatus.TIMEOUT)
        return total, success, failure, timeout

    def _calculate_duration_stats(
        self,
        records: list[ToolCallRecord],
        total: int,
    ) -> tuple[float, float]:
        """计算时长统计信息。

        Args:
            records: 审计记录列表
            total: 记录总数

        Returns:
            包含 (总时长ms, 平均时长ms) 的元组
        """
        total_duration = sum(r.duration_ms for r in records)
        avg_duration = total_duration / total if total > 0 else 0.0
        return total_duration, avg_duration

    def _build_tool_usage_stats(
        self,
        records: list[ToolCallRecord],
    ) -> dict[str, dict]:
        """构建工具使用统计。

        遍历审计记录，按工具名称聚合调用次数、成功/失败数和时长信息。

        Args:
            records: 审计记录列表

        Returns:
            以工具名称为键的统计字典
        """
        tool_stats: dict[str, dict] = {}
        for r in records:
            if r.tool_name not in tool_stats:
                tool_stats[r.tool_name] = {
                    "call_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "total_duration_ms": 0.0,
                    "avg_duration_ms": 0.0,
                }
            stats = tool_stats[r.tool_name]
            stats["call_count"] += 1
            if r.status == ToolCallStatus.SUCCESS:
                stats["success_count"] += 1
            else:
                stats["failure_count"] += 1
            stats["total_duration_ms"] += r.duration_ms

        for stats in tool_stats.values():
            if stats["call_count"] > 0:
                stats["avg_duration_ms"] = (
                    stats["total_duration_ms"] / stats["call_count"]
                )

        return tool_stats

    def _collect_issues(
        self,
        records: list[ToolCallRecord],
    ) -> list[dict]:
        """收集审计问题。

        从审计记录中提取 WARNING、ERROR 和 CRITICAL 级别的问题。

        Args:
            records: 审计记录列表

        Returns:
            问题字典列表，每个字典包含 record_id、tool_name、level 和 notes
        """
        issues = []
        for r in records:
            if r.audit_level in (AuditLevel.WARNING, AuditLevel.ERROR, AuditLevel.CRITICAL):
                issues.append({
                    "record_id": r.record_id,
                    "tool_name": r.tool_name,
                    "level": r.audit_level.value,
                    "notes": r.audit_notes,
                })
        return issues

    def clear_records(self, evaluation_id: str | None = None):
        """清除审计记录"""
        if evaluation_id:
            self._records = [
                r for r in self._records
                if r.evaluation_id != evaluation_id
            ]
        else:
            self._records.clear()

    def _filter_sensitive_args(self, args: dict) -> dict:
        """过滤敏感参数"""
        if not self.config.audit_sensitive_args:
            return args

        filtered = {}
        for key, value in args.items():
            if key.lower() in [f.lower() for f in self.config.sensitive_fields]:
                filtered[key] = "***REDACTED***"
            elif isinstance(value, dict):
                filtered[key] = self._filter_sensitive_args(value)
            else:
                filtered[key] = value

        return filtered

    def _truncate_output(self, output: Any, max_length: int = 1000) -> Any:
        """截断输出"""
        if isinstance(output, str) and len(output) > max_length:
            return output[:max_length] + "...(truncated)"
        return output

    def _auto_audit(self, record: ToolCallRecord):
        """自动审计检查"""
        # 检查超时
        if record.duration_ms > 10000:
            record.audit_level = AuditLevel.WARNING
            record.audit_notes.append(f"工具调用耗时过长: {record.duration_ms:.0f}ms")

        # 检查失败
        if record.status == ToolCallStatus.FAILURE:
            record.audit_level = AuditLevel.ERROR
            record.audit_notes.append(f"工具调用失败: {record.error_message}")

        # 检查权限拒绝
        if record.status == ToolCallStatus.PERMISSION_DENIED:
            record.audit_level = AuditLevel.CRITICAL
            record.audit_notes.append("工具权限被拒绝，可能存在安全风险")

        # 检查可疑工具名
        suspicious_tools = ["eval", "exec", "system", "shell", "delete_all"]
        if any(s in record.tool_name.lower() for s in suspicious_tools):
            if record.audit_level.value < AuditLevel.WARNING.value:
                record.audit_level = AuditLevel.WARNING
            record.audit_notes.append(f"使用可疑工具: {record.tool_name}")
