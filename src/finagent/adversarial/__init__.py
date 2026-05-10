"""
对抗性测试模块

实现四层对抗性测试框架：
- Level 1: 基线测试
- Level 2: 噪声注入测试
- Level 3: 元认知攻击测试
- Level 4: 对抗攻击测试
"""

from .adversarial import (
    AdversarialConfig,
    AdversarialLevel,
    AdversarialTester,
    AttackResult,
)
from .attacks import (
    BaseAttack,
    ComplianceBypassAttack,
    DataLeakageAttack,
    JailbreakAttack,
    PromptInjectionAttack,
)
from .financial import (
    FinancialAdversarialTester,
    FinancialAttackResult,
    GaussianNoiseInjector,
    TechnicalIndicatorAttacker,
    TrendReversalGenerator,
)
from .mutators import (
    AdversarialMutator,
    BaseMutator,
    NoiseMutator,
    ParaphraseMutator,
)

__all__ = [
    "AdversarialTester",
    "AdversarialConfig",
    "AdversarialLevel",
    "AttackResult",
    "BaseAttack",
    "PromptInjectionAttack",
    "JailbreakAttack",
    "DataLeakageAttack",
    "ComplianceBypassAttack",
    "BaseMutator",
    "NoiseMutator",
    "ParaphraseMutator",
    "AdversarialMutator",
    "GaussianNoiseInjector",
    "TrendReversalGenerator",
    "TechnicalIndicatorAttacker",
    "FinancialAdversarialTester",
    "FinancialAttackResult",
]
