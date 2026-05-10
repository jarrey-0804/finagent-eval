#!/usr/bin/env python3
"""
多模型交叉验证评测测试
使用 DeepSeek + 百炼 + 智谱GLM 三个模型同时评分，计算 ICC 一致性
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '/workspace/finagent-eval/src')

from finagent.judge.judge import (
    LLMJudge, JudgeConfig, ModelConfig, LLMProvider, ConsensusMethod
)
from finagent.interface.models import EvalTask, EvalResponse, EvalDimension


async def run_multi_model_evaluation():
    """运行多模型交叉验证评测"""
    print("=" * 70)
    print("FinAgent-Eval 多模型交叉验证评测")
    print("=" * 70)
    print("\n模型配置:")
    print("  1. DeepSeek (deepseek-chat) - 权重: 1.0")
    print("  2. 百炼 (qwen-plus) - 权重: 1.0")
    print("  3. 智谱GLM (glm-4) - 权重: 1.0")
    print("\n共识方法: ICC_BASED (基于组内相关系数的加权)")
    print("=" * 70)

    # 配置三个模型
    config = JudgeConfig(
        models=[
            ModelConfig(
                provider=LLMProvider.DEEPSEEK,
                model_name="deepseek-chat",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                weight=1.0,
            ),
            ModelConfig(
                provider=LLMProvider.DASHSCOPE,
                model_name="qwen-plus",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                weight=1.0,
            ),
            ModelConfig(
                provider=LLMProvider.ZHIPU,
                model_name="glm-4",
                api_key=os.getenv("ZHIPU_API_KEY"),
                weight=1.0,
            ),
        ],
        consensus_method=ConsensusMethod.ICC_BASED,
    )

    judge = LLMJudge(config)

    # 测试任务：基金知识问答
    task = EvalTask(
        task_id="fund_knowledge_001",
        task_type="knowledge_qa",
        input_data={"query": "请解释什么是基金的夏普比率，以及如何使用它来评估基金表现？"},
        dimension=EvalDimension.ACCURACY,
    )

    # 模拟 Agent 回答（一个合理的回答）
    response = EvalResponse(
        task_id="fund_knowledge_001",
        output="""夏普比率（Sharpe Ratio）是衡量基金风险调整后收益的重要指标。

计算公式：
夏普比率 = (基金收益率 - 无风险收益率) / 基金收益率的标准差

解读：
- 夏普比率 > 1：基金表现优秀，风险调整后收益良好
- 0 < 夏普比率 < 1：基金表现一般，收益勉强覆盖风险
- 夏普比率 < 0：基金表现不佳，收益低于无风险利率

使用建议：
1. 同类基金比较：在相同类型基金中比较夏普比率
2. 时间周期：关注长期夏普比率（如3年、5年）
3. 结合其他指标：与最大回撤、年化收益率等指标综合评估""",
    )

    print("\n【评测任务】")
    print(f"问题: {task.input_data.get('query', '')}")
    print(f"\nAgent回答长度: {len(response.output)} 字符")
    print(f"评测维度: {EvalDimension.ACCURACY.value} (准确性)")

    print("\n" + "=" * 70)
    print("开始多模型评分...")
    print("=" * 70)

    try:
        result = await judge.judge(task, response, EvalDimension.ACCURACY)

        print("\n【各模型评分结果】")
        print("-" * 70)
        for i, individual in enumerate(result.individual_results, 1):
            print(f"\n模型 {i}: {individual.model_name}")
            print(f"  评分: {individual.score:.1f}/100")
            print(f"  置信度: {individual.confidence:.2f}")
            print(f"  推理: {individual.reasoning[:60]}...")

        print("\n" + "=" * 70)
        print("【多模型交叉验证结果】")
        print("=" * 70)
        print(f"\n最终共识评分: {result.final_score:.1f}/100")
        print(f"ICC 组内相关系数: {result.icc:.3f}")
        print(f"共识方法: {result.consensus_method}")

        # ICC 解读
        icc = result.icc
        if icc >= 0.75:
            icc_level = "优秀 (≥0.75)"
            reliability = "模型间一致性高，评分结果可信"
        elif icc >= 0.5:
            icc_level = "良好 (0.5-0.75)"
            reliability = "模型间一致性中等，评分结果基本可信"
        elif icc >= 0.25:
            icc_level = "一般 (0.25-0.5)"
            reliability = "模型间一致性较低，建议人工复核"
        else:
            icc_level = "较差 (<0.25)"
            reliability = "模型间一致性差，评分结果不可信"

        print(f"\n一致性等级: {icc_level}")
        print(f"可信度评估: {reliability}")

        # 评分分布分析
        scores = [s.score for s in result.individual_results]
        score_range = max(scores) - min(scores)
        print(f"\n评分分布:")
        print(f"  最高分: {max(scores):.1f}")
        print(f"  最低分: {min(scores):.1f}")
        print(f"  分差: {score_range:.1f}")

        if score_range <= 5:
            consensus_level = "高度一致"
        elif score_range <= 15:
            consensus_level = "基本一致"
        else:
            consensus_level = "分歧较大"
        print(f"  共识程度: {consensus_level}")

        print("\n" + "=" * 70)
        print("【评测结论】")
        print("=" * 70)

        final_score = result.final_score
        if final_score >= 90:
            rating = "S (卓越)"
            comment = "Agent回答质量极高，信息准确完整"
        elif final_score >= 80:
            rating = "A (优秀)"
            comment = "Agent回答质量良好，信息基本准确"
        elif final_score >= 70:
            rating = "B (良好)"
            comment = "Agent回答质量尚可，有小瑕疵"
        elif final_score >= 60:
            rating = "C (合格)"
            comment = "Agent回答基本可用，有明显改进空间"
        else:
            rating = "D (不合格)"
            comment = "Agent回答质量较差，需要重大改进"

        print(f"\n评级: {rating}")
        print(f"评价: {comment}")

        if icc >= 0.75:
            print(f"\n✅ 评测结果可信 (ICC={icc:.3f})")
        else:
            print(f"\n⚠️  评测结果需谨慎解读 (ICC={icc:.3f})")

        return result

    except Exception as e:
        print(f"\n❌ 评测失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(run_multi_model_evaluation())
    sys.exit(0 if result else 1)
