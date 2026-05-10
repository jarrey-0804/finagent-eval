"""
LLM Judge 评分器

将 LLMJudge 封装为兼容 ScoringEngine 的评分指标（BaseMetric）。
通过 LLM 多模型共识评分替代纯规则评分，提升评测质量。
"""

import asyncio
import logging

from ..interface.models import EvalDimension, EvalResponse, EvalTask
from ..judge.judge import JudgeConfig, LLMJudge
from .engine import BaseMetric

logger = logging.getLogger(__name__)


class LLMJudgeScorer(BaseMetric):
    """
    基于 LLM Judge 的评分指标。

    将 LLMJudge 的多模型共识评分能力封装为 BaseMetric 接口，
    使其可以直接注册到 ScoringEngine 中使用。

    使用示例:
    ```python
    from finagent.scoring import ScoringEngine
    from finagent.scoring.llm_judge_scorer import LLMJudgeScorer
    from finagent.judge.judge import JudgeConfig

    # 创建评分引擎
    engine = ScoringEngine()

    # 用 LLM Judge 替换默认的准确性指标
    judge_config = JudgeConfig()
    scorer = LLMJudgeScorer(
        dimension=EvalDimension.ACCURACY,
        judge_config=judge_config,
    )
    engine.register_metric(EvalDimension.ACCURACY, scorer)
    ```
    """

    def __init__(
        self,
        dimension: EvalDimension,
        judge_config: JudgeConfig | None = None,
    ):
        """
        初始化 LLM Judge 评分器。

        Args:
            dimension: 评测维度。
            judge_config: LLM Judge 配置，为 None 时使用默认配置。
        """
        super().__init__(dimension)
        self._judge = LLMJudge(config=judge_config)

    @property
    def name(self) -> str:
        return f"LLM Judge ({self.dimension.value})"

    @property
    def description(self) -> str:
        return f"基于大语言模型多模型共识的{self.dimension.value}评分"

    def compute(
        self,
        task: EvalTask,
        response: EvalResponse,
        reference: str | None = None,
    ) -> tuple[float, float, list[str], str]:
        """
        计算评分。

        调用 LLMJudge 进行多模型评分，并将 JudgeResult 转换为
        BaseMetric 要求的 (score, confidence, evidence, reasoning) 格式。

        Args:
            task: 评测任务。
            response: Agent 响应。
            reference: 参考答案（可选）。

        Returns:
            tuple: (score, confidence, evidence, reasoning)
        """
        try:
            # 在同步上下文中运行异步的 judge 方法
            result = asyncio.get_event_loop().run_until_complete(
                self._judge.judge(task, response, self.dimension, reference)
            )
        except RuntimeError:
            # 如果没有正在运行的事件循环，创建一个新的
            result = asyncio.run(
                self._judge.judge(task, response, self.dimension, reference)
            )
        except Exception as e:
            logger.error(
                "LLMJudgeScorer 评分失败: dimension=%s, error=%s",
                self.dimension.value,
                str(e),
            )
            return (
                0.0,
                0.0,
                [f"LLM Judge 评分失败: {str(e)}"],
                f"评分过程出错: {str(e)}",
            )

        # 将 MultiJudgeResult 转换为 BaseMetric 输出格式
        score = result.final_score
        confidence = result.icc  # 使用 ICC 作为置信度

        # 收集所有模型的证据
        evidence: list[str] = []
        reasoning_parts: list[str] = []

        for individual in result.individual_results:
            if individual.evidence:
                evidence.extend(individual.evidence)
            if individual.reasoning:
                reasoning_parts.append(
                    f"[{individual.model_name}] {individual.reasoning}"
                )

        # 添加共识信息
        evidence.append(
            f"共识方法: {result.consensus_method.value}, "
            f"ICC: {result.icc:.2f}, "
            f"各模型分数: {result.scores}"
        )
        reasoning_parts.append(
            f"多模型共识分数: {result.final_score:.1f} "
            f"(方法: {result.consensus_method.value}, ICC: {result.icc:.2f})"
        )

        reasoning = "；".join(reasoning_parts)

        return score, confidence, evidence, reasoning
