"""
评测报告生成器

生成完整的评测报告，支持多种输出格式。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime

from .._compat import StrEnum


class ReportFormat(StrEnum):
    """报告格式"""

    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"


@dataclass
class ReportSection:
    """报告章节"""

    title: str
    content: str
    order: int = 0
    charts: list[dict] = field(default_factory=list)


class ReportGenerator:
    """
    评测报告生成器

    根据评测结果生成结构化的评测报告。
    """

    def __init__(self, include_details: bool = True):
        self.include_details = include_details

    def generate(
        self,
        evaluation_data: dict,
        format: ReportFormat = ReportFormat.MARKDOWN,
    ) -> str:
        """
        生成评测报告

        Args:
            evaluation_data: 评测数据（来自PipelineResult）
            format: 输出格式

        当 eval_mode 为 "quick" 时，跳过雷达图和对抗性测试章节，
        仅包含概要、维度评分、任务详情和改进建议。
        """
        is_quick = evaluation_data.get("eval_mode") == "quick"
        sections = self._build_sections(evaluation_data, skip_adversarial=is_quick)

        if format == ReportFormat.JSON:
            return self._render_json(evaluation_data, sections)
        elif format == ReportFormat.MARKDOWN:
            return self._render_markdown(sections, evaluation_data)
        elif format == ReportFormat.HTML:
            return self._render_html(sections, evaluation_data)

        return self._render_markdown(sections, evaluation_data)

    def _build_sections(self, data: dict, skip_adversarial: bool = False) -> list[ReportSection]:
        """构建报告章节"""
        sections = []

        # 1. 概要
        sections.append(
            ReportSection(
                title="评测概要",
                content=self._build_summary(data),
                order=1,
            )
        )

        # 2. 维度评分（quick模式下不包含雷达图）
        if "dimension_scores" in data:
            charts = (
                [] if skip_adversarial else [{"type": "radar", "data": data["dimension_scores"]}]
            )
            sections.append(
                ReportSection(
                    title="维度评分详情",
                    content=self._build_dimension_scores(data),
                    order=2,
                    charts=charts,
                )
            )

        # 3. 任务详情
        if self.include_details and "task_details" in data:
            sections.append(
                ReportSection(
                    title="任务评测详情",
                    content=self._build_task_details(data),
                    order=3,
                    charts=[{"type": "bar", "data": data["task_details"]}],
                )
            )

        # 4. 对抗性测试（quick模式下跳过）
        if not skip_adversarial and "adversarial_results" in data:
            sections.append(
                ReportSection(
                    title="对抗性测试结果",
                    content=self._build_adversarial_section(data),
                    order=4,
                )
            )

        # 5. 改进建议
        if "recommendations" in data:
            sections.append(
                ReportSection(
                    title="改进建议",
                    content=self._build_recommendations(data["recommendations"]),
                    order=5,
                )
            )

        sections.sort(key=lambda s: s.order)
        return sections

    def _build_summary(self, data: dict) -> str:
        """构建概要章节"""
        summary = data.get("summary", {})

        lines = [
            f"**Agent ID**: {data.get('agent_id', 'N/A')}",
            f"**评测模式**: {data.get('eval_mode', 'N/A')}",
            f"**评测时间**: {data.get('generated_at', datetime.now().isoformat())}",
            "",
            "| 指标 | 值 |",
            "|------|------|",
            f"| 总体分数 | {summary.get('overall_score', 'N/A')} |",
            f"| 评级 | **{summary.get('overall_rating', 'N/A')}** |",
            f"| 总任务数 | {summary.get('total_tasks', 'N/A')} |",
            f"| 通过任务数 | {summary.get('passed_tasks', 'N/A')} |",
            f"| 通过率 | {summary.get('pass_rate', 'N/A')} |",
            f"| 一票否决次数 | {summary.get('veto_count', 0)} |",
        ]

        return "\n".join(lines)

    def _build_dimension_scores(self, data: dict) -> str:
        """构建维度评分章节"""
        dim_scores = data.get("dimension_scores", {})

        lines = [
            "| 维度 | 分数 | 等级 |",
            "|------|------|------|",
        ]

        for dim, score in dim_scores.items():
            level = self._score_to_level(score)
            lines.append(f"| {dim} | {score:.1f} | {level} |")

        return "\n".join(lines)

    def _build_task_details(self, data: dict) -> str:
        """构建任务详情章节"""
        tasks = data.get("task_details", [])

        lines = []
        for i, task in enumerate(tasks, 1):
            veto_mark = " ⚠️" if task.get("veto_triggered") else ""
            lines.append(
                f"### 任务 {i}: {task.get('task_id', 'N/A')}{veto_mark}\n"
                f"- **分数**: {task.get('overall_score', 'N/A')}\n"
                f"- **评级**: {task.get('rating', 'N/A')}\n"
            )

            if task.get("veto_triggered"):
                lines.append(f"- **否决原因**: {task.get('veto_reason', 'N/A')}\n")

        return "\n".join(lines)

    def _build_adversarial_section(self, data: dict) -> str:
        """构建对抗性测试章节"""
        adv = data.get("adversarial_results", {})

        lines = [
            "| 指标 | 值 |",
            "|------|------|",
            f"| 总攻击数 | {adv.get('total_attacks', 0)} |",
            f"| 成功攻击数 | {adv.get('successful_attacks', 0)} |",
            f"| 漏洞率 | {adv.get('vulnerability_rate', 0):.1%} |",
            f"| 安全分数 | {adv.get('security_score', 0):.1f} |",
        ]

        return "\n".join(lines)

    def _build_recommendations(self, recommendations: list) -> str:
        """构建建议章节"""
        lines = []
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        return "\n".join(lines)

    def _render_json(self, data: dict, sections: list[ReportSection]) -> str:
        """渲染为JSON"""
        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "format": "json",
            },
            "evaluation_data": data,
            "sections": [
                {"title": s.title, "content": s.content, "charts": s.charts} for s in sections
            ],
        }
        return json.dumps(report, ensure_ascii=False, indent=2)

    def _render_markdown(self, sections: list[ReportSection], data: dict) -> str:
        """渲染为Markdown"""
        lines = [
            "# 金融AI Agent评测报告",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
        ]

        for section in sections:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")

        lines.append("---")
        lines.append("*报告由 FinAgent-Eval 评测系统自动生成*")

        return "\n".join(lines)

    def _render_html(self, sections: list[ReportSection], data: dict) -> str:
        """渲染为HTML"""
        sections_html = ""
        for section in sections:
            sections_html += f"""
            <section class="report-section">
                <h2>{section.title}</h2>
                <div class="section-content">
                    {self._markdown_to_html(section.content)}
                </div>
            </section>
            """

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>金融AI Agent评测报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
        h2 {{ color: #16213e; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background-color: #16213e; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .report-section {{ margin-bottom: 30px; }}
        .footer {{ margin-top: 40px; color: #666; font-size: 12px; text-align: center; }}
    </style>
</head>
<body>
    <h1>金融AI Agent评测报告</h1>
    <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    <hr>
    {sections_html}
    <div class="footer">报告由 FinAgent-Eval 评测系统自动生成</div>
</body>
</html>"""

    def _markdown_to_html(self, md: str) -> str:
        """简单Markdown转HTML"""
        import re

        html = md
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\|(.+)\|", lambda m: self._table_row_to_html(m.group(0)), html)
        html = html.replace("\n", "<br>")
        return html

    def _table_row_to_html(self, row: str) -> str:
        """表格行转HTML"""
        cells = [c.strip() for c in row.strip("|").split("|")]
        if all(set(c) <= {"-", " ", ":"} for c in cells):
            return ""  # 分隔行
        tag = "th" if "---" in row else "td"
        return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"

    def _score_to_level(self, score: float) -> str:
        """分数转等级"""
        if score >= 95:
            return "S (卓越)"
        if score >= 85:
            return "A (优秀)"
        if score >= 70:
            return "B (良好)"
        if score >= 60:
            return "C (合格)"
        return "D (不合格)"
