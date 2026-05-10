"""
report/charts.py 单元测试

测试图表渲染模块：ChartConfig、RadarChart、ScoreBarChart、
NetValueChart、AdversarialDecayChart 的渲染功能。
"""

import base64
import re
from unittest.mock import patch

import pytest

from finagent.report.charts import (
    AdversarialDecayChart,
    ChartConfig,
    ChartRenderer,
    NetValueChart,
    RadarChart,
    ScoreBarChart,
)


# ---------------------------------------------------------------------------
# ChartConfig 测试
# ---------------------------------------------------------------------------

class TestChartConfig:

    def test_default_values(self):
        """默认配置值"""
        config = ChartConfig()
        assert config.width == 800
        assert config.height == 600
        assert config.title == ""
        assert config.colors is not None
        assert len(config.colors) == 6

    def test_custom_values(self):
        """自定义配置值"""
        config = ChartConfig(width=1024, height=768, title="测试图表")
        assert config.width == 1024
        assert config.height == 768
        assert config.title == "测试图表"

    def test_default_colors_list(self):
        """默认颜色列表应包含预期颜色"""
        config = ChartConfig()
        assert "#16213e" in config.colors
        assert "#e94560" in config.colors


# ---------------------------------------------------------------------------
# ChartRenderer 基类测试
# ---------------------------------------------------------------------------

class TestChartRenderer:

    def test_render_not_implemented(self):
        """基类 render 应抛出 NotImplementedError"""
        renderer = ChartRenderer()
        with pytest.raises(NotImplementedError):
            renderer.render({})


# ---------------------------------------------------------------------------
# RadarChart 测试
# ---------------------------------------------------------------------------

class TestRadarChart:

    def test_render_empty_data(self):
        """空数据应返回无数据提示"""
        chart = RadarChart()
        result = chart.render({})
        assert "<p>无数据</p>" in result

    def test_render_single_dimension(self):
        """单维度应生成 SVG"""
        chart = RadarChart()
        result = chart.render({"准确性": 85.0})
        assert "<svg" in result
        assert "准确性" in result
        assert "85.0" in result

    def test_render_multiple_dimensions(self):
        """多维度应生成包含所有维度的 SVG"""
        chart = RadarChart()
        data = {"准确性": 85.0, "完整性": 70.0, "推理能力": 90.0}
        result = chart.render(data)
        assert "<svg" in result
        assert "准确性" in result
        assert "完整性" in result
        assert "推理能力" in result

    def test_render_with_custom_title(self):
        """自定义标题应出现在 SVG 中"""
        config = ChartConfig(title="自定义雷达图")
        chart = RadarChart(config=config)
        result = chart.render({"准确性": 80.0})
        assert "自定义雷达图" in result

    def test_render_default_title(self):
        """默认标题应为'维度评分雷达图'"""
        chart = RadarChart()
        result = chart.render({"准确性": 80.0})
        assert "维度评分雷达图" in result

    def test_render_contains_polygon(self):
        """SVG 应包含数据多边形"""
        chart = RadarChart()
        result = chart.render({"准确性": 80.0, "完整性": 60.0})
        assert "polygon" in result

    def test_render_contains_grid_lines(self):
        """SVG 应包含网格线"""
        chart = RadarChart()
        result = chart.render({"准确性": 80.0})
        assert "stroke" in result

    def test_generate_radar_svg_zero_values(self):
        """零值应正常渲染"""
        chart = RadarChart()
        result = chart.render({"准确性": 0.0, "完整性": 0.0})
        assert "<svg" in result


# ---------------------------------------------------------------------------
# ScoreBarChart 测试
# ---------------------------------------------------------------------------

class TestScoreBarChart:

    def test_render_empty_data(self):
        """空数据应生成 HTML（无柱子）"""
        chart = ScoreBarChart()
        result = chart.render({})
        assert "bar-chart" in result
        assert "评分分布" in result

    def test_render_single_bar(self):
        """单条柱应渲染"""
        chart = ScoreBarChart()
        result = chart.render({"准确性": 85.0})
        assert "准确性" in result
        assert "85.0" in result
        assert "bar" in result

    def test_render_multiple_bars(self):
        """多条柱应渲染"""
        chart = ScoreBarChart()
        data = {"准确性": 85.0, "完整性": 70.0, "推理能力": 90.0}
        result = chart.render(data)
        assert "准确性" in result
        assert "完整性" in result
        assert "推理能力" in result

    def test_score_color_green(self):
        """85 分以上应为绿色"""
        chart = ScoreBarChart()
        assert chart._score_color(85.0) == "#28a745"
        assert chart._score_color(100.0) == "#28a745"

    def test_score_color_blue(self):
        """70-84 分应为蓝色"""
        chart = ScoreBarChart()
        assert chart._score_color(70.0) == "#17a2b8"
        assert chart._score_color(84.0) == "#17a2b8"

    def test_score_color_yellow(self):
        """60-69 分应为黄色"""
        chart = ScoreBarChart()
        assert chart._score_color(60.0) == "#ffc107"
        assert chart._score_color(69.0) == "#ffc107"

    def test_score_color_red(self):
        """60 分以下应为红色"""
        chart = ScoreBarChart()
        assert chart._score_color(59.0) == "#dc3545"
        assert chart._score_color(0.0) == "#dc3545"

    def test_render_with_custom_title(self):
        """自定义标题应出现在 HTML 中"""
        config = ChartConfig(title="自定义评分")
        chart = ScoreBarChart(config=config)
        result = chart.render({"准确性": 80.0})
        assert "自定义评分" in result

    def test_render_contains_css(self):
        """HTML 应包含内联 CSS"""
        chart = ScoreBarChart()
        result = chart.render({"准确性": 80.0})
        assert "bar-row" in result
        assert "bar-container" in result


# ---------------------------------------------------------------------------
# NetValueChart 测试
# ---------------------------------------------------------------------------

class TestNetValueChart:

    def test_render_empty_data(self):
        """空数据应返回无数据提示"""
        chart = NetValueChart()
        result = chart.render({"dates": [], "values": []})
        assert "无净值数据" in result

    def test_render_single_point(self):
        """单点数据应返回数据不足提示"""
        chart = NetValueChart()
        result = chart.render({"dates": ["2024-01-01"], "values": [1.0]})
        assert "数据不足" in result

    def test_render_valid_data(self):
        """有效数据应生成 SVG"""
        chart = NetValueChart()
        data = {
            "dates": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "values": [1.0, 1.05, 1.03],
        }
        result = chart.render(data)
        assert "<svg" in result
        assert "2024-01-01" in result

    def test_render_with_benchmark(self):
        """包含基准数据时应渲染基准线"""
        chart = NetValueChart()
        data = {
            "dates": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "values": [1.0, 1.05, 1.03],
            "benchmark": [1.0, 1.02, 1.01],
        }
        result = chart.render(data)
        assert "基准" in result
        assert "stroke-dasharray" in result

    def test_render_without_benchmark(self):
        """不包含基准数据时不应显示基准标签"""
        chart = NetValueChart()
        data = {
            "dates": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "values": [1.0, 1.05, 1.03],
        }
        result = chart.render(data)
        assert "基准" not in result

    def test_render_custom_config(self):
        """自定义配置应影响 SVG 尺寸"""
        config = ChartConfig(width=1024, height=768, title="自定义净值")
        chart = NetValueChart(config=config)
        data = {
            "dates": ["2024-01-01", "2024-01-02"],
            "values": [1.0, 1.05],
        }
        result = chart.render(data)
        assert 'width="1024"' in result
        assert 'height="768"' in result
        assert "自定义净值" in result

    def test_render_default_title(self):
        """默认标题应为'净值曲线'"""
        chart = NetValueChart()
        data = {
            "dates": ["2024-01-01", "2024-01-02"],
            "values": [1.0, 1.05],
        }
        result = chart.render(data)
        assert "净值曲线" in result


# ---------------------------------------------------------------------------
# AdversarialDecayChart 测试
# ---------------------------------------------------------------------------

class TestAdversarialDecayChart:

    def _make_sample_data(self):
        """创建示例对抗性衰减数据"""
        return [
            {"level": "baseline", "score": 85.0, "label": "基线"},
            {"level": "noisy", "score": 72.0, "label": "噪声"},
            {"level": "meta_cognitive", "score": 55.0, "label": "元认知"},
            {"level": "adversarial", "score": 35.0, "label": "对抗"},
        ]

    def test_render_empty_data(self):
        """空数据应返回无数据提示"""
        chart = AdversarialDecayChart()
        result = chart.render([])
        assert "无对抗性衰减数据" in result

    def test_render_valid_data(self):
        """有效数据应生成 SVG"""
        chart = AdversarialDecayChart()
        result = chart.render(self._make_sample_data())
        assert "<svg" in result
        assert "基线" in result
        assert "噪声" in result

    def test_render_contains_bars(self):
        """SVG 应包含柱状图元素"""
        chart = AdversarialDecayChart()
        result = chart.render(self._make_sample_data())
        assert "<rect" in result

    def test_render_contains_score_labels(self):
        """SVG 应包含分数标签"""
        chart = AdversarialDecayChart()
        result = chart.render(self._make_sample_data())
        assert "85.0" in result
        assert "72.0" in result

    def test_render_contains_decay_line(self):
        """多数据点应包含衰减趋势连线"""
        chart = AdversarialDecayChart()
        result = chart.render(self._make_sample_data())
        assert "stroke-dasharray" in result

    def test_to_base64(self):
        """to_base64 应返回 base64 编码的 data URI"""
        chart = AdversarialDecayChart()
        result = chart.to_base64(self._make_sample_data())
        assert result.startswith("data:image/svg+xml;base64,")
        # 解码验证是有效的 SVG
        encoded = result.replace("data:image/svg+xml;base64,", "")
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert "<svg" in decoded

    def test_level_colors(self):
        """LEVEL_COLORS 应有4个颜色"""
        assert len(AdversarialDecayChart.LEVEL_COLORS) == 4
        assert AdversarialDecayChart.LEVEL_COLORS[0] == "#28a745"  # 绿
        assert AdversarialDecayChart.LEVEL_COLORS[3] == "#dc3545"  # 红

    def test_render_custom_title(self):
        """自定义标题应出现在 SVG 中"""
        config = ChartConfig(title="自定义衰减图")
        chart = AdversarialDecayChart(config=config)
        result = chart.render(self._make_sample_data())
        assert "自定义衰减图" in result

    def test_render_single_data_point(self):
        """单数据点应正常渲染（无连线）"""
        chart = AdversarialDecayChart()
        data = [{"level": "baseline", "score": 85.0, "label": "基线"}]
        result = chart.render(data)
        assert "<svg" in result
        assert "基线" in result
        # 单点不应有趋势连线
        assert "stroke-dasharray" not in result
