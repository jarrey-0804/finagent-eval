"""
judge/consensus.py 单元测试

测试共识构建器的各种共识方法、ICC计算、异常输入处理等。
"""

import pytest
import statistics

from finagent.judge.consensus import ConsensusBuilder, ConsensusResult
from finagent.judge.judge import ConsensusMethod, JudgeResult
from finagent.interface.models import EvalDimension


# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------

def _make_judge_result(score: float, dimension: EvalDimension = EvalDimension.ACCURACY) -> JudgeResult:
    """创建 JudgeResult 测试数据"""
    return JudgeResult(
        dimension=dimension,
        score=score,
        confidence=0.8,
        reasoning="test reasoning",
        evidence=["evidence1"],
        model_name="test-model",
        latency_ms=100.0,
    )


def _make_results(scores: list[float]) -> list[JudgeResult]:
    """批量创建 JudgeResult"""
    return [_make_judge_result(s) for s in scores]


# ---------------------------------------------------------------------------
# ConsensusBuilder 初始化
# ---------------------------------------------------------------------------

class TestConsensusBuilderInit:
    """测试 ConsensusBuilder 初始化"""

    def test_init_default_method(self):
        builder = ConsensusBuilder()
        assert builder.method == ConsensusMethod.WEIGHTED_AVERAGE

    def test_init_custom_method(self):
        builder = ConsensusBuilder(method=ConsensusMethod.MEDIAN)
        assert builder.method == ConsensusMethod.MEDIAN

    def test_init_custom_min_icc(self):
        builder = ConsensusBuilder(min_icc=0.9)
        assert builder.min_icc == 0.9

    def test_init_majority_vote(self):
        builder = ConsensusBuilder(method=ConsensusMethod.MAJORITY_VOTE)
        assert builder.method == ConsensusMethod.MAJORITY_VOTE

    def test_init_icc_based(self):
        builder = ConsensusBuilder(method=ConsensusMethod.ICC_BASED)
        assert builder.method == ConsensusMethod.ICC_BASED


# ---------------------------------------------------------------------------
# build 方法 - 空输入
# ---------------------------------------------------------------------------

class TestConsensusBuilderBuildEmpty:
    """测试空输入场景"""

    def test_build_empty_results(self):
        builder = ConsensusBuilder()
        result = builder.build([])
        assert isinstance(result, ConsensusResult)
        assert result.final_score == 0.0
        assert result.icc == 0.0
        assert result.individual_scores == []
        assert result.weights == []
        assert result.passed_icc_threshold is False

    def test_build_empty_results_default_weights(self):
        builder = ConsensusBuilder()
        result = builder.build([], weights=None)
        assert result.weights == []


# ---------------------------------------------------------------------------
# build 方法 - 加权平均
# ---------------------------------------------------------------------------

class TestConsensusBuilderWeightedAverage:
    """测试加权平均共识方法"""

    def test_build_weighted_average_equal_weights(self):
        builder = ConsensusBuilder(method=ConsensusMethod.WEIGHTED_AVERAGE)
        results = _make_results([80.0, 90.0, 70.0])
        result = builder.build(results)
        assert result.method == ConsensusMethod.WEIGHTED_AVERAGE
        assert result.final_score == pytest.approx(80.0)
        assert result.individual_scores == [80.0, 90.0, 70.0]

    def test_build_weighted_average_custom_weights(self):
        builder = ConsensusBuilder(method=ConsensusMethod.WEIGHTED_AVERAGE)
        results = _make_results([80.0, 90.0])
        result = builder.build(results, weights=[2.0, 1.0])
        # (80*2 + 90*1) / 3 = 83.33
        assert result.final_score == pytest.approx(250.0 / 3.0, abs=0.01)

    def test_build_weighted_average_single_result(self):
        builder = ConsensusBuilder(method=ConsensusMethod.WEIGHTED_AVERAGE)
        results = _make_results([75.0])
        result = builder.build(results)
        assert result.final_score == pytest.approx(75.0)
        assert result.icc == 1.0  # 单个分数 ICC 为 1.0

    def test_build_weighted_average_zero_weights(self):
        """权重全为零时回退到简单平均"""
        builder = ConsensusBuilder(method=ConsensusMethod.WEIGHTED_AVERAGE)
        results = _make_results([80.0, 90.0])
        result = builder.build(results, weights=[0.0, 0.0])
        assert result.final_score == pytest.approx(85.0)


# ---------------------------------------------------------------------------
# build 方法 - 中位数
# ---------------------------------------------------------------------------

class TestConsensusBuilderMedian:
    """测试中位数共识方法"""

    def test_build_median_odd_count(self):
        builder = ConsensusBuilder(method=ConsensusMethod.MEDIAN)
        results = _make_results([70.0, 80.0, 90.0])
        result = builder.build(results)
        assert result.final_score == pytest.approx(80.0)

    def test_build_median_even_count(self):
        builder = ConsensusBuilder(method=ConsensusMethod.MEDIAN)
        results = _make_results([70.0, 80.0, 90.0, 100.0])
        result = builder.build(results)
        assert result.final_score == pytest.approx(85.0)


# ---------------------------------------------------------------------------
# build 方法 - 多数投票
# ---------------------------------------------------------------------------

class TestConsensusBuilderMajorityVote:
    """测试多数投票共识方法"""

    def test_build_majority_vote_clear_winner(self):
        builder = ConsensusBuilder(method=ConsensusMethod.MAJORITY_VOTE)
        # 三个分数都在 60-80 区间
        results = _make_results([65.0, 70.0, 75.0])
        result = builder.build(results)
        # 所有分数都落在 60-80 bin，中值为 70
        assert result.final_score == pytest.approx(70.0)

    def test_build_majority_vote_different_bins(self):
        builder = ConsensusBuilder(method=ConsensusMethod.MAJORITY_VOTE)
        # 两个在 60-80，一个在 80-100
        results = _make_results([65.0, 70.0, 85.0])
        result = builder.build(results)
        # 65 和 70 都 bin 到 70，85 bin 到 90；众数为 70
        assert result.final_score == pytest.approx(70.0)

    def test_build_majority_vote_score_at_100(self):
        builder = ConsensusBuilder(method=ConsensusMethod.MAJORITY_VOTE)
        # 分数恰好为 100，走 else 分支 -> binned.append(90)
        results = _make_results([100.0])
        result = builder.build(results)
        assert result.final_score == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# build 方法 - ICC 基于加权
# ---------------------------------------------------------------------------

class TestConsensusBuilderICCBased:
    """测试基于 ICC 的加权共识方法"""

    def test_build_icc_based_high_icc(self):
        """高 ICC 时权重接近均匀"""
        builder = ConsensusBuilder(method=ConsensusMethod.ICC_BASED)
        # 相同分数 -> ICC = 1.0
        results = _make_results([80.0, 80.0, 80.0])
        result = builder.build(results, weights=[1.0, 1.0, 1.0])
        assert result.final_score == pytest.approx(80.0)
        assert result.icc == pytest.approx(1.0)

    def test_build_icc_based_low_icc(self):
        """低 ICC 时权重差异增大"""
        builder = ConsensusBuilder(method=ConsensusMethod.ICC_BASED)
        results = _make_results([50.0, 100.0])
        result = builder.build(results, weights=[1.0, 2.0])
        # ICC 较低，但仍然应该计算出合理分数
        assert 50.0 <= result.final_score <= 100.0


# ---------------------------------------------------------------------------
# ICC 计算
# ---------------------------------------------------------------------------

class TestCalculateICC:
    """测试 ICC 计算"""

    def test_icc_single_score(self):
        builder = ConsensusBuilder()
        icc = builder._calculate_icc([80.0])
        assert icc == 1.0

    def test_icc_identical_scores(self):
        builder = ConsensusBuilder()
        icc = builder._calculate_icc([80.0, 80.0, 80.0])
        assert icc == pytest.approx(1.0)

    def test_icc_zero_mean(self):
        builder = ConsensusBuilder()
        icc = builder._calculate_icc([0.0, 0.0])
        assert icc == 0.0

    def test_icc_high_variance(self):
        builder = ConsensusBuilder()
        icc = builder._calculate_icc([10.0, 100.0])
        assert 0.0 <= icc < 1.0

    def test_icc_bounded(self):
        """ICC 值应在 [0, 1] 范围内"""
        builder = ConsensusBuilder()
        for scores in [[1.0, 2.0, 3.0], [10.0, 90.0], [50.0, 50.0]]:
            icc = builder._calculate_icc(scores)
            assert 0.0 <= icc <= 1.0


# ---------------------------------------------------------------------------
# ICC 阈值检查
# ---------------------------------------------------------------------------

class TestICCThreshold:
    """测试 ICC 阈值判断"""

    def test_passed_icc_threshold_high_icc(self):
        builder = ConsensusBuilder(min_icc=0.75)
        results = _make_results([80.0, 80.0, 80.0])
        result = builder.build(results)
        assert result.passed_icc_threshold is True

    def test_passed_icc_threshold_low_icc(self):
        builder = ConsensusBuilder(min_icc=0.99)
        results = _make_results([50.0, 100.0])
        result = builder.build(results)
        assert result.passed_icc_threshold is False


# ---------------------------------------------------------------------------
# ConsensusResult 数据类
# ---------------------------------------------------------------------------

class TestConsensusResult:
    """测试 ConsensusResult 数据类"""

    def test_result_fields(self):
        builder = ConsensusBuilder()
        results = _make_results([80.0, 90.0])
        result = builder.build(results, weights=[1.0, 2.0])
        assert result.final_score > 0
        assert result.method == ConsensusMethod.WEIGHTED_AVERAGE
        assert len(result.individual_scores) == 2
        assert len(result.weights) == 2
        assert isinstance(result.passed_icc_threshold, bool)

    def test_result_to_dict_not_required(self):
        """ConsensusResult 是 dataclass，可以直接访问属性"""
        builder = ConsensusBuilder()
        results = _make_results([80.0])
        result = builder.build(results)
        assert hasattr(result, 'final_score')
        assert hasattr(result, 'icc')
        assert hasattr(result, 'method')


# ---------------------------------------------------------------------------
# 边界条件
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """测试边界条件"""

    def test_very_high_scores(self):
        builder = ConsensusBuilder()
        results = _make_results([99.0, 100.0, 98.0])
        result = builder.build(results)
        assert result.final_score > 95.0

    def test_very_low_scores(self):
        builder = ConsensusBuilder()
        results = _make_results([1.0, 2.0, 3.0])
        result = builder.build(results)
        assert result.final_score < 10.0

    def test_many_results(self):
        builder = ConsensusBuilder()
        scores = list(range(50, 100, 5))  # 10 个分数
        results = _make_results(scores)
        result = builder.build(results)
        assert len(result.individual_scores) == 10
        assert result.final_score == pytest.approx(statistics.mean(scores))

    def test_mixed_dimensions(self):
        """不同维度的评分结果"""
        builder = ConsensusBuilder()
        results = [
            _make_judge_result(80.0, EvalDimension.ACCURACY),
            _make_judge_result(70.0, EvalDimension.COMPLETENESS),
        ]
        result = builder.build(results)
        assert result.final_score == pytest.approx(75.0)
