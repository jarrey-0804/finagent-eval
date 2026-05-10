"""
命令行接口模块

提供命令行工具入口。
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .api.app import run_server
from .config import Config, load_config


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        prog="finagent-eval",
        description="金融AI Agent评测系统命令行工具",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # serve 命令
    serve_parser = subparsers.add_parser("serve", help="启动API服务")
    serve_parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    serve_parser.add_argument("--port", type=int, default=8000, help="监听端口")
    serve_parser.add_argument("--config", type=str, help="配置文件路径")
    serve_parser.add_argument("--workers", type=int, default=4, help="工作进程数")

    # eval 命令
    eval_parser = subparsers.add_parser("eval", help="运行评测")
    eval_parser.add_argument("--agent-id", required=True, help="Agent ID")
    eval_parser.add_argument("--endpoint", help="Agent HTTP端点URL")
    eval_parser.add_argument("--mode", choices=["quick", "full"], default="full", help="评测模式")
    eval_parser.add_argument("--output", "-o", help="输出文件路径")
    eval_parser.add_argument("--config", type=str, help="配置文件路径")

    # generate 命令
    gen_parser = subparsers.add_parser("generate", help="生成评测任务")
    gen_parser.add_argument("--count", type=int, default=20, help="任务数量")
    gen_parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    gen_parser.add_argument("--mode", choices=["quick", "full"], default="full", help="评测模式")

    # test 命令
    test_parser = subparsers.add_parser("test", help="运行对抗性测试")
    test_parser.add_argument("--agent-id", required=True, help="Agent ID")
    test_parser.add_argument("--endpoint", help="Agent HTTP端点URL")
    test_parser.add_argument("--level", choices=["baseline", "noisy", "meta_cognitive", "adversarial", "all"],
                             default="all", help="测试等级")
    test_parser.add_argument("--output", "-o", help="输出文件路径")

    # config 命令
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_parser.add_argument("--init", action="store_true", help="生成默认配置文件")
    config_parser.add_argument("--show", action="store_true", help="显示当前配置")
    config_parser.add_argument("--path", type=str, help="配置文件路径")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "serve":
        handle_serve(args)
    elif args.command == "eval":
        handle_eval(args)
    elif args.command == "generate":
        handle_generate(args)
    elif args.command == "test":
        handle_test(args)
    elif args.command == "config":
        handle_config(args)


def handle_serve(args):
    """处理serve命令"""
    import uvicorn

    config = None
    if args.config:
        config = load_config(args.config)

    print(f"启动API服务: http://{args.host}:{args.port}")

    if args.workers > 1:
        uvicorn.run(
            "finagent.api.app:create_app",
            host=args.host,
            port=args.port,
            workers=args.workers,
            factory=True,
        )
    else:
        run_server(host=args.host, port=args.port, config=config)


def handle_eval(args):
    """处理eval命令"""
    async def run():
        from . import AgentConfig, EvalMode, EvalPipeline, HTTPAdapter, PipelineConfig

        # 创建适配器
        if args.endpoint:
            adapter = HTTPAdapter(
                endpoint_url=args.endpoint,
                config=AgentConfig(
                    agent_id=args.agent_id,
                    agent_name=args.agent_id,
                ),
            )
        else:
            print("错误: 需要提供 --endpoint 参数")
            sys.exit(1)

        # 创建流水线
        mode = EvalMode.QUICK if args.mode == "quick" else EvalMode.FULL
        pipeline = EvalPipeline(
            agent=adapter,
            config=PipelineConfig(eval_mode=mode),
        )

        # 运行评测
        print(f"开始评测 Agent: {args.agent_id}")
        print(f"评测模式: {args.mode}")

        result = await pipeline.run()

        # 输出结果
        print("\n" + "=" * 50)
        print("评测结果")
        print("=" * 50)

        if result.evaluation_score:
            score = result.evaluation_score
            print(f"总体分数: {score.overall_score:.1f}")
            print(f"评级: {score.overall_rating.value}")
            print(f"总任务数: {score.total_tasks}")
            print(f"通过任务数: {score.passed_tasks}")
            print(f"通过率: {score.pass_rate:.1%}")

            print("\n维度分数:")
            for dim, avg in score.dimension_averages.items():
                print(f"  - {dim.value}: {avg:.1f}")

        # 保存结果
        if args.output:
            import json
            output = {
                "agent_id": args.agent_id,
                "mode": args.mode,
                "overall_score": result.evaluation_score.overall_score if result.evaluation_score else None,
                "rating": result.evaluation_score.overall_rating.value if result.evaluation_score else None,
                "report": result.report,
            }

            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            print(f"\n结果已保存到: {args.output}")

    asyncio.run(run())


def handle_generate(args):
    """处理generate命令"""
    import json

    from . import EvalTaskGenerator, TaskGeneratorConfig

    print(f"生成评测任务: {args.count}个")

    config = TaskGeneratorConfig(
        tasks_per_source=args.count // 5,
        max_total_tasks=args.count,
    )

    generator = EvalTaskGenerator(config)
    tasks = generator.generate_tasks(n_tasks=args.count)

    # 序列化任务
    tasks_data = [
        {
            "task_id": t.task_id,
            "task_type": t.task_type.value,
            "query": t.query,
            "dimensions": [d.value for d in t.dimensions],
            "context": t.context,
        }
        for t in tasks
    ]

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tasks_data, f, ensure_ascii=False, indent=2)

    print(f"已生成 {len(tasks)} 个任务")
    print(f"保存到: {args.output}")


def handle_test(args):
    """处理test命令"""
    async def run():
        from . import AdversarialConfig, AdversarialTester, AgentConfig, HTTPAdapter
        from .adversarial import AdversarialLevel

        # 创建适配器
        if args.endpoint:
            adapter = HTTPAdapter(
                endpoint_url=args.endpoint,
                config=AgentConfig(
                    agent_id=args.agent_id,
                    agent_name=args.agent_id,
                ),
            )
        else:
            print("错误: 需要提供 --endpoint 参数")
            sys.exit(1)

        # 确定测试等级
        if args.level == "all":
            levels = list(AdversarialLevel)
        else:
            levels = [AdversarialLevel(args.level)]

        # 创建测试器
        tester = AdversarialTester(
            agent=adapter,
            config=AdversarialConfig(levels=levels),
        )

        # 运行测试
        print(f"开始对抗性测试: {args.agent_id}")
        print(f"测试等级: {args.level}")

        result = await tester.run_tests()

        # 输出结果
        print("\n" + "=" * 50)
        print("对抗性测试结果")
        print("=" * 50)

        print(f"总攻击数: {result.total_attacks}")
        print(f"成功攻击数: {result.successful_attacks}")
        print(f"漏洞率: {result.vulnerability_rate:.1%}")
        print(f"安全分数: {result.overall_security_score:.1f}")

        print("\n建议:")
        for rec in result.recommendations:
            print(f"  - {rec}")

        # 保存结果
        if args.output:
            import json
            output = {
                "agent_id": args.agent_id,
                "level": args.level,
                "total_attacks": result.total_attacks,
                "successful_attacks": result.successful_attacks,
                "vulnerability_rate": result.vulnerability_rate,
                "security_score": result.overall_security_score,
                "recommendations": result.recommendations,
            }

            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            print(f"\n结果已保存到: {args.output}")

    asyncio.run(run())


def handle_config(args):
    """处理config命令"""
    if args.init:
        config = Config()
        path = Path(args.path or "config/config.yaml")
        config.to_yaml(path)
        print(f"配置文件已生成: {path}")

    elif args.show:
        config = load_config(args.path)
        print("当前配置:")
        print(config.model_dump_json(indent=2))

    else:
        print("请指定 --init 或 --show")


if __name__ == "__main__":
    main()
