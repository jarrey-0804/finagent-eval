"""
基于规则的评分模块

提供知识问答、工具调用和绩效评分的规则化评分逻辑。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..interface.models import EvalDimension, EvalResponse, EvalTask


@dataclass
class RuleScore:
    """规则评分结果"""
    rule_name: str
    score: float  # 0-100
    passed: bool
    evidence: list[str] = field(default_factory=list)
    details: str = ""


class BaseRule(ABC):
    """评分规则基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """规则名称"""
        pass

    @property
    @abstractmethod
    def dimension(self) -> EvalDimension:
        """关联的评测维度"""
        pass

    @abstractmethod
    def evaluate(
        self,
        task: EvalTask,
        response: EvalResponse,
        reference: str | None = None,
    ) -> RuleScore:
        """执行规则评分"""
        pass


class KnowledgeAccuracyRule(BaseRule):
    """知识准确性规则"""

    @property
    def name(self) -> str:
        return "知识准确性"

    @property
    def dimension(self) -> EvalDimension:
        return EvalDimension.ACCURACY

    def evaluate(
        self,
        task: EvalTask,
        response: EvalResponse,
        reference: str | None = None,
    ) -> RuleScore:
        """评估知识问答的准确性"""
        evidence = []

        if not response.output:
            return RuleScore(
                rule_name=self.name,
                score=0.0,
                passed=False,
                evidence=["Agent无输出"],
                details="Agent未产生任何回答",
            )

        output = response.output
        score = 50.0

        # 规则1: 关键信息覆盖率
        if reference:
            ref_keywords = self._extract_keywords(reference)
            output_keywords = self._extract_keywords(output)

            if ref_keywords:
                overlap = len(ref_keywords & output_keywords) / len(ref_keywords)
                score += overlap * 40
                evidence.append(f"关键词覆盖率: {overlap:.1%}")

        # 规则2: 数值一致性
        import re
        ref_numbers = re.findall(r'[\d,]+\.?\d*%?', reference or "")
        out_numbers = re.findall(r'[\d,]+\.?\d*%?', output)

        if ref_numbers and out_numbers:
            matches = sum(1 for n in ref_numbers if n in out_numbers)
            number_accuracy = matches / len(ref_numbers)
            score += number_accuracy * 20
            evidence.append(f"数值一致率: {number_accuracy:.1%}")

        # 规则3: 无事实性错误
        error_words = ["错误", "不正确", "有误"]
        has_errors = any(w in output for w in error_words)
        if has_errors:
            score -= 15
            evidence.append("输出中包含错误标记")

        score = max(0, min(100, score))
        passed = score >= 60

        return RuleScore(
            rule_name=self.name,
            score=score,
            passed=passed,
            evidence=evidence,
            details=f"知识准确性评分: {score:.1f}",
        )

    def _extract_keywords(self, text: str) -> set[str]:
        import re
        words = re.findall(r'[\u4e00-\u9fa5]{2,}|\b[a-zA-Z]{3,}\b', text.lower())
        stopwords = {"的", "是", "在", "有", "和", "了", "对", "为", "与", "到", "等"}
        return {w for w in words if w not in stopwords}


class ToolCallRule(BaseRule):
    """工具调用规则"""

    @property
    def name(self) -> str:
        return "工具调用"

    @property
    def dimension(self) -> EvalDimension:
        return EvalDimension.TOOL_USAGE

    def evaluate(
        self,
        task: EvalTask,
        response: EvalResponse,
        reference: str | None = None,
    ) -> RuleScore:
        """评估工具调用的正确性"""
        evidence = []

        tool_calls = getattr(response, 'tool_calls', None) or []

        # 规则1: 必须调用工具
        if not tool_calls:
            return RuleScore(
                rule_name=self.name,
                score=0.0,
                passed=False,
                evidence=["未进行任何工具调用"],
                details="任务需要工具调用但Agent未执行",
            )

        total = len(tool_calls)
        successful = sum(1 for tc in tool_calls if tc.get("success", False))
        success_rate = successful / total if total > 0 else 0

        # 规则2: 工具调用成功率
        score = success_rate * 70
        evidence.append(f"工具调用: {successful}/{total} (成功率: {success_rate:.1%})")

        # 规则3: 工具选择正确性
        expected_tools = (task.context or {}).get("expected_tools", [])
        if expected_tools:
            used_tools = [tc.get("name", "") for tc in tool_calls]
            correct = sum(1 for t in used_tools if t in expected_tools)
            tool_accuracy = correct / len(expected_tools)
            score += tool_accuracy * 30
            evidence.append(f"工具选择正确率: {tool_accuracy:.1%}")

        score = min(100, score)
        passed = score >= 60

        return RuleScore(
            rule_name=self.name,
            score=score,
            passed=passed,
            evidence=evidence,
            details=f"工具调用评分: {score:.1f}",
        )


class PerformanceRule(BaseRule):
    """绩效评分规则"""

    @property
    def name(self) -> str:
        return "绩效评分"

    @property
    def dimension(self) -> EvalDimension:
        return EvalDimension.REASONING

    def evaluate(
        self,
        task: EvalTask,
        response: EvalResponse,
        reference: str | None = None,
    ) -> RuleScore:
        """评估回答的推理质量"""
        evidence = []

        if not response.output:
            return RuleScore(
                rule_name=self.name,
                score=0.0,
                passed=False,
                evidence=["无输出"],
                details="无法评估绩效",
            )

        output = response.output
        score = 40.0

        # 规则1: 推理结构完整性
        reasoning_markers = ["因为", "所以", "因此", "导致", "由于", "根据"]
        found_markers = [m for m in reasoning_markers if m in output]
        if found_markers:
            score += len(found_markers) * 5
            evidence.append(f"推理标记: {', '.join(found_markers[:3])}")

        # 规则2: 结论明确性
        conclusion_markers = ["建议", "推荐", "结论", "综上", "总之"]
        has_conclusion = any(m in output for m in conclusion_markers)
        if has_conclusion:
            score += 15
            evidence.append("包含明确结论")

        # 规则3: 数据支撑
        import re
        data_refs = re.findall(r'\d+\.?\d*%?|\d{4}年', output)
        if data_refs:
            score += min(len(data_refs) * 3, 20)
            evidence.append(f"数据支撑: {len(data_refs)}处")

        # 规则4: 逻辑一致性
        contradictions = 0
        pairs = [("上涨", "下跌"), ("增加", "减少"), ("看好", "看空")]
        for a, b in pairs:
            if a in output and b in output:
                contradictions += 1
        if contradictions > 0:
            score -= contradictions * 10
            evidence.append(f"发现{contradictions}处潜在矛盾")

        score = max(0, min(100, score))
        passed = score >= 60

        return RuleScore(
            rule_name=self.name,
            score=score,
            passed=passed,
            evidence=evidence,
            details=f"绩效评分: {score:.1f}",
        )


class RuleBasedScorer:
    """基于规则的评分器"""

    def __init__(self):
        self.rules: list[BaseRule] = [
            KnowledgeAccuracyRule(),
            ToolCallRule(),
            PerformanceRule(),
        ]

    def add_rule(self, rule: BaseRule):
        """添加自定义规则"""
        self.rules.append(rule)

    def evaluate(
        self,
        task: EvalTask,
        response: EvalResponse,
        reference: str | None = None,
    ) -> list[RuleScore]:
        """执行所有规则评分"""
        results = []
        for rule in self.rules:
            result = rule.evaluate(task, response, reference)
            results.append(result)
        return results

    def evaluate_dimension(
        self,
        task: EvalTask,
        response: EvalResponse,
        dimension: EvalDimension,
        reference: str | None = None,
    ) -> RuleScore | None:
        """评估指定维度"""
        for rule in self.rules:
            if rule.dimension == dimension:
                return rule.evaluate(task, response, reference)
        return None
