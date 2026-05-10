"""
评分引擎模块

实现多维度评分、加权聚合、评级映射和一票否决机制。
"""

from .aggregator import AggregationMethod, ScoreAggregator
from .engine import ScoringConfig, ScoringEngine
from .llm_judge_scorer import LLMJudgeScorer
from .metrics import (
    AccuracyMetric,
    BaseMetric,
    CompletenessMetric,
    ComplianceMetric,
    ConsistencyMetric,
    ProfessionalismMetric,
    ReasoningMetric,
    RiskAwarenessMetric,
    RobustnessMetric,
    SecurityMetric,
    ToolUsageMetric,
    TransparencyMetric,
)
from .rater import LevelRater, RatingLevel, VetoChecker
from .rules import (
    BaseRule,
    KnowledgeAccuracyRule,
    PerformanceRule,
    RuleBasedScorer,
    RuleScore,
    ToolCallRule,
)
from .trading_performance import TradingPerformanceMetric
from .veto import (
    AdversarialCVVeto,
    ComplianceVeto,
    HallucinationVeto,
    InsiderTradingVeto,
    MisleadingInfoVeto,
    PIIExposureVeto,
    SecurityVeto,
    VetoCondition,
    VetoResult,
)

__all__ = [
    "ScoringEngine",
    "ScoringConfig",
    "BaseMetric",
    "AccuracyMetric",
    "CompletenessMetric",
    "ReasoningMetric",
    "ToolUsageMetric",
    "ComplianceMetric",
    "RiskAwarenessMetric",
    "ProfessionalismMetric",
    "RobustnessMetric",
    "SecurityMetric",
    "TransparencyMetric",
    "ConsistencyMetric",
    "ScoreAggregator",
    "AggregationMethod",
    "LevelRater",
    "RatingLevel",
    "VetoChecker",
    # rules.py exports
    "RuleScore",
    "BaseRule",
    "KnowledgeAccuracyRule",
    "ToolCallRule",
    "PerformanceRule",
    "RuleBasedScorer",
    # veto.py exports
    "VetoResult",
    "VetoCondition",
    "ComplianceVeto",
    "SecurityVeto",
    "InsiderTradingVeto",
    "MisleadingInfoVeto",
    "PIIExposureVeto",
    "HallucinationVeto",
    "AdversarialCVVeto",
    # llm_judge_scorer.py exports
    "LLMJudgeScorer",
    # trading_performance.py exports
    "TradingPerformanceMetric",
]
