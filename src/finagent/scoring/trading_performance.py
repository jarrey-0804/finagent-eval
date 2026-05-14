"""
交易绩效评分指标模块

实现基于交易数据的绩效评分指标，包括：
- CR (Cumulative Return / 累计收益率)
- SR (Sharpe Ratio / 夏普比率)
- MDD (Maximum Drawdown / 最大回撤)
- WinRate (胜率)
"""

import logging
import math

from ..interface.models import EvalDimension, EvalResponse, EvalTask
from .engine import BaseMetric

logger = logging.getLogger(__name__)


class TradingPerformanceMetric(BaseMetric):
    """交易绩效评分指标"""

    def __init__(self):
        super().__init__(EvalDimension.REASONING)

    @property
    def name(self) -> str:
        return "交易绩效"

    @property
    def description(self) -> str:
        return "基于交易数据评估累计收益率、夏普比率、最大回撤和胜率"

    def compute(
        self,
        task: EvalTask,
        response: EvalResponse,
        reference: str | None = None,
    ) -> tuple[float, float, list[str], str]:
        """
        计算交易绩效评分

        从 response.tool_calls 或 response.output 中提取交易数据，
        计算 CR / SR / MDD / WinRate 四个指标，并映射为 0-100 分。

        Returns:
            tuple: (score, confidence, evidence, reasoning)
        """
        evidence: list[str] = []
        reasoning_parts: list[str] = []

        # --- 提取交易数据 ---
        trading_data = self._extract_trading_data(task, response)

        if trading_data is None:
            # 没有交易数据，返回默认分数
            return 50.0, 0.3, ["未找到交易数据"], "无法提取交易数据，使用默认分数"

        try:
            # --- 计算四个指标 ---
            cr = self._calc_cumulative_return(trading_data)
            sr = self._calc_sharpe_ratio(trading_data)
            mdd = self._calc_max_drawdown(trading_data)
            win_rate = self._calc_win_rate(trading_data)

            evidence.append(f"累计收益率(CR): {cr:.2f}%")
            evidence.append(f"夏普比率(SR): {sr:.4f}")
            evidence.append(f"最大回撤(MDD): {mdd:.2f}%")
            evidence.append(f"胜率(WinRate): {win_rate:.2f}%")

            # --- 映射为 0-100 分 ---
            score = self._aggregate_score(cr, sr, mdd, win_rate)
            confidence = self._calc_confidence(trading_data)

            reasoning_parts.append(
                f"CR={cr:.2f}%, SR={sr:.4f}, MDD={mdd:.2f}%, WinRate={win_rate:.2f}%"
            )
            reasoning_parts.append(f"综合评分={score:.1f}")

        except Exception as e:
            logger.warning("计算交易绩效指标时出错: %s", e)
            return 50.0, 0.2, [f"计算错误: {e}"], f"交易绩效计算异常: {e}"

        score = max(0.0, min(100.0, score))
        reasoning = "；".join(reasoning_parts)
        return score, confidence, evidence, reasoning

    # ------------------------------------------------------------------
    # 数据提取
    # ------------------------------------------------------------------

    def _extract_trading_data(self, task: EvalTask, response: EvalResponse) -> dict | None:
        """
        从 response.tool_calls 或 response.output 中提取交易数据。

        依次尝试从 tool_calls、output 文本、task context 提取。

        Returns:
            提取到的交易数据字典，或 None。
        """
        result = self._extract_from_tool_calls(response)
        if result is None:
            result = self._extract_from_output(response.output or "")
        if result is None:
            result = self._extract_from_context(task)
        return result

    def _extract_from_tool_calls(self, response: EvalResponse) -> dict | None:
        """从 response.tool_calls 中提取交易数据。"""
        if response.tool_calls:
            for tc in response.tool_calls:
                result = tc.get("output") or tc.get("result") or {}
                if isinstance(result, dict) and (
                    result.get("trades") or result.get("portfolio_values")
                ):
                    return result
        return None

    def _extract_from_output(self, output: str) -> dict | None:
        """从 output 文本中尝试解析 JSON 提取交易数据。"""
        if not output:
            return None
        import json
        import re

        json_blocks = re.findall(r"\{[^{}]*\}", output)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict) and (
                    data.get("trades") or data.get("portfolio_values")
                ):
                    return data
            except (json.JSONDecodeError, ValueError):
                continue
        return None

    def _extract_from_context(self, task: EvalTask) -> dict | None:
        """从 task context 中查找交易数据。"""
        context = task.context or {}
        if context.get("trades") or context.get("portfolio_values"):
            return context
        return None

    # ------------------------------------------------------------------
    # 指标计算
    # ------------------------------------------------------------------

    def _calc_cumulative_return(self, data: dict) -> float:
        """CR (Cumulative Return / 累计收益率): (final - initial) / initial * 100"""
        portfolio_values = data.get("portfolio_values")
        if portfolio_values and len(portfolio_values) >= 2:
            initial = float(portfolio_values[0])
            final = float(portfolio_values[-1])
            if initial != 0:
                return (final - initial) / abs(initial) * 100

        # 从 trades 累加
        trades = data.get("trades", [])
        if trades:
            trade_initial: float | None = data.get("initial_value")
            trade_final: float | None = data.get("final_value")
            if trade_initial is not None and trade_final is not None and trade_initial != 0:
                return (float(trade_final) - float(trade_initial)) / abs(float(trade_initial)) * 100

            # 从每笔交易的 return_rate 累乘
            total_return = 1.0
            for t in trades:
                rr = t.get("return_rate", 0)
                total_return *= 1 + rr
            return (total_return - 1) * 100

        return 0.0

    def _calc_sharpe_ratio(self, data: dict, risk_free_rate: float = 0.02) -> float:
        """SR (Sharpe Ratio / 夏普比率): (mean_return - risk_free_rate) / std_return"""
        trades = data.get("trades", [])
        portfolio_values = data.get("portfolio_values")

        returns: list[float] = []

        if portfolio_values and len(portfolio_values) >= 2:
            for i in range(1, len(portfolio_values)):
                prev = portfolio_values[i - 1]
                if prev != 0:
                    returns.append((portfolio_values[i] - prev) / abs(prev))

        if not returns and trades:
            returns = [t.get("return_rate", 0) for t in trades]

        if len(returns) < 2:
            return 0.0

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_ret = math.sqrt(variance) if variance > 0 else 0.0

        if std_ret == 0:
            return 0.0

        # 年化处理：假设 252 个交易日
        annual_factor = math.sqrt(252)
        annualized_mean = mean_ret * 252
        annualized_std = std_ret * annual_factor

        if annualized_std == 0:
            return 0.0

        return (annualized_mean - risk_free_rate) / annualized_std

    def _calc_max_drawdown(self, data: dict) -> float:
        """MDD (Maximum Drawdown / 最大回撤): max peak-to-trough decline (%)"""
        portfolio_values = data.get("portfolio_values")
        trades = data.get("trades", [])

        values: list[float] = []

        if portfolio_values and len(portfolio_values) >= 2:
            values = portfolio_values
        elif trades:
            # 从 trades 的 pnl 累积构建净值曲线
            cumulative = data.get("initial_value", 10000.0)
            values = [cumulative]
            for t in trades:
                cumulative += t.get("pnl", 0)
                values.append(cumulative)

        if len(values) < 2:
            return 0.0

        peak = values[0]
        max_dd = 0.0

        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / abs(peak) * 100 if peak != 0 else 0
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _calc_win_rate(self, data: dict) -> float:
        """WinRate (胜率): 盈利交易数 / 总交易数 * 100"""
        trades = data.get("trades", [])
        if not trades:
            return 0.0

        wins = 0
        for t in trades:
            pnl = t.get("pnl", 0)
            ret = t.get("return_rate", 0)
            if pnl > 0 or ret > 0:
                wins += 1

        return wins / len(trades) * 100

    # ------------------------------------------------------------------
    # 评分映射
    # ------------------------------------------------------------------

    def _aggregate_score(self, cr: float, sr: float, mdd: float, win_rate: float) -> float:
        """
        将四个指标映射为 0-100 综合评分。

        评分规则：
        - CR: 正收益加分，负收益扣分
        - SR: >1 优秀，>0.5 良好，<0 差
        - MDD: <10% 优秀，<20% 良好，>30% 差
        - WinRate: >60% 优秀，>50% 良好，<40% 差
        """
        score = 50.0
        score += self._score_cr(cr)
        score += self._score_sr(sr)
        score += self._score_mdd(mdd)
        score += self._score_win_rate(win_rate)
        return max(0.0, min(100.0, score))

    def _score_cr(self, cr: float) -> float:
        """CR 评分 (权重 25%)"""
        if cr > 20:
            return 15
        elif cr > 10:
            return 10
        elif cr > 0:
            return 5
        elif cr > -10:
            return -5
        else:
            return -15

    def _score_sr(self, sr: float) -> float:
        """SR 评分 (权重 25%)"""
        if sr > 2.0:
            return 15
        elif sr > 1.0:
            return 10
        elif sr > 0.5:
            return 5
        elif sr > 0:
            return 0
        else:
            return -10

    def _score_mdd(self, mdd: float) -> float:
        """MDD 评分 (权重 25%)"""
        if mdd < 5:
            return 10
        elif mdd < 10:
            return 5
        elif mdd < 20:
            return 0
        elif mdd < 30:
            return -5
        else:
            return -15

    def _score_win_rate(self, win_rate: float) -> float:
        """WinRate 评分 (权重 25%)"""
        if win_rate > 70:
            return 10
        elif win_rate > 60:
            return 5
        elif win_rate > 50:
            return 0
        elif win_rate > 40:
            return -5
        else:
            return -10

    def _calc_confidence(self, data: dict) -> float:
        """根据数据完整度计算置信度"""
        confidence = 0.5

        if data.get("portfolio_values") and len(data["portfolio_values"]) >= 2:
            confidence += 0.15

        if data.get("trades") and len(data["trades"]) >= 1:
            confidence += 0.15

        if data.get("initial_value") is not None and data.get("final_value") is not None:
            confidence += 0.1

        return min(1.0, confidence)
