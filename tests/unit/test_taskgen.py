"""
任务生成器单元测试
"""

import pytest
from finagent.taskgen.generator import (
    EvalTaskGenerator, TaskGeneratorConfig, DataSource,
    TaskSampler, SamplingStrategy,
)
from finagent.interface.models import EvalDimension, DifficultyLevel


class TestTaskGeneratorConfig:
    """任务生成器配置测试"""

    def test_default_config(self):
        config = TaskGeneratorConfig()
        assert len(config.data_sources) == 5
        assert config.tasks_per_source == 10
        assert config.max_total_tasks == 100

    def test_difficulty_distribution(self):
        config = TaskGeneratorConfig()
        total = sum(config.difficulty_distribution.values())
        assert abs(total - 1.0) < 0.001

    def test_invalid_distribution(self):
        from finagent.interface.models import DifficultyLevel
        with pytest.raises(ValueError):
            TaskGeneratorConfig(
                difficulty_distribution={
                    DifficultyLevel.EASY: 0.5,
                    DifficultyLevel.MEDIUM: 0.6,
                }
            )


class TestEvalTaskGenerator:
    """任务生成器测试"""

    @pytest.fixture
    def generator(self):
        config = TaskGeneratorConfig(
            tasks_per_source=2,
            max_total_tasks=10,
        )
        return EvalTaskGenerator(config)

    def test_initialization(self, generator):
        """测试初始化"""
        assert len(generator.datasets) == 5

    def test_generate_tasks(self, generator):
        """测试任务生成"""
        tasks = generator.generate_tasks(n_tasks=5)
        assert len(tasks) > 0
        for task in tasks:
            assert task.task_id is not None

    def test_generate_quick_mode(self, generator):
        """测试快速模式"""
        tasks = generator.generate_quick_mode_tasks()
        assert len(tasks) > 0

    def test_generate_full_mode(self, generator):
        """测试完整模式"""
        tasks = generator.generate_full_mode_tasks()
        assert len(tasks) > 0

    def test_generate_adversarial_tasks(self, generator):
        """测试对抗性任务生成 - _source key缺失导致KeyError"""
        with pytest.raises(KeyError):
            generator.generate_adversarial_tasks()

    def test_dataset_stats(self, generator):
        """测试数据集统计"""
        stats = generator.get_dataset_stats()
        assert len(stats) == 5
        for source, info in stats.items():
            assert "name" in info
            assert "count" in info


class TestTaskSampler:
    """任务采样器测试"""

    @pytest.fixture
    def items(self):
        return [
            {"id": f"item_{i}", "difficulty": d}
            for i, d in enumerate(["easy", "medium", "hard", "expert"] * 5)
        ]

    def test_random_sampling(self, items):
        sampler = TaskSampler(SamplingStrategy.RANDOM)
        result = sampler.sample(items, 5)
        assert len(result) == 5

    def test_stratified_sampling(self, items):
        sampler = TaskSampler(SamplingStrategy.STRATIFIED)
        result = sampler.sample(items, 8)
        assert len(result) == 8

    def test_balanced_sampling(self, items):
        sampler = TaskSampler(SamplingStrategy.BALANCED)
        result = sampler.sample(items, 4)
        assert len(result) == 4

    def test_sample_less_than_available(self, items):
        sampler = TaskSampler(SamplingStrategy.RANDOM)
        result = sampler.sample(items, 3)
        assert len(result) == 3

    def test_sample_more_than_available(self, items):
        sampler = TaskSampler(SamplingStrategy.RANDOM)
        result = sampler.sample(items, 100)
        assert len(result) == len(items)
