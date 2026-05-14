"""
图表渲染模块

提供评测结果的可视化图表渲染功能。
"""

import base64
import math
from dataclasses import dataclass


@dataclass
class ChartConfig:
    """图表配置"""

    width: int = 800
    height: int = 600
    title: str = ""
    colors: list[str] = None

    def __post_init__(self):
        if self.colors is None:
            self.colors = [
                "#16213e",
                "#0f3460",
                "#e94560",
                "#533483",
                "#2b2e4a",
                "#8d99ae",
            ]


class ChartRenderer:
    """图表渲染器基类"""

    def __init__(self, config: ChartConfig | None = None):
        self.config = config or ChartConfig()

    def render(self, data: dict) -> str:
        """渲染图表，返回HTML/SVG字符串"""
        raise NotImplementedError


class RadarChart(ChartRenderer):
    """
    雷达图渲染器

    用于展示多维度评分的雷达图。
    """

    def render(self, data: dict) -> str:
        """渲染雷达图"""
        dimensions = list(data.keys())
        scores = list(data.values())

        # 生成SVG雷达图
        svg = self._generate_radar_svg(dimensions, scores)
        return svg

    def _generate_radar_svg(
        self,
        labels: list[str],
        values: list[float],
    ) -> str:
        """生成SVG雷达图"""

        n = len(labels)
        if n == 0:
            return "<p>无数据</p>"

        cx, cy = 300, 300
        max_r = 200

        # 计算每个维度的角度（从顶部开始，顺时针分布）
        angles = []
        for i in range(n):
            angle = (2 * math.pi * i / n) - math.pi / 2
            angles.append(angle)

        # 生成网格线（同心多边形）
        grid_lines = ""
        for level in [0.2, 0.4, 0.6, 0.8, 1.0]:
            r = max_r * level
            grid_points = []
            for angle in angles:
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                grid_points.append(f"{px:.2f},{py:.2f}")

            grid_lines += (
                f'<polygon points="{" ".join(grid_points)}" '
                f'fill="none" stroke="#ddd" stroke-width="1"/>'
            )

        # 生成从中心到各顶点的轴线
        axis_lines = ""
        for angle in angles:
            ex = cx + max_r * math.cos(angle)
            ey = cy + max_r * math.sin(angle)
            axis_lines += (
                f'<line x1="{cx}" y1="{cy}" x2="{ex:.2f}" y2="{ey:.2f}" '
                f'stroke="#ddd" stroke-width="1"/>'
            )

        # 生成数据多边形
        data_points = []
        for i, angle in enumerate(angles):
            val = values[i] / 100.0 if i < len(values) else 0
            r = max_r * val
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            data_points.append(f"{px:.2f},{py:.2f}")

        data_polygon = " ".join(data_points)

        # 生成标签（沿各维度方向放置在多边形外侧）
        labels_svg = ""
        for i, label in enumerate(labels):
            angle = angles[i]
            label_r = max_r + 25
            lx = cx + label_r * math.cos(angle)
            ly = cy + label_r * math.sin(angle)
            # 根据角度调整文本对齐方式
            if math.cos(angle) > 0.1:
                anchor = "start"
            elif math.cos(angle) < -0.1:
                anchor = "end"
            else:
                anchor = "middle"
            # 垂直微调
            dy = 4 if math.sin(angle) > 0 else -4
            score_text = f"{values[i]:.1f}" if i < len(values) else "N/A"
            labels_svg += (
                f'<text x="{lx:.2f}" y="{ly + dy:.2f}" '
                f'text-anchor="{anchor}" font-size="12">'
                f"{label}: {score_text}</text>"
            )

        return f"""<svg width="600" height="600" xmlns="http://www.w3.org/2000/svg">
    <rect width="600" height="600" fill="white"/>
    <text x="300" y="30" text-anchor="middle" font-size="18" font-weight="bold">{self.config.title or "维度评分雷达图"}</text>
    {grid_lines}
    {axis_lines}
    <polygon points="{data_polygon}" fill="rgba(233,69,96,0.3)" stroke="#e94560" stroke-width="2"/>
    {labels_svg}
</svg>"""


class ScoreBarChart(ChartRenderer):
    """
    分数柱状图渲染器
    """

    def render(self, data: dict) -> str:
        """渲染柱状图"""
        items = list(data.items()) if isinstance(data, dict) else data

        bars_html = ""
        max_score = 100

        for _i, (label, score) in enumerate(items):
            if isinstance(score, (int, float)):
                width_pct = (score / max_score) * 100
                color = self._score_color(score)
                bars_html += f"""
                <div class="bar-row">
                    <div class="bar-label">{label}</div>
                    <div class="bar-container">
                        <div class="bar" style="width: {width_pct}%; background-color: {color};"></div>
                    </div>
                    <div class="bar-value">{score:.1f}</div>
                </div>"""

        return f"""<div class="bar-chart" style="width: {self.config.width}px;">
            <h3>{self.config.title or "评分分布"}</h3>
            {bars_html}
            <style>
                .bar-row {{ display: flex; align-items: center; margin: 5px 0; }}
                .bar-label {{ width: 120px; font-size: 12px; text-align: right; padding-right: 10px; }}
                .bar-container {{ flex: 1; background: #eee; border-radius: 4px; height: 20px; }}
                .bar {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
                .bar-value {{ width: 50px; font-size: 12px; padding-left: 10px; }}
            </style>
        </div>"""

    def _score_color(self, score: float) -> str:
        """根据分数返回颜色"""
        if score >= 85:
            return "#28a745"  # 绿色
        if score >= 70:
            return "#17a2b8"  # 蓝色
        if score >= 60:
            return "#ffc107"  # 黄色
        return "#dc3545"  # 红色


class NetValueChart(ChartRenderer):
    """
    净值曲线渲染器

    用于展示投资策略的净值变化曲线。
    """

    def render(self, data: dict) -> str:
        """渲染净值曲线"""
        dates = data.get("dates", [])
        values = data.get("values", [])
        benchmark = data.get("benchmark", [])

        if not dates or not values:
            return "<p>无净值数据</p>"

        # 生成SVG折线图
        width = self.config.width
        height = self.config.height
        padding = 50

        chart_w = width - 2 * padding
        chart_h = height - 2 * padding

        n = len(dates)
        if n < 2:
            return "<p>数据不足</p>"

        all_vals = values + benchmark
        min_val = min(all_vals) * 0.99
        max_val = max(all_vals) * 1.01
        val_range = max_val - min_val if max_val != min_val else 1

        def to_x(i):
            return padding + (i / (n - 1)) * chart_w

        def to_y(v):
            return padding + chart_h - ((v - min_val) / val_range) * chart_h

        # 生成折线路径
        line_path = " ".join(f"M {to_x(i)} {to_y(v)}" for i, v in enumerate(values))

        # 基准线
        benchmark_path = ""
        if benchmark:
            benchmark_path = " ".join(f"M {to_x(i)} {to_y(v)}" for i, v in enumerate(benchmark))

        # X轴标签
        x_labels = ""
        step = max(1, n // 6)
        for i in range(0, n, step):
            x = to_x(i)
            y = height - padding + 20
            x_labels += (
                f'<text x="{x}" y="{y}" text-anchor="middle" font-size="10">{dates[i]}</text>'
            )

        # Y轴标签
        y_labels = ""
        for v in [min_val, (min_val + max_val) / 2, max_val]:
            y = to_y(v)
            y_labels += (
                f'<text x="{padding - 10}" y="{y}" text-anchor="end" font-size="10">{v:.2f}</text>'
            )
            y_labels += f'<line x1="{padding}" y1="{y}" x2="{width - padding}" y2="{y}" stroke="#eee" stroke-width="1"/>'

        benchmark_line = ""
        if benchmark_path:
            benchmark_line = f'<path d="{benchmark_path}" fill="none" stroke="#999" stroke-width="1.5" stroke-dasharray="5,5"/>'

        return f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="{width}" height="{height}" fill="white"/>
    <text x="{width / 2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{self.config.title or "净值曲线"}</text>
    {y_labels}
    {x_labels}
    {benchmark_line}
    <path d="{line_path}" fill="none" stroke="#e94560" stroke-width="2"/>
    <circle cx="{to_x(0)}" cy="{to_y(values[0])}" r="3" fill="#e94560"/>
    <circle cx="{to_x(-1)}" cy="{to_y(values[-1])}" r="3" fill="#e94560"/>
    <text x="{width - padding}" y="45" text-anchor="end" font-size="11" fill="#e94560">● 策略净值</text>
    {"<text x='" + str(width - padding) + "' y='60' text-anchor='end' font-size='11' fill='#999'>--- 基准</text>" if benchmark else ""}
</svg>"""


class AdversarialDecayChart(ChartRenderer):
    """
    对抗性衰减图表渲染器

    用于展示模型在不同对抗性难度级别下评分的衰减趋势。
    以垂直柱状图形式展示 baseline -> noisy -> meta_cognitive -> adversarial
    四个级别的分数变化，使用绿→黄→橙→红渐变色表示衰减程度。
    """

    # 四个对抗级别的渐变颜色（绿→黄→橙→红）
    LEVEL_COLORS = ["#28a745", "#ffc107", "#fd7e14", "#dc3545"]

    def render(self, data: list[dict]) -> str:
        """
        渲染对抗性衰减柱状图。

        Args:
            data: 包含以下键的字典列表:
                - level (str): 对抗级别名称
                - score (float): 该级别的得分
                - label (str): 显示标签

        Returns:
            SVG 字符串
        """
        if not data:
            return "<p>无对抗性衰减数据</p>"

        return self._generate_decay_svg(data)

    def to_base64(self, data: list[dict]) -> str:
        """将SVG图表编码为base64字符串，用于嵌入HTML"""
        svg_str = self.render(data)
        encoded = base64.b64encode(svg_str.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{encoded}"

    def _generate_decay_svg(self, data: list[dict]) -> str:
        """生成对抗性衰减SVG柱状图"""
        width = self.config.width
        height = self.config.height
        padding = 60

        chart_w = width - 2 * padding
        chart_h = height - 2 * padding - 30  # 底部留空给标签

        n = len(data)
        if n == 0:
            return "<p>无数据</p>"

        # 计算分数范围
        scores = [item["score"] for item in data]
        max_score = max(scores) * 1.1 if max(scores) > 0 else 100
        min_score = 0

        # 柱子参数
        bar_gap = chart_w * 0.15 / max(n, 1)
        bar_width = (chart_w - bar_gap * (n + 1)) / max(n, 1)

        # Y轴刻度
        y_ticks = 5
        y_labels = ""
        for i in range(y_ticks + 1):
            val = min_score + (max_score - min_score) * i / y_ticks
            y = padding + chart_h - (chart_h * i / y_ticks)
            y_labels += (
                f'<text x="{padding - 10}" y="{y + 4}" '
                f'text-anchor="end" font-size="11">{val:.1f}</text>'
            )
            y_labels += (
                f'<line x1="{padding}" y1="{y}" x2="{width - padding}" y2="{y}" '
                f'stroke="#eee" stroke-width="1"/>'
            )

        # 生成柱子和标签
        bars_svg = ""
        for i, item in enumerate(data):
            score = item["score"]
            label = item.get("label", item.get("level", f"Level {i}"))
            level = item.get("level", f"level_{i}")

            # 柱子位置
            x = padding + bar_gap + i * (bar_width + bar_gap)
            bar_h = (score / max_score) * chart_h
            y = padding + chart_h - bar_h

            # 根据索引选择颜色（最多4个级别）
            color = self.LEVEL_COLORS[min(i, len(self.LEVEL_COLORS) - 1)]

            # 绘制柱子（带圆角顶部效果）
            bars_svg += (
                f'<rect x="{x:.2f}" y="{y:.2f}" '
                f'width="{bar_width:.2f}" height="{bar_h:.2f}" '
                f'fill="{color}" rx="3" ry="3"/>'
            )

            # 在柱子上方显示分数
            bars_svg += (
                f'<text x="{x + bar_width / 2:.2f}" y="{y - 8}" '
                f'text-anchor="middle" font-size="13" font-weight="bold" '
                f'fill="{color}">{score:.1f}</text>'
            )

            # X轴标签（级别名称）
            label_y = padding + chart_h + 20
            bars_svg += (
                f'<text x="{x + bar_width / 2:.2f}" y="{label_y}" '
                f'text-anchor="middle" font-size="11" fill="#333">{label}</text>'
            )

            # X轴副标签（level key）
            bars_svg += (
                f'<text x="{x + bar_width / 2:.2f}" y="{label_y + 15}" '
                f'text-anchor="middle" font-size="9" fill="#999">{level}</text>'
            )

        # 绘制衰减趋势连线（连接各柱子顶部中点）
        if n >= 2:
            line_points = []
            for i, item in enumerate(data):
                score = item["score"]
                x = padding + bar_gap + i * (bar_width + bar_gap) + bar_width / 2
                bar_h = (score / max_score) * chart_h
                y = padding + chart_h - bar_h
                line_points.append(f"{x:.2f},{y:.2f}")

            path_d = "M " + " L ".join(line_points)
            bars_svg += (
                f'<path d="{path_d}" fill="none" stroke="#333" '
                f'stroke-width="1.5" stroke-dasharray="6,3" opacity="0.5"/>'
            )
            # 在连线节点上画小圆点
            for pt in line_points:
                bars_svg += (
                    f'<circle cx="{pt.split(",")[0]}" cy="{pt.split(",")[1]}" '
                    f'r="3" fill="#333" opacity="0.5"/>'
                )

        # Y轴标题
        y_axis_title = (
            f'<text x="15" y="{padding + chart_h / 2}" '
            f'text-anchor="middle" font-size="12" fill="#666" '
            f'transform="rotate(-90, 15, {padding + chart_h / 2})">分数</text>'
        )

        title = self.config.title or "对抗性衰减趋势"

        return f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="{width}" height="{height}" fill="white"/>
    <text x="{width / 2}" y="30" text-anchor="middle" font-size="16" font-weight="bold">{title}</text>
    {y_axis_title}
    {y_labels}
    {bars_svg}
    <!-- Y轴 -->
    <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{padding + chart_h}" stroke="#333" stroke-width="1.5"/>
    <!-- X轴 -->
    <line x1="{padding}" y1="{padding + chart_h}" x2="{width - padding}" y2="{padding + chart_h}" stroke="#333" stroke-width="1.5"/>
</svg>"""
