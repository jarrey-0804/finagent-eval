"""
变异器模块

提供文本变异功能用于生成对抗样本。
"""

from .adversarial import (
    AdversarialMutator,
    BaseMutator,
    NoiseMutator,
    ParaphraseMutator,
)

__all__ = [
    "BaseMutator",
    "NoiseMutator",
    "ParaphraseMutator",
    "AdversarialMutator",
]
