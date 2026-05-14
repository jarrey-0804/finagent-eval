"""
Prometheus 指标采集器

实现 4 类核心监控指标：
1. 评测指标（总数、成功率、耗时）
2. 系统指标（CPU、内存、并发数）
3. LLM 指标（调用次数、延迟、成本）
4. MCP 指标（服务器可用性、工具调用次数）
"""

import time
from dataclasses import dataclass, field


@dataclass
class MetricsConfig:
    """指标配置"""

    enabled: bool = True
    collection_interval: int = 15  # 采集间隔(秒)
    retention_hours: int = 24  # 数据保留时间(小时)


@dataclass
class MetricPoint:
    """指标数据点"""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """
    Prometheus 格式指标采集器
    """

    def __init__(self, config: MetricsConfig | None = None):
        self.config = config or MetricsConfig()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._labels: dict[str, dict[str, str]] = {}

    # ---- 计数器操作 ----

    def increment_counter(self, name: str, value: float = 1.0, labels: dict | None = None):
        """递增计数器"""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value
        if labels:
            self._labels[key] = labels

    def get_counter(self, name: str, labels: dict | None = None) -> float:
        """获取计数器值"""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0.0)

    # ---- 仪表盘操作 ----

    def set_gauge(self, name: str, value: float, labels: dict | None = None):
        """设置仪表值"""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        if labels:
            self._labels[key] = labels

    def get_gauge(self, name: str, labels: dict | None = None) -> float:
        """获取仪表值"""
        key = self._make_key(name, labels)
        return self._gauges.get(key, 0.0)

    # ---- 直方图操作 ----

    def observe(self, name: str, value: float, labels: dict | None = None):
        """记录观测值"""
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        if labels:
            self._labels[key] = labels

    def get_histogram_stats(self, name: str, labels: dict | None = None) -> dict:
        """获取直方图统计"""
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])

        if not values:
            return {"count": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        return {
            "count": n,
            "avg": sum(sorted_vals) / n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "p50": sorted_vals[int(n * 0.5)],
            "p95": sorted_vals[min(int(n * 0.95), n - 1)],
            "p99": sorted_vals[min(int(n * 0.99), n - 1)],
        }

    # ---- Prometheus 格式导出 ----

    def render_prometheus(self) -> str:
        """导出 Prometheus 文本格式"""
        lines = []

        # 计数器
        for key, value in self._counters.items():
            name, labels_str = self._parse_key(key)
            label_str = self._format_labels(labels_str)
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{label_str} {value}")

        # 仪表
        for key, value in self._gauges.items():
            name, labels_str = self._parse_key(key)
            label_str = self._format_labels(labels_str)
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{label_str} {value}")

        # 直方图摘要
        for key, values in self._histograms.items():
            name, labels_str = self._parse_key(key)
            label_str = self._format_labels(labels_str)
            lines.append(f"# TYPE {name} summary")
            stats = self._get_percentiles(values)
            for q, v in stats.items():
                lines.append(f'{name}{{quantile="{q}"{label_str[1:-1] if label_str else ""}}} {v}')
            lines.append(f"{name}_count{label_str} {len(values)}")
            lines.append(f"{name}_sum{label_str} {sum(values)}")

        return "\n".join(lines) + "\n"

    # ---- 便捷方法 ----

    def record_evaluation_start(self, agent_id: str, eval_mode: str):
        """记录评测开始"""
        self.increment_counter(
            "finagent_evaluations_total", labels={"agent_id": agent_id, "mode": eval_mode}
        )
        self.set_gauge(
            "finagent_evaluations_active", self.get_gauge("finagent_evaluations_active") + 1
        )

    def record_evaluation_complete(
        self, agent_id: str, eval_mode: str, success: bool, duration_s: float
    ):
        """记录评测完成"""
        self.set_gauge(
            "finagent_evaluations_active", max(0, self.get_gauge("finagent_evaluations_active") - 1)
        )
        status = "success" if success else "failure"
        self.increment_counter(
            "finagent_evaluations_completed_total",
            labels={"agent_id": agent_id, "mode": eval_mode, "status": status},
        )
        self.observe(
            "finagent_evaluation_duration_seconds",
            duration_s,
            labels={"agent_id": agent_id, "mode": eval_mode},
        )

    def record_llm_call(self, model: str, latency_ms: float, tokens: int, cost_usd: float):
        """记录LLM调用"""
        self.increment_counter("finagent_llm_calls_total", labels={"model": model})
        self.observe("finagent_llm_latency_ms", latency_ms, labels={"model": model})
        self.increment_counter("finagent_llm_tokens_total", float(tokens), labels={"model": model})
        self.increment_counter("finagent_llm_cost_usd_total", cost_usd, labels={"model": model})

    def record_mcp_call(self, server: str, tool: str, success: bool):
        """记录MCP工具调用"""
        status = "success" if success else "failure"
        self.increment_counter(
            "finagent_mcp_tool_calls_total",
            labels={"server": server, "tool": tool, "status": status},
        )

    def record_mcp_health(self, server: str, healthy: bool):
        """记录MCP健康状态"""
        value = 1.0 if healthy else 0.0
        self.set_gauge("finagent_mcp_server_up", value, labels={"server": server})

    def get_all_metrics(self) -> dict:
        """获取所有指标（JSON格式）"""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                key: self.get_histogram_stats(*self._parse_key(key)) for key in self._histograms
            },
        }

    def reset(self):
        """重置所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._labels.clear()

    # ---- 内部方法 ----

    def _make_key(self, name: str, labels: dict | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _parse_key(self, key: str) -> tuple[str, dict]:
        if "{" not in key:
            return key, {}
        name, rest = key.split("{", 1)
        labels_str = rest.rstrip("}")
        labels = {}
        for part in labels_str.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                labels[k.strip()] = v.strip().strip('"')
        return name, labels

    def _format_labels(self, labels: dict) -> str:
        if not labels:
            return ""
        return "{" + ",".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"

    def _get_percentiles(self, values: list[float]) -> dict:
        if not values:
            return {}
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "0.5": sorted_vals[int(n * 0.5)],
            "0.9": sorted_vals[min(int(n * 0.9), n - 1)],
            "0.95": sorted_vals[min(int(n * 0.95), n - 1)],
            "0.99": sorted_vals[min(int(n * 0.99), n - 1)],
        }
