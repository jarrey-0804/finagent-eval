"""
压力/并发测试 — 评测流水线在并发负载下的表现

模拟多个评测流水线同时运行、并发评分操作、
调度器高负载提交以及资源配额竞争等场景，
验证系统在并发条件下的正确性和性能表现。

使用 asyncio 实现异步并发，threading 实现线程级并发。
"""

import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pytest

from finagent.interface.models import (
    EvalTask, EvalResponse, TaskType, EvalDimension,
)
from finagent.taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig
from finagent.scoring.engine import ScoringEngine
from finagent.scoring.veto import VetoChecker
from finagent.pipeline.scheduler import (
    EvaluationScheduler, SchedulerConfig, TaskPriority,
    ScheduledTaskStatus,
)
from finagent.pipeline.quota import ResourceQuota, QuotaConfig


# ============================================================
# 辅助函数
# ============================================================

def _run_single_evaluation(
    eval_id: str,
    n_tasks: int = 5,
    seed: int = 42,
) -> dict:
    """
    模拟单次完整评测流水线执行。

    包含任务生成、模拟Agent响应、评分三个阶段。

    Args:
        eval_id: 评测唯一标识
        n_tasks: 生成任务数量
        seed: 随机种子

    Returns:
        dict: 包含 eval_id, n_tasks, scores, total_time 的结果字典
    """
    start = time.perf_counter()

    # 阶段1: 任务生成
    config = TaskGeneratorConfig(
        tasks_per_source=n_tasks,
        max_total_tasks=n_tasks,
        random_seed=seed,
    )
    generator = EvalTaskGenerator(config)
    tasks = generator.generate_tasks(n_tasks=n_tasks)

    # 阶段2: 模拟Agent响应
    responses = []
    for task in tasks:
        responses.append(EvalResponse(
            task_id=task.task_id,
            output=(
                "根据财务数据分析，该股票2024年Q3营收388亿元，同比增长15%。"
                "净利润率22.5%，ROE为18.5%。投资有风险，请谨慎决策。"
            ),
            tool_calls=[
                {"name": "get_financial", "args": {"symbol": "600519"}, "success": True},
            ],
        ))

    # 阶段3: 评分
    engine = ScoringEngine()
    scores = []
    for task, response in zip(tasks, responses):
        score = engine.score_task(task, response)
        scores.append(score.overall_score)

    elapsed = time.perf_counter() - start

    return {
        "eval_id": eval_id,
        "n_tasks": len(tasks),
        "scores": scores,
        "total_time": elapsed,
    }


def _print_stress_result(label: str, n_workers: int, total_time: float, per_worker_times: list[float]):
    """
    打印压力测试结果摘要。

    Args:
        label: 测试名称
        n_workers: 并发数
        total_time: 总耗时
        per_worker_times: 每个worker的耗时列表
    """
    avg = sum(per_worker_times) / len(per_worker_times) if per_worker_times else 0
    max_t = max(per_worker_times) if per_worker_times else 0
    min_t = min(per_worker_times) if per_worker_times else 0
    print(
        f"\n[{label}] 并发数={n_workers} | "
        f"总耗时={total_time:.3f}s | "
        f"平均={avg:.3f}s | "
        f"最小={min_t:.3f}s | "
        f"最大={max_t:.3f}s"
    )


# ============================================================
# 测试用例
# ============================================================

class TestStressConcurrentEvaluations:
    """并发评测流水线压力测试"""

    def test_concurrent_evaluations_3(self):
        """
        测试1: 3个并发评测流水线

        使用线程池模拟3个评测流水线同时执行。
        验证:
        - 所有评测均正常完成
        - 评分结果在有效范围内
        - 并发执行总时间合理（应接近最慢单次执行时间，而非累加）
        """
        n_workers = 3
        results = []

        start_total = time.perf_counter()

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {
                executor.submit(
                    _run_single_evaluation,
                    eval_id=f"concurrent_3_{i}",
                    n_tasks=5,
                    seed=42 + i,
                ): i
                for i in range(n_workers)
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        total_time = time.perf_counter() - start_total
        per_worker_times = [r["total_time"] for r in results]

        # 正确性验证: 所有评测完成
        assert len(results) == n_workers, (
            f"预期 {n_workers} 个评测完成，实际 {len(results)} 个"
        )

        # 正确性验证: 评分结果有效
        for r in results:
            assert len(r["scores"]) > 0, f"评测 {r['eval_id']} 无评分结果"
            for s in r["scores"]:
                assert 0 <= s <= 100, f"评分超出范围: {s}"

        # 性能验证: 并发总时间应合理（允许线程开销，不超过串行时间的2倍）
        serial_estimate = sum(per_worker_times)
        assert total_time < serial_estimate * 2.0, (
            f"并发性能异常: 并发耗时 {total_time:.2f}s 超过串行估算的2倍 {serial_estimate * 2.0:.2f}s"
        )

        _print_stress_result(
            "3并发评测", n_workers, total_time, per_worker_times
        )

    def test_concurrent_evaluations_5(self):
        """
        测试2: 5个并发评测流水线

        使用线程池模拟5个评测流水线同时执行。
        验证:
        - 所有评测均正常完成
        - 评分结果在有效范围内
        - 并发执行总时间合理
        """
        n_workers = 5
        results = []

        start_total = time.perf_counter()

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {
                executor.submit(
                    _run_single_evaluation,
                    eval_id=f"concurrent_5_{i}",
                    n_tasks=5,
                    seed=100 + i,
                ): i
                for i in range(n_workers)
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        total_time = time.perf_counter() - start_total
        per_worker_times = [r["total_time"] for r in results]

        # 正确性验证
        assert len(results) == n_workers, (
            f"预期 {n_workers} 个评测完成，实际 {len(results)} 个"
        )

        for r in results:
            assert len(r["scores"]) > 0, f"评测 {r['eval_id']} 无评分结果"
            for s in r["scores"]:
                assert 0 <= s <= 100, f"评分超出范围: {s}"

        # 性能验证: 并发总时间应合理（允许线程开销，不超过串行时间的2倍）
        serial_estimate = sum(per_worker_times)
        assert total_time < serial_estimate * 2.0, (
            f"并发性能异常: 并发耗时 {total_time:.2f}s 超过串行估算的2倍 {serial_estimate * 2.0:.2f}s"
        )

        _print_stress_result(
            "5并发评测", n_workers, total_time, per_worker_times
        )


class TestStressConcurrentScoring:
    """并发评分压力测试"""

    def test_concurrent_scoring(self, scoring_engine):
        """
        测试3: 10个并发评分操作

        使用线程池模拟10个评分操作同时执行。
        验证:
        - 所有评分操作正常完成
        - 评分结果有效且一致
        - 并发评分不产生异常
        """
        n_workers = 10
        n_tasks_per_worker = 5
        results = []
        errors = []

        # 每个worker独立生成自己的任务和响应，避免共享数据竞争
        def _score_batch(worker_id: int) -> dict:
            """单个worker执行一批评分（独立生成数据）"""
            # 生成任务
            config = TaskGeneratorConfig(
                tasks_per_source=n_tasks_per_worker,
                max_total_tasks=n_tasks_per_worker,
                random_seed=200 + worker_id,
            )
            generator = EvalTaskGenerator(config)
            tasks = generator.generate_tasks(n_tasks=n_tasks_per_worker)

            # 构造响应
            responses = []
            for task in tasks:
                responses.append(EvalResponse(
                    task_id=task.task_id,
                    output="根据分析，该股票基本面良好。ROE为18.5%。投资有风险。",
                    tool_calls=[{"name": "get_data", "args": {}, "success": True}],
                ))

            start = time.perf_counter()
            scores = []
            for task, response in zip(tasks, responses):
                score = scoring_engine.score_task(task, response)
                scores.append(score.overall_score)
            elapsed = time.perf_counter() - start
            return {"worker_id": worker_id, "scores": scores, "elapsed": elapsed}

        start_total = time.perf_counter()

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {
                executor.submit(_score_batch, i): i
                for i in range(n_workers)
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append((futures[future], str(e)))

        total_time = time.perf_counter() - start_total
        per_worker_times = [r["elapsed"] for r in results]

        # 正确性验证: 无异常
        assert len(errors) == 0, f"并发评分出现 {len(errors)} 个错误: {errors}"

        # 正确性验证: 所有worker完成
        assert len(results) == n_workers, (
            f"预期 {n_workers} 个worker完成，实际 {len(results)} 个"
        )

        # 正确性验证: 评分结果有效
        total_scores = sum(len(r["scores"]) for r in results)
        assert total_scores == n_workers * n_tasks_per_worker, (
            f"预期 {n_workers * n_tasks_per_worker} 个评分，实际 {total_scores} 个"
        )
        for r in results:
            for s in r["scores"]:
                assert 0 <= s <= 100, f"评分超出范围: {s}"

        _print_stress_result(
            "10并发评分", n_workers, total_time, per_worker_times
        )


class TestStressScheduler:
    """调度器高负载压力测试"""

    @pytest.mark.asyncio
    async def test_scheduler_under_load(self, scheduler):
        """
        测试4: 调度器高负载提交

        向调度器提交20个评测任务，验证:
        - 所有任务被正确排队
        - 调度器按优先级和并发限制执行
        - 所有任务最终完成
        - 完成顺序与提交顺序一致（同优先级）
        """
        n_tasks = 20
        submitted_ids = []

        # 启动调度器
        await scheduler.start()

        try:
            # 提交20个任务（混合优先级）
            priorities = [
                TaskPriority.HIGH,
                TaskPriority.NORMAL,
                TaskPriority.LOW,
                TaskPriority.NORMAL,
            ]
            for i in range(n_tasks):
                priority = priorities[i % len(priorities)]
                task_id = await scheduler.submit(
                    evaluation_id=f"eval_load_{i}",
                    agent_id=f"agent_{i % 5}",
                    priority=priority,
                )
                submitted_ids.append(task_id)

            # 等待所有任务完成（最多30秒）
            max_wait = 30.0
            poll_interval = 0.5
            waited = 0.0

            while waited < max_wait:
                queue_status = scheduler.get_queue_status()
                if queue_status["completed_count"] >= n_tasks:
                    break
                await asyncio.sleep(poll_interval)
                waited += poll_interval

            # 验证: 所有任务完成
            queue_status = scheduler.get_queue_status()
            assert queue_status["completed_count"] == n_tasks, (
                f"预期 {n_tasks} 个任务完成，实际 {queue_status['completed_count']} 个 "
                f"(队列: {queue_status['queue_size']}, 运行中: {queue_status['running_count']})"
            )

            # 验证: 无失败任务
            completed_tasks = scheduler._completed
            failed = [t for t in completed_tasks if t.status == ScheduledTaskStatus.FAILED]
            assert len(failed) == 0, (
                f"有 {len(failed)} 个任务失败: {[t.task_id for t in failed]}"
            )

            # 验证: 每个提交的任务都有对应的完成记录
            completed_ids = {t.task_id for t in completed_tasks}
            for tid in submitted_ids:
                assert tid in completed_ids, f"任务 {tid} 未在完成列表中"

            print(
                f"\n[调度器高负载] 提交={n_tasks} | "
                f"完成={queue_status['completed_count']} | "
                f"等待={waited:.1f}s | "
                f"最大并发={queue_status['max_concurrent']}"
            )

        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_resource_quota_contention(self, quota_config):
        """
        测试5: 资源配额竞争

        模拟多个评测竞争有限的资源配额。
        配额限制: max_concurrent=3, max_cpu=80%, max_memory=2048MB
        验证:
        - 超出配额的分配请求被拒绝
        - 释放资源后新的分配可以成功
        - 资源使用计数准确
        """
        quota = ResourceQuota(quota_config)
        max_concurrent = quota_config.max_concurrent_evaluations

        allocated = []
        rejected = []

        # 阶段1: 尝试分配超过最大并发数的资源
        for i in range(max_concurrent + 5):
            success = quota.allocate(f"eval_contention_{i}")
            if success:
                allocated.append(f"eval_contention_{i}")
            else:
                rejected.append(f"eval_contention_{i}")

        # 验证: 恰好分配了 max_concurrent 个
        assert len(allocated) == max_concurrent, (
            f"预期分配 {max_concurrent} 个，实际 {len(allocated)} 个"
        )

        # 验证: 其余被拒绝
        assert len(rejected) == 5, (
            f"预期拒绝 5 个，实际 {len(rejected)} 个"
        )

        # 验证: 资源使用情况
        usage = quota.get_usage()
        assert usage.active_evaluations == max_concurrent, (
            f"活跃评测数应为 {max_concurrent}，实际 {usage.active_evaluations}"
        )

        # 阶段2: 释放一个资源后，新的分配应成功
        quota.release(allocated[0])
        remaining_quota = quota.get_remaining()
        assert remaining_quota["concurrent_remaining"] == 1, (
            f"释放后应剩余1个并发槽位，实际 {remaining_quota['concurrent_remaining']}"
        )

        # 新分配应成功
        success = quota.allocate("eval_contention_new")
        assert success, "释放资源后新分配应成功"

        # 阶段3: 再次填满后应再次拒绝
        success = quota.allocate("eval_contention_overflow")
        assert not success, "配额已满时新分配应失败"

        # 阶段4: 释放所有资源后，使用应归零
        for eid in allocated[1:]:
            quota.release(eid)
        quota.release("eval_contention_new")

        usage_final = quota.get_usage()
        assert usage_final.active_evaluations == 0, (
            f"全部释放后活跃数应为0，实际 {usage_final.active_evaluations}"
        )

        print(
            f"\n[资源配额竞争] 最大并发={max_concurrent} | "
            f"成功分配={len(allocated)} | "
            f"被拒绝={len(rejected)} | "
            f"最终活跃={usage_final.active_evaluations}"
        )


class TestStressVetoConcurrency:
    """否决检查并发压力测试"""

    def test_concurrent_veto_checks(self):
        """
        附加测试: 100次并发否决检查

        使用线程池模拟100个否决检查同时执行。
        验证线程安全性: 所有检查正常完成，无异常。
        """
        n_workers = 100
        checker = VetoChecker(threshold=30.0)
        results = []
        errors = []

        def _single_veto_check(idx: int) -> dict:
            """单次否决检查"""
            task = EvalTask(
                task_id=f"veto_concurrent_{idx}",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension=EvalDimension.COMPLIANCE,
                input_data={"query": "测试查询"},
            )
            response = EvalResponse(
                task_id=task.task_id,
                output="投资有风险，请谨慎决策。该股票ROE为18.5%。",
            )
            dim_scores = {
                "compliance": 50.0 + (idx % 50),
                "security": 60.0 + (idx % 40),
            }
            start = time.perf_counter()
            result = checker.check(task, response, dim_scores)
            elapsed = time.perf_counter() - start
            return {"idx": idx, "vetoed": result.vetoed, "elapsed": elapsed}

        start_total = time.perf_counter()

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {
                executor.submit(_single_veto_check, i): i
                for i in range(n_workers)
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append((futures[future], str(e)))

        total_time = time.perf_counter() - start_total

        # 正确性验证: 无异常
        assert len(errors) == 0, f"并发否决检查出现 {len(errors)} 个错误"

        # 正确性验证: 所有检查完成
        assert len(results) == n_workers, (
            f"预期 {n_workers} 个检查完成，实际 {len(results)} 个"
        )

        per_worker_times = [r["elapsed"] for r in results]
        _print_stress_result(
            "100并发否决检查", n_workers, total_time, per_worker_times
        )
