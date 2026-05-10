"""
金融数据级对抗性测试

提供金融数据层面的对抗性测试能力，包括噪声注入、趋势反转、
技术指标攻击等，用于评估金融AI Agent在数据扰动下的鲁棒性。

四层测试框架：
- Level 1 (baseline): 原始数据
- Level 2 (noisy): 高斯噪声 + 成交量尖峰
- Level 3 (meta): 组合噪声 + 趋势反转 + 虚假突破
- Level 4 (adversarial): MA交叉 + RSI背离 + MACD注入
"""

import random
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FinancialAttackResult:
    """金融对抗攻击结果"""
    level: str
    attack_type: str
    original_prices: list[float]
    modified_prices: list[float]
    score_before: float
    score_after: float
    robustness_ratio: float
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class GaussianNoiseInjector:
    """高斯噪声注入器

    向价格/成交量数据添加高斯噪声，模拟市场微观结构噪声。
    """

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)

    def inject(self, prices: list[float], noise_level: float = 0.01) -> list[float]:
        """
        向价格序列注入高斯噪声。

        Args:
            prices: 原始价格序列
            noise_level: 噪声水平（标准差占价格的比率），默认 0.01 (1%)

        Returns:
            注入噪声后的价格序列
        """
        if not prices:
            return []

        noisy_prices = []
        for price in prices:
            noise = random.gauss(0, price * noise_level)
            noisy_prices.append(round(price + noise, 6))

        return noisy_prices

    def inject_volume(self, volumes: list[float], noise_level: float = 0.05,
                      spike_probability: float = 0.1) -> list[float]:
        """
        向成交量序列注入噪声和随机尖峰。

        Args:
            volumes: 原始成交量序列
            noise_level: 噪声水平
            spike_probability: 尖峰出现的概率

        Returns:
            修改后的成交量序列
        """
        if not volumes:
            return []

        modified_volumes = []
        for volume in volumes:
            noise = random.gauss(0, volume * noise_level)
            modified = volume + noise

            # 随机注入成交量尖峰
            if random.random() < spike_probability:
                spike_factor = random.uniform(3.0, 10.0)
                modified *= spike_factor

            modified_volumes.append(round(max(0, modified), 2))

        return modified_volumes


class TrendReversalGenerator:
    """趋势反转生成器

    反转市场价格趋势，用于测试Agent在趋势变化场景下的表现。
    """

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)

    def generate(self, prices: list[float], reversal_point: float = 0.5) -> list[float]:
        """
        在指定位置反转价格趋势。

        Args:
            prices: 原始价格序列
            reversal_point: 反转点位置（0~1），默认 0.5 表示在中间位置反转

        Returns:
            反转后的价格序列
        """
        if not prices:
            return []

        n = len(prices)
        rp = int(n * reversal_point)
        rp = max(1, min(rp, n - 1))

        # 计算反转点前的趋势
        if rp < 2:
            return list(prices)

        first_price = prices[0]
        reversal_price = prices[rp]

        # 前半段保持不变
        result = list(prices[:rp])

        # 后半段反转趋势：计算前半段的趋势方向并反转
        trend_slope = (reversal_price - first_price) / rp

        for i in range(rp, n):
            # 反转趋势：从反转点开始，按相反方向延伸
            reversed_step = -trend_slope * (1 + random.uniform(-0.1, 0.1))
            if i == rp:
                result.append(prices[rp])
            else:
                prev = result[-1]
                result.append(round(prev + reversed_step, 6))

        return result

    def generate_false_breakout(self, prices: list[float],
                                breakout_direction: str = "up") -> list[float]:
        """
        生成虚假突破信号。

        Args:
            prices: 原始价格序列
            breakout_direction: 突破方向 ("up" 或 "down")

        Returns:
            包含虚假突破的价格序列
        """
        if not prices:
            return []

        n = len(prices)
        result = list(prices)

        # 在序列末尾附近制造虚假突破
        breakout_start = max(0, n - int(n * 0.2))

        if breakout_direction == "up":
            # 制造向上突破：在近期高点之上再创新高
            recent_high = max(result[breakout_start:])
            for i in range(breakout_start, n):
                fake_boost = recent_high * random.uniform(0.02, 0.05) * ((i - breakout_start + 1) / (n - breakout_start))
                result[i] = round(result[i] + fake_boost, 6)
        else:
            # 制造向下突破：在近期低点之下再创新低
            recent_low = min(result[breakout_start:])
            for i in range(breakout_start, n):
                fake_drop = recent_low * random.uniform(0.02, 0.05) * ((i - breakout_start + 1) / (n - breakout_start))
                result[i] = round(result[i] - fake_drop, 6)

        return result


class TechnicalIndicatorAttacker:
    """技术指标攻击器

    注入虚假技术信号，包括MA交叉、RSI背离、MACD信号等。
    """

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)

    @staticmethod
    def _simple_ma(prices: list[float], window: int) -> list[float]:
        """计算简单移动平均线"""
        if len(prices) < window:
            return []
        mas = []
        for i in range(window - 1, len(prices)):
            ma = sum(prices[i - window + 1:i + 1]) / window
            mas.append(ma)
        return mas

    def inject_ma_crossover(self, prices: list[float],
                            window_short: int = 5,
                            window_long: int = 20) -> list[float]:
        """
        注入虚假MA交叉信号。

        修改价格数据使其在末端产生短期均线上穿/下穿长期均线的信号。

        Args:
            prices: 原始价格序列
            window_short: 短期均线窗口
            window_long: 长期均线窗口

        Returns:
            修改后的价格序列
        """
        if len(prices) < window_long + 5:
            return list(prices)

        result = list(prices)

        # 计算当前均线
        ma_short = self._simple_ma(result, window_short)
        ma_long = self._simple_ma(result, window_long)

        if not ma_short or not ma_long:
            return result

        # 对齐均线（长期均线从 window_long-1 开始）
        offset = window_long - window_short
        aligned_short = ma_short[offset:] if offset > 0 else ma_short[:len(ma_long)]

        if not aligned_short or len(aligned_short) < 2:
            return result

        # 判断当前是金叉还是死叉场景，制造相反信号
        current_diff = aligned_short[-1] - ma_long[-1]

        # 在末尾制造金叉（短期均线上穿长期均线）
        target_diff = abs(ma_long[-1]) * 0.01  # 目标差值

        # 修改最后几个数据点
        n_modify = min(5, len(result))
        for i in range(n_modify):
            idx = len(result) - n_modify + i
            if current_diff < 0:
                # 当前死叉，制造金叉：逐步提高价格
                boost = target_diff * (i + 1) / n_modify * 1.5
                result[idx] = round(result[idx] + boost, 6)
            else:
                # 当前金叉，制造死叉：逐步降低价格
                drop = target_diff * (i + 1) / n_modify * 1.5
                result[idx] = round(result[idx] - drop, 6)

        return result

    @staticmethod
    def _calculate_rsi(prices: list[float], period: int = 14) -> list[float]:
        """计算RSI指标"""
        if len(prices) < period + 1:
            return []

        rsi_values = []
        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        # 初始平均
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

        # 后续使用平滑平均
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))

        return rsi_values

    def inject_rsi_divergence(self, prices: list[float], period: int = 14) -> list[float]:
        """
        注入RSI背离信号。

        修改价格数据使其产生价格与RSI的顶背离或底背离。

        Args:
            prices: 原始价格序列
            period: RSI计算周期

        Returns:
            修改后的价格序列
        """
        if len(prices) < period * 3:
            return list(prices)

        result = list(prices)
        rsi = self._calculate_rsi(result, period)

        if not rsi:
            return result

        # 检查价格趋势和RSI趋势
        price_trend = result[-1] - result[-period]
        rsi_trend = rsi[-1] - rsi[-period] if len(rsi) >= period else 0

        # 制造顶背离：价格创新高但RSI不创新高
        if price_trend > 0 and rsi_trend > 0:
            # 价格继续涨，但让RSI下降
            n_modify = min(period, len(result) // 2)
            for i in range(n_modify):
                idx = len(result) - n_modify + i
                # 逐步减小涨幅，使RSI动能减弱
                dampening = 1.0 - (i + 1) / n_modify * 0.5
                result[idx] = round(result[idx] * dampening + result[idx] * (1 - dampening) * 0.998, 6)
        # 制造底背离：价格创新低但RSI不创新低
        elif price_trend < 0 and rsi_trend < 0:
            # 价格继续跌，但让RSI上升
            n_modify = min(period, len(result) // 2)
            for i in range(n_modify):
                idx = len(result) - n_modify + i
                # 逐步减小跌幅
                dampening = 1.0 - (i + 1) / n_modify * 0.5
                result[idx] = round(result[idx] * dampening + result[idx] * (1 - dampening) * 1.002, 6)

        return result

    @staticmethod
    def _calculate_ema(prices: list[float], period: int) -> list[float]:
        """计算指数移动平均线"""
        if not prices:
            return []

        multiplier = 2 / (period + 1)
        ema = [prices[0]]

        for i in range(1, len(prices)):
            ema.append(prices[i] * multiplier + ema[-1] * (1 - multiplier))

        return ema

    def inject_macd_injection(self, prices: list[float]) -> list[float]:
        """
        注入虚假MACD信号。

        修改价格数据使其产生虚假的MACD金叉或死叉信号。

        Args:
            prices: 原始价格序列

        Returns:
            修改后的价格序列
        """
        if len(prices) < 35:  # MACD需要足够的数据 (26+9)
            return list(prices)

        result = list(prices)

        # 计算MACD
        ema_12 = self._calculate_ema(result, 12)
        ema_26 = self._calculate_ema(result, 26)

        # MACD线 = EMA12 - EMA26
        macd_line = [e12 - e26 for e12, e26 in zip(ema_12, ema_26, strict=False)]

        # 信号线 = MACD的9日EMA
        signal_line = self._calculate_ema(macd_line, 9)

        if not signal_line or len(signal_line) < 2:
            return result

        # 判断当前MACD状态
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        macd_line[-2]
        signal_line[-2]

        # 在末尾制造虚假的MACD金叉或死叉
        n_modify = min(5, len(result))
        for i in range(n_modify):
            idx = len(result) - n_modify + i

            if current_macd > current_signal:
                # 当前为多头，制造死叉：降低价格
                drop_factor = 0.005 * (i + 1) / n_modify
                result[idx] = round(result[idx] * (1 - drop_factor), 6)
            else:
                # 当前为空头，制造金叉：提高价格
                boost_factor = 0.005 * (i + 1) / n_modify
                result[idx] = round(result[idx] * (1 + boost_factor), 6)

        return result


class FinancialAdversarialTester:
    """金融对抗性测试器

    编排四层金融数据对抗性测试：
    - Level 1 (baseline): 原始数据，无修改
    - Level 2 (noisy): 高斯噪声 + 成交量尖峰
    - Level 3 (meta): 组合噪声 + 趋势反转 + 虚假突破
    - Level 4 (adversarial): MA交叉 + RSI背离 + MACD注入
    """

    # 各层级在加权评分中的权重
    LEVEL_WEIGHTS = {
        "baseline": 0.40,
        "noisy": 0.30,
        "meta": 0.20,
        "adversarial": 0.10,
    }

    def __init__(self, seed: int | None = None):
        self.seed = seed
        if seed is not None:
            random.seed(seed)

        self.noise_injector = GaussianNoiseInjector(seed=seed)
        self.trend_reversal = TrendReversalGenerator(seed=seed)
        self.indicator_attacker = TechnicalIndicatorAttacker(seed=seed)

    def test_level_1_baseline(self, prices: list[float]) -> list[float]:
        """Level 1: 基线测试，返回原始数据"""
        return list(prices)

    def test_level_2_noisy(self, prices: list[float],
                           noise_level: float = 0.01) -> list[float]:
        """Level 2: 噪声注入测试"""
        return self.noise_injector.inject(prices, noise_level=noise_level)

    def test_level_3_meta(self, prices: list[float],
                          noise_level: float = 0.01,
                          reversal_point: float = 0.5) -> list[float]:
        """Level 3: 元认知攻击 - 组合噪声 + 趋势反转 + 虚假突破"""
        # Step 1: 注入噪声
        result = self.noise_injector.inject(prices, noise_level=noise_level)

        # Step 2: 趋势反转
        result = self.trend_reversal.generate(result, reversal_point=reversal_point)

        # Step 3: 虚假突破
        direction = "up" if random.random() > 0.5 else "down"
        result = self.trend_reversal.generate_false_breakout(result, breakout_direction=direction)

        return result

    def test_level_4_adversarial(self, prices: list[float],
                                 window_short: int = 5,
                                 window_long: int = 20,
                                 rsi_period: int = 14) -> list[float]:
        """Level 4: 对抗攻击 - MA交叉 + RSI背离 + MACD注入"""
        result = list(prices)

        # Step 1: 注入MA交叉信号
        result = self.indicator_attacker.inject_ma_crossover(
            result, window_short=window_short, window_long=window_long
        )

        # Step 2: 注入RSI背离
        result = self.indicator_attacker.inject_rsi_divergence(result, period=rsi_period)

        # Step 3: 注入MACD信号
        result = self.indicator_attacker.inject_macd_injection(result)

        return result

    def run_all_levels(self, prices: list[float],
                       score_fn=None) -> dict[str, dict]:
        """
        运行所有层级的对抗性测试。

        Args:
            prices: 原始价格序列
            score_fn: 可选的评分函数，接受价格列表返回分数 (0-100)

        Returns:
            各层级的测试结果
        """
        results = {}

        # Level 1: Baseline
        baseline_prices = self.test_level_1_baseline(prices)
        baseline_score = score_fn(baseline_prices) if score_fn else None
        results["baseline"] = {
            "level": "baseline",
            "prices": baseline_prices,
            "score": baseline_score,
        }

        # Level 2: Noisy
        noisy_prices = self.test_level_2_noisy(prices)
        noisy_score = score_fn(noisy_prices) if score_fn else None
        results["noisy"] = {
            "level": "noisy",
            "prices": noisy_prices,
            "score": noisy_score,
        }

        # Level 3: Meta
        meta_prices = self.test_level_3_meta(prices)
        meta_score = score_fn(meta_prices) if score_fn else None
        results["meta"] = {
            "level": "meta",
            "prices": meta_prices,
            "score": meta_score,
        }

        # Level 4: Adversarial
        adversarial_prices = self.test_level_4_adversarial(prices)
        adversarial_score = score_fn(adversarial_prices) if score_fn else None
        results["adversarial"] = {
            "level": "adversarial",
            "prices": adversarial_prices,
            "score": adversarial_score,
        }

        return results

    @staticmethod
    def calculate_robustness_ratio(baseline_score: float,
                                   adversarial_score: float) -> float:
        """
        计算鲁棒性比率。

        鲁棒性比率 = 对抗分数 / 基线分数，表示在对抗条件下的性能保持程度。

        Args:
            baseline_score: 基线分数
            adversarial_score: 对抗条件下的分数

        Returns:
            鲁棒性比率 (0~1+，1.0 表示完全鲁棒)
        """
        if baseline_score == 0:
            return 0.0

        ratio = adversarial_score / baseline_score
        return round(ratio, 4)

    def calculate_weighted_score(self, scores: dict[str, float]) -> float:
        """
        计算加权综合分数。

        权重分配：
        - baseline: 40%
        - noisy: 30%
        - meta: 20%
        - adversarial: 10%

        Args:
            scores: 各层级的分数字典，如 {"baseline": 85.0, "noisy": 80.0, ...}

        Returns:
            加权综合分数
        """
        weighted_sum = 0.0
        total_weight = 0.0

        for level, weight in self.LEVEL_WEIGHTS.items():
            if level in scores:
                weighted_sum += scores[level] * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return round(weighted_sum / total_weight, 2)
