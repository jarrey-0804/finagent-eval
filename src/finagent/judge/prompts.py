"""
Judge提示模板模块

提供评分提示的构建模板。
"""

from dataclasses import dataclass

from ..interface.models import EvalDimension, EvalResponse, EvalTask


@dataclass
class PromptTemplate:
    """提示模板"""
    name: str
    system_template: str
    user_template: str

    def format(
        self,
        task: EvalTask,
        response: EvalResponse,
        dimension: EvalDimension,
        reference: str | None = None,
    ) -> tuple[str, str]:
        """格式化提示"""
        system_prompt = self.system_template.format(dimension=dimension.value)

        user_prompt = self.user_template.format(
            query=task.input_data.get('query', ''),
            output=response.output or "（无输出）",
            reference=reference or "（无参考答案）",
            error=response.error or "",
        )

        return system_prompt, user_prompt


# 预定义模板
DEFAULT_TEMPLATE = PromptTemplate(
    name="default",
    system_template="""你是一个专业的金融AI评测专家，负责评估AI Agent的回答质量。

评估维度：{dimension}

请严格按照以下JSON格式输出：
{{
    "score": <0-100的整数>,
    "confidence": <0-1的浮点数>,
    "reasoning": "<评分理由>",
    "evidence": ["<证据1>", "<证据2>"]
}}
""",
    user_template="""【问题】
{query}

【Agent回答】
{output}

【参考答案】
{reference}

请给出评分结果（JSON格式）：""",
)

DETAILED_TEMPLATE = PromptTemplate(
    name="detailed",
    system_template="""你是一位资深的金融AI评测专家，具有丰富的金融领域知识和AI评估经验。

当前评估维度：{dimension}

评估要求：
1. 仔细分析问题和回答的每个细节
2. 结合金融行业标准和监管要求
3. 给出客观、公正的评分

输出格式（JSON）：
{{
    "score": <0-100的整数>,
    "confidence": <0-1的浮点数>,
    "reasoning": "<详细的评分理由>",
    "evidence": ["<支持评分的具体证据>"],
    "improvements": ["<改进建议>"]
}}
""",
    user_template="""请对以下AI Agent的回答进行全面评估：

【用户问题】
{query}

【AI回答】
{output}

【参考答案】
{reference}

【错误信息】
{error}

请提供详细的评估结果：""",
)

COMPLIANCE_TEMPLATE = PromptTemplate(
    name="compliance",
    system_template="""你是一位金融合规专家，负责评估AI回答是否符合金融监管要求。

评估维度：{dimension}

合规检查要点：
1. 是否包含违规承诺（保本、保收益等）
2. 是否有适当的风险提示
3. 是否符合投资者适当性要求
4. 是否有误导性表述

输出格式（JSON）：
{{
    "score": <0-100的整数>,
    "confidence": <0-1的浮点数>,
    "reasoning": "<合规性分析>",
    "evidence": ["<发现的合规问题或合规点>"],
    "violations": ["<违规项>"]
}}
""",
    user_template="""请评估以下回答的合规性：

【问题】
{query}

【回答】
{output}

请给出合规性评分：""",
)
