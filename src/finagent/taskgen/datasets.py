"""
数据集模块

提供各类金融评测数据集的实现。
"""

# 从generator导入所有数据集类
from .generator import (
    BaseDataset,
    BizFinBenchDataset,
    DataSource,
    FinMCPBenchDataset,
    FinTrustDataset,
    StockBenchDataset,
    TaskCategory,
    TraderBenchDataset,
)

__all__ = [
    "BaseDataset",
    "BizFinBenchDataset",
    "FinMCPBenchDataset",
    "StockBenchDataset",
    "TraderBenchDataset",
    "FinTrustDataset",
    "DataSource",
    "TaskCategory",
]
