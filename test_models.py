#!/usr/bin/env python3
"""
测试已配置的LLM模型是否可正常工作
"""
import asyncio
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
import sys
sys.path.insert(0, '/workspace/finagent-eval/src')

from finagent.judge.judge import (
    LLMJudge, JudgeConfig, ModelConfig, LLMProvider
)
from finagent.interface.models import EvalTask, EvalResponse, EvalDimension


async def test_model(provider: LLMProvider, model_name: str, api_key_env: str):
    """测试单个模型"""
    api_key = os.getenv(api_key_env)
    if not api_key or api_key.startswith('sk-your') or api_key.startswith('sk-ant'):
        return None, "未配置"

    config = JudgeConfig(
        models=[
            ModelConfig(
                provider=provider,
                model_name=model_name,
                api_key=api_key,
                weight=1.0,
            )
        ]
    )

    judge = LLMJudge(config)

    # 创建测试任务
    task = EvalTask(
        task_id="test_task",
        task_type="knowledge_qa",
        input_data={"query": "什么是基金净值？"},
        dimension=EvalDimension.ACCURACY,
    )
    response = EvalResponse(
        task_id="test_task",
        output="基金净值是指每份基金单位的净资产价值。",
    )

    try:
        result = await judge.judge(task, response, EvalDimension.ACCURACY)
        return result, "成功"
    except Exception as e:
        return None, f"失败: {str(e)[:50]}"


async def main():
    print("=" * 60)
    print("FinAgent-Eval LLM模型连通性测试")
    print("=" * 60)

    models_to_test = [
        (LLMProvider.DEEPSEEK, "deepseek-chat", "DEEPSEEK_API_KEY"),
        (LLMProvider.DASHSCOPE, "qwen-plus", "DASHSCOPE_API_KEY"),
        (LLMProvider.ZHIPU, "glm-4", "ZHIPU_API_KEY"),
    ]

    results = []
    for provider, model_name, env_key in models_to_test:
        print(f"\n测试 {provider.value}/{model_name}...")
        result, status = await test_model(provider, model_name, env_key)
        results.append((provider.value, model_name, status))

        if result:
            print(f"  ✅ 状态: {status}")
            print(f"  📊 评分: {result.final_score:.1f}")
            print(f"  🎯 ICC: {result.icc:.3f}")
        else:
            print(f"  ❌ 状态: {status}")

    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    for provider, model_name, status in results:
        icon = "✅" if status == "成功" else "❌" if "失败" in status else "⏭️"
        print(f"{icon} {provider}/{model_name}: {status}")

    # 统计
    success_count = sum(1 for _, _, s in results if s == "成功")
    print(f"\n总计: {success_count}/{len(results)} 个模型工作正常")


if __name__ == "__main__":
    asyncio.run(main())
