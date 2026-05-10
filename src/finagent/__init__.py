"""
FinAgent-Eval: 金融AI Agent评测系统

一个标准化的金融AI Agent评测框架，支持多维度评分、对抗性测试和自动化评测流程。
"""

__version__ = "1.0.0"
__author__ = "FinAgent Team"

from .adapter import (
    AdapterRegistry,
    HTTPAdapter,
    LangGraphAdapter,
)
from .adversarial import (
    AdversarialConfig,
    AdversarialTester,
)
from .interface import (
    AgentConfig,
    AgentType,
    DifficultyLevel,
    EvalDimension,
    EvalMode,
    EvalResponse,
    EvalStatus,
    EvalTask,
    FinancialAgentInterface,
    TaskType,
)
from .judge import (
    JudgeConfig,
    LLMJudge,
)
from .pipeline import (
    EvalPipeline,
    PipelineConfig,
)
from .scoring import (
    RatingLevel,
    ScoringConfig,
    ScoringEngine,
)
from .taskgen import (
    EvalTaskGenerator,
    TaskGeneratorConfig,
)

__all__ = [
    # Interface
    "FinancialAgentInterface",
    "AgentConfig",
    "EvalTask",
    "EvalResponse",
    "EvalMode",
    "EvalStatus",
    "EvalDimension",
    "DifficultyLevel",
    "TaskType",
    "AgentType",
    # Adapter
    "LangGraphAdapter",
    "HTTPAdapter",
    "AdapterRegistry",
    # TaskGen
    "EvalTaskGenerator",
    "TaskGeneratorConfig",
    # Scoring
    "ScoringEngine",
    "ScoringConfig",
    "RatingLevel",
    # Pipeline
    "EvalPipeline",
    "PipelineConfig",
    # Judge
    "LLMJudge",
    "JudgeConfig",
    # Adversarial
    "AdversarialTester",
    "AdversarialConfig",
]
