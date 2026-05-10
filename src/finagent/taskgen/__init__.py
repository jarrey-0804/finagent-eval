"""
评测任务生成器模块

实现从多个数据源生成评测任务的功能，支持：
- BizFinBench: 金融业务场景基准测试
- FinMCP-Bench: MCP工具调用基准测试
- StockBench: 股票分析基准测试
- TraderBench: 交易决策基准测试
- FINTRUST: 金融可信度基准测试
"""

from .datasets import (
    BaseDataset,
    BizFinBenchDataset,
    FinMCPBenchDataset,
    FinTrustDataset,
    StockBenchDataset,
    TraderBenchDataset,
)
from .generator import EvalTaskGenerator, TaskGeneratorConfig
from .sampler import SamplingStrategy, TaskSampler

__all__ = [
    "EvalTaskGenerator",
    "TaskGeneratorConfig",
    "BaseDataset",
    "BizFinBenchDataset",
    "FinMCPBenchDataset",
    "StockBenchDataset",
    "TraderBenchDataset",
    "FinTrustDataset",
    "TaskSampler",
    "SamplingStrategy",
]
