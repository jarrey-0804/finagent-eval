"""
共识构建模块

实现多模型评分的共识机制。
"""

import statistics
from dataclasses import dataclass

from .judge import ConsensusMethod, JudgeResult


@dataclass
class ConsensusResult:
    """共识结果"""
    final_score: float
    icc: float
    method: ConsensusMethod
    individual_scores: list[float]
    weights: list[float]
    passed_icc_threshold: bool


class ConsensusBuilder:
    """共识构建器"""

    def __init__(
        self,
        method: ConsensusMethod = ConsensusMethod.WEIGHTED_AVERAGE,
        min_icc: float = 0.75,
    ):
        self.method = method
        self.min_icc = min_icc

    def build(
        self,
        results: list[JudgeResult],
        weights: list[float] | None = None,
    ) -> ConsensusResult:
        """构建共识"""

        scores = [r.score for r in results]

        if not scores:
            return ConsensusResult(
                final_score=0.0,
                icc=0.0,
                method=self.method,
                individual_scores=[],
                weights=[],
                passed_icc_threshold=False,
            )

        # 计算ICC
        icc = self._calculate_icc(scores)

        # 默认权重
        if weights is None:
            weights = [1.0] * len(scores)

        # 计算共识分数
        final_score = self._calculate_consensus(scores, weights)

        return ConsensusResult(
            final_score=final_score,
            icc=icc,
            method=self.method,
            individual_scores=scores,
            weights=weights,
            passed_icc_threshold=icc >= self.min_icc,
        )

    def _calculate_icc(self, scores: list[float]) -> float:
        """计算组内相关系数"""
        if len(scores) < 2:
            return 1.0

        mean_score = statistics.mean(scores)
        if mean_score == 0:
            return 0.0

        std_score = statistics.stdev(scores) if len(scores) > 1 else 0
        cv = std_score / mean_score

        # 转换为ICC
        icc = 1 / (1 + cv)

        return min(1.0, max(0.0, icc))

    def _calculate_consensus(
        self,
        scores: list[float],
        weights: list[float],
    ) -> float:
        """计算共识分数"""

        if self.method == ConsensusMethod.MAJORITY_VOTE:
            return self._majority_vote(scores)
        elif self.method == ConsensusMethod.WEIGHTED_AVERAGE:
            return self._weighted_average(scores, weights)
        elif self.method == ConsensusMethod.MEDIAN:
            return statistics.median(scores)
        elif self.method == ConsensusMethod.ICC_BASED:
            return self._icc_weighted(scores, weights)
        else:
            return statistics.mean(scores)

    def _majority_vote(self, scores: list[float]) -> float:
        """多数投票"""
        # 离散化到区间
        bins = [0, 20, 40, 60, 80, 100]
        binned = []

        for score in scores:
            for i in range(len(bins) - 1):
                if bins[i] <= score < bins[i + 1]:
                    binned.append((bins[i] + bins[i + 1]) / 2)
                    break
            else:
                binned.append(90)

        # 返回众数
        if binned:
            return statistics.mode(binned)
        return statistics.mean(scores)

    def _weighted_average(
        self,
        scores: list[float],
        weights: list[float],
    ) -> float:
        """加权平均"""
        total_weight = sum(weights)
        if total_weight == 0:
            return statistics.mean(scores)

        return sum(s * w for s, w in zip(scores, weights, strict=False)) / total_weight

    def _icc_weighted(
        self,
        scores: list[float],
        weights: list[float],
    ) -> float:
        """基于ICC的加权"""
        icc = self._calculate_icc(scores)

        # ICC高时使用均匀权重，ICC低时偏向高权重模型
        adjusted_weights = []
        for w in weights:
            adjusted = w * (0.5 + 0.5 * icc)
            adjusted_weights.append(adjusted)

        return self._weighted_average(scores, adjusted_weights)
