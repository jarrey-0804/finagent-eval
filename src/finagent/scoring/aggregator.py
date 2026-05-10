"""
分数聚合器模块

提供多种分数聚合方法。
"""

from .engine import AggregationMethod, ScoreAggregator

__all__ = [
    "ScoreAggregator",
    "AggregationMethod",
]
