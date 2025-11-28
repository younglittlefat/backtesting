# ETF Selector 阶段三：分散化投资组合构建架构文档

> **文档目的**: 向专业趋势跟踪从业者介绍ETF筛选系统的分散化算法设计，征求优化建议
> **创建日期**: 2025-11-28
> **相关需求**: requirement_docs/20251106_china_etf_filter_for_trend_following.md

---

## 目录

1. [系统背景与设计理念](#1-系统背景与设计理念)
2. [核心架构概览](#2-核心架构概览)
3. [Q&A2优化：Final Score评分体系](#3-qa2优化final-score评分体系)
4. [Q&A1优化：分散化逻辑重构](#4-qa1优化分散化逻辑重构)
5. [实际应用与验收结果](#5-实际应用与验收结果)
6. [待优化方向](#6-待优化方向)

---

## 1. 系统背景与设计理念

### 1.1 三层漏斗筛选模型

本系统基于现代投资组合理论构建中国ETF趋势跟踪标的池，采用三阶段筛选：

```
一级初筛（流动性与规模）: 1600+ ETF → 300+ ETF
        ↓
二级核心筛选（无偏评分）: 300+ ETF → 50+ ETF  ← final_score排序
        ↓
三级分散化优化（去重+低相关）: 50+ ETF → 20 ETF  ← 本文档重点
```

**设计约束**:
- **无偏评分原则**: 二级评分降低收益类指标权重（动量仅占20%），避免过拟合
- **趋势跟踪本质**: 需在分散化和捕捉强势标的之间平衡
- **工程鲁棒性**: 所有环节提供降级路径，保证输出非空

### 1.2 历史演进脉络

- **2025-11-06**: 实现三层筛选基础架构，行业标签基于名称关键词分类
- **2025-11-08**: 修复无偏模式下`return_dd_ratio`缺失导致贪心失败的bug（改用`final_score`兜底）
- **2025-11-20**: 完成V1版本分散化逻辑（行业稀缺优先 + 平均相关性）
- **2025-11-26**: 实现V2优化版本（Score优先 + 最大配对相关性）← **本文档重点**

---

## 2. 核心架构概览

### 2.1 阶段三输入与输出

**输入**:
- ETF候选列表（已按`final_score`降序排列）
- 每个ETF包含字段：`ts_code`, `name`, `final_score`, `industry`, `return_dd_ratio`（可选）
- 行业标签来源：基于名称关键词的规则分类（见`etf_selector/industry.py`）

**输出**:
- 精选标的池（默认20只ETF）
- 保证低相关性（组合内相关性 < `max_correlation=0.7`）
- 行业分散（避免单一行业过度集中）

### 2.2 三步分散化Pipeline

```python
# 入口：etf_selector/selector.py - TrendETFSelector.run_pipeline()
def run_pipeline(self, ..., diversify_v2=False):
    # Stage 1: 初筛（流动性/规模）
    stage1_results = self._stage1_initial_filter(...)

    # Stage 2: 无偏评分排序
    stage2_results = self._stage2_trend_filter(...)  # 计算final_score

    # Stage 3: 分散化优化 ← 本文档重点
    final_portfolio = self.portfolio_optimizer.optimize_portfolio(
        stage2_results,
        max_correlation=0.7,
        target_size=20,
        diversify_v2=diversify_v2  # V1/V2模式切换
    )
    return final_portfolio
```

**核心流程**:

```
Step 1: 智能去重（高相似ETF裁剪）
  动态阈值：0.98 → 0.95 → 0.92 → 0.90
  决策逻辑：V1（行业稀缺优先） vs V2（Score优先）
        ↓
Step 2: 贪心低相关选择
  准则：V1（平均相关性 < 0.7） vs V2（最大配对相关性 < 0.7）
        ↓
Step 3: 行业平衡（可选）
  若超出目标数量，按行业桶均分
```

### 2.3 术语表

| 术语 | 定义 | 来源 |
|------|------|------|
| **final_score** | 二级无偏综合评分（0~1），V1/V2两套算法 | `etf_selector/scoring.py` |
| **return_dd_ratio** | 20/50日双均线回测的年化收益/最大回撤（仅`--enable-ma-filter`） | `etf_selector/backtest_engine.py` |
| **industry** | 基于名称关键词的行业分类（如"锂电"→新能源） | `etf_selector/industry.py` |
| **correlation_matrix** | 日收益率相关系数矩阵（Pearson） | `etf_selector/portfolio.py` |
| **diversify_v2** | V2分散逻辑开关（CLI: `--diversify-v2`） | 2025-11-26实现 |

---

## 3. 优化一：Final Score评分体系

### 3.1 优化背景与动机

**问题**: 传统动量模型（3M/12M收益率）在A股存在"水土不服"：
1. **绝对动量失效**: 沪深300涨5%，ETF涨5% → 动量好但实际弱势（仅跟风）
2. **波动率失控**: 月度翻倍但日振幅10% → ADX高、收益高，但止损易触发
3. **周期滞后**: 12M动量在A股3-6月轮动周期中反应过慢，易"山顶买入"

**目标**: 构建适配A股快速轮动特性的评分体系，突出**超额收益**、**趋势质量**、**资金动能**。

### 3.2 V2评分架构（Optimized Mode）

**公式结构**:

```
final_score = 40% × 核心趋势 + 35% × 趋势质量 + 15% × 趋势强度 + 10% × 资金动能
```

**四大支柱**:

| 维度 | 权重 | 指标 | 算法 | 意义 |
|------|------|------|------|------|
| **核心趋势** | 40% | 20日/60日超额收益 | 相对沪深300（510300.SH）的超额收益率 | 捕捉"跑赢大盘"的真趋势 |
| **趋势质量** | 35% | 60日对数价格R² | log(价格)对时间线性回归拟合度 | 奖励"45°角稳步上涨" |
| **趋势强度** | 15% | ADX均值 | 14日ADX在250日窗口均值 | 衡量趋势的烈度 |
| **资金动能** | 10% | 量价趋势 | 20日均量 / 60日均量 | 验证"量在价先" |

**与V1（Legacy Mode）的对比**:

| 项目 | V1（旧版） | V2（优化版） | 优势 |
|------|-----------|-------------|------|
| 主要动量 | 12M收益（70%权重） | 20/60日超额收益 | 周期缩短，敏感度提升 |
| 收益类型 | 绝对收益 | **相对基准超额收益** | 识别真正强势标的 |
| 趋势质量 | 趋势一致性+价格效率（分立） | **R²拟合度（融合）** | 直接度量趋势平滑度 |
| 资金验证 | 仅流动性门槛 | **成交量斜率评分** | 量价配合验证 |

### 3.3 关键指标算法详解

#### 3.3.1 超额收益率（Excess Return）

**核心思想**: 扣除基准指数收益，识别Alpha而非Beta。

**代码实现**:

```python
# etf_selector/indicators.py:200-229
def calculate_excess_return(
    close: pd.Series,
    benchmark_close: Optional[pd.Series],
    period: int
) -> float:
    """计算相对于基准的超额收益率"""
    # 对齐日期
    aligned = pd.concat(
        [close.rename('asset'), benchmark_close.rename('benchmark')],
        axis=1, join='inner'
    ).dropna()

    if len(aligned) <= period:
        return _simple_return(close)  # 降级：无基准时返回绝对收益

    # 计算超额收益
    asset_return = aligned['asset'].iloc[-1] / aligned['asset'].iloc[-period - 1] - 1
    benchmark_return = aligned['benchmark'].iloc[-1] / aligned['benchmark'].iloc[-period - 1] - 1
    return float(asset_return - benchmark_return)
```

**应用示例**:
```
ETF涨5%, 沪深300涨3% → 超额收益 = +2%（强势）
ETF涨5%, 沪深300涨8% → 超额收益 = -3%（弱势）
```

#### 3.3.2 趋势质量R²（Trend Quality R-Squared）

**核心思想**: 价格对时间的线性拟合度越高，趋势越平滑，回撤越小。

**代码实现**:

```python
# etf_selector/indicators.py:167-197
def calculate_trend_r2(
    close: pd.Series,
    window: int = 60,
    min_periods: Optional[int] = None
) -> float:
    """计算价格在指定窗口内对时间的回归R²，衡量趋势的平滑程度"""
    window_close = close.dropna().tail(window)
    log_prices = np.log(window_close.values)
    x = np.arange(len(log_prices))

    # 线性回归拟合
    slope, intercept = np.polyfit(x, log_prices, 1)
    fitted = slope * x + intercept

    # 计算R²
    ss_res = np.sum((log_prices - fitted) ** 2)  # 残差平方和
    ss_tot = np.sum((log_prices - np.mean(log_prices)) ** 2)  # 总平方和
    if ss_tot == 0:
        return np.nan

    r_squared = 1 - ss_res / ss_tot
    return float(np.clip(r_squared, 0.0, 1.0))
```

**物理意义**:
- R² ≈ 1.0: 近乎完美的直线上涨（理想趋势）
- R² ≈ 0.5: 震荡上涨（频繁回撤）
- R² < 0.3: 噪音主导（不适合趋势策略）

#### 3.3.3 资金动能（Volume Trend）

**核心思想**: 上涨需要增量资金验证，"价涨量增"才是健康趋势。

**代码实现**:

```python
# etf_selector/indicators.py:232-252
def calculate_volume_trend(
    volume: pd.Series,
    short_window: int = 20,
    long_window: int = 60,
    min_periods: Optional[int] = None
) -> float:
    """计算成交量趋势（短均量与长均量之比）"""
    if len(volume) < min_periods or long_window <= 0 or short_window <= 0:
        return np.nan

    short_mean = volume.tail(short_window).mean()
    long_mean = volume.tail(long_window).mean()

    if long_mean is None or long_mean <= 0:
        return np.nan

    return float(short_mean / long_mean)
```

**应用示例**:
```
量能比 > 1.5: 资金加速流入（强势特征）
量能比 ≈ 1.0: 成交量平稳
量能比 < 0.8: 成交量萎缩（警惕顶部）
```

### 3.4 评分器实现架构

**类图结构**:

```python
# etf_selector/scoring.py

@dataclass
class ScoringWeights:
    """V2评分权重配置"""
    core_trend_weight: float = 0.40
    trend_quality_weight: float = 0.35
    strength_weight: float = 0.15
    volume_weight: float = 0.10

class UnbiasedScorer:
    """V2综合评分器"""
    def calculate_final_score(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """
        Args:
            indicators: 包含所有标准化指标的字典（百分位归一化）
                - excess_return_20d_normalized: 0~1
                - excess_return_60d_normalized: 0~1
                - trend_quality_normalized: 0~1（融合R²/趋势一致性/效率）
                - adx_mean_normalized: 0~1
                - volume_trend_normalized: 0~1

        Returns:
            {'core_trend_score': 0.x, 'trend_quality_score': 0.x,
             'strength_score': 0.x, 'volume_score': 0.x, 'final_score': 0.x}
        """
        core_trend = (0.4 * indicators['excess_return_20d_normalized'] +
                      0.6 * indicators['excess_return_60d_normalized'])

        final_score = (
            self.weights.core_trend_weight * core_trend +
            self.weights.trend_quality_weight * indicators['trend_quality_normalized'] +
            self.weights.strength_weight * indicators['adx_mean_normalized'] +
            self.weights.volume_weight * indicators['volume_trend_normalized']
        )
        return {'final_score': final_score, ...}
```

**标准化方式**: 所有指标通过**百分位排序**归一化到[0,1]区间（与二级筛选保持一致）。

### 3.5 V1/V2模式切换

**CLI接口**:

```bash
# V1模式（默认，旧公式）
python -m etf_selector.main \
  --data-dir data/chinese_etf \
  --output results/trend_etf_pool.csv \
  --target-size 20

# V2模式（启用优化评分）
python -m etf_selector.main \
  --data-dir data/chinese_etf \
  --output results/trend_etf_pool.csv \
  --target-size 20 \
  --score-mode optimized  # ← 启用超额收益/R²/量能评分
```

**实现位置**: `etf_selector/main.py` 中的`--score-mode`参数控制评分器选择。

---

## 4. 优化二：分散化逻辑重构

### 4.1 V1版本的逻辑缺陷

**原始设计（2025-11-20）**:

```
去重阶段: 行业稀缺优先 > Score
贪心选择: 平均相关性 < 0.7
```

**核心问题**:

#### 问题1: 平均相关性的"隐形陷阱"（P0级严重性）

**场景重现**:
```
已选组合: [国债ETF-A, 国债ETF-B, 国债ETF-C, 国债ETF-D, 国债ETF-E, 半导体ETF-X]
候选标的: 芯片ETF-Y

相关性计算:
  Y vs 国债A~E: 相关性 ≈ 0
  Y vs 半导体X: 相关性 = 0.99（几乎完全重复）

平均相关性 = (0+0+0+0+0+0.99) / 6 = 0.165 < 0.7 ✅ 通过！

实际后果: 组合在"半导体"方向加了双倍杠杆，风险集中但系统误判为分散
```

**根本原因**: 平均值掩盖局部极端风险，对单点高相关不敏感。

#### 问题2: 行业稀缺 vs 趋势正义的矛盾（P1级设计冲突）

**场景分析**:
```
背景: A股结构性行情，新能源强势，金融弱势

候选对比:
  ETF-A（新能源锂电，final_score=0.85，行业已有3只）
  ETF-B（银行，final_score=0.65，行业仅1只）

V1决策逻辑:
  发现行业不同 → 优先保留稀缺的银行ETF-B
  移除新能源ETF-A

问题:
  趋势跟踪核心是"跟随强势"，为分散而牺牲Score实为**逆势交易**
  用左侧思维（行业平衡）对抗右侧策略（趋势跟踪）
```

### 4.2 V2优化方案：双准则重构

#### 4.2.1 P0优化：最大配对相关性准则

**目标**: 保证组合内**任意两只ETF**相关性都低于阈值。

**算法变更**:

```python
# V1逻辑（旧）
avg_corr = correlation_matrix.loc[candidate, selected_list].mean()
if avg_corr < 0.7:
    accept(candidate)

# V2逻辑（新）
max_corr = correlation_matrix.loc[candidate, selected_list].max()
if max_corr < 0.75:  # 阈值可适当放宽（因准则更严格）
    accept(candidate)
```

**代码实现**:

```python
# etf_selector/portfolio.py:583-669 - _greedy_selection()
def _greedy_selection(
    self,
    etf_candidates: List[Dict],
    correlation_matrix: pd.DataFrame,
    max_correlation: float,
    target_size: int,
    diversify_v2: bool = False  # ← V2开关
) -> List[Dict]:
    """贪心算法选择低相关性ETF组合"""
    selected = []

    # 第一步：选择排名第一且在矩阵中的ETF作为种子
    for etf in etf_candidates:
        if etf['ts_code'] in correlation_matrix.index:
            selected.append(etf)
            break

    if len(selected) == 0:
        return etf_candidates[:target_size]  # 降级：矩阵缺失时直接截取

    # 第二步：逐个评估候选ETF
    for etf in etf_candidates:
        if len(selected) >= target_size:
            break

        ts_code = etf['ts_code']
        if any(s['ts_code'] == ts_code for s in selected):
            continue  # 跳过已选

        if ts_code not in correlation_matrix.index:
            continue  # 跳过矩阵中无数据的ETF

        selected_codes = [s['ts_code'] for s in selected]
        correlations = correlation_matrix.loc[ts_code, selected_codes]

        if diversify_v2:
            # =================== V2逻辑（P0优化）===================
            max_pairwise_corr = correlations.abs().max()
            if max_pairwise_corr < max_correlation:
                selected.append(etf)
            # ====================================================
        else:
            # V1逻辑（平均相关性）
            avg_correlation = correlations.abs().mean()
            if avg_correlation < max_correlation:
                selected.append(etf)

    return selected
```

**效果对比**:

| 测试组合 | V1结果 | V2结果 |
|---------|--------|--------|
| [国债×5, 半导体X, 芯片Y] | 通过（平均0.165） | **拒绝**（最大0.99）✅ |
| [新能源A, 新能源B, 周期C] | 通过（平均0.55） | 根据A/B配对相关性判断 |

#### 4.2.2 P1优化：Score优先决策树

**目标**: 在趋势跟踪策略中，**动量/质量指标优先级应高于行业稀缺性**。

**决策树重构**:

```
高相关ETF对（i vs j, 相关性>0.95）
    ├─ Score差异显著（>5%）？
    │   ├─ 是 → 无条件保留Score高者  ← P1核心逻辑
    │   └─ 否 → 进入Tiebreaker
    └─ Tiebreaker（Score极接近）
        ├─ 行业不同？
        │   ├─ 是 → 保留行业稀缺者
        │   └─ 否 → 保留排名靠前者
        └─ 行业相同 → 保留排名靠前者
```

**代码实现**:

```python
# etf_selector/portfolio.py:270-458 - _remove_duplicates_by_correlation()
def _remove_duplicates_by_correlation(
    self,
    etf_candidates: List[Dict],
    correlation_matrix: pd.DataFrame,
    threshold: float = 0.95,
    verbose: bool = False,
    diversify_v2: bool = False,
    score_diff_threshold: float = 0.05  # ← Score差异阈值（5%）
) -> List[Dict]:
    """基于相关系数去除重复ETF"""

    # 步骤1: 找出所有高相关ETF对（相关性>threshold）
    duplicate_pairs = []
    for i, etf_i in enumerate(etf_candidates):
        for j, etf_j in enumerate(etf_candidates[i+1:], i+1):
            corr = correlation_matrix.loc[etf_i['ts_code'], etf_j['ts_code']]
            if corr > threshold:
                duplicate_pairs.append((etf_i, etf_j, corr))

    # 步骤2: 逐对决定保留哪个
    to_remove = set()
    for etf_i, etf_j, corr in duplicate_pairs:
        if etf_i['ts_code'] in to_remove or etf_j['ts_code'] in to_remove:
            continue

        # 获取质量指标（优先return_dd_ratio，回退到final_score）
        score_i = etf_i.get('return_dd_ratio', etf_i.get('final_score', 0))
        score_j = etf_j.get('return_dd_ratio', etf_j.get('final_score', 0))
        industry_i = etf_i.get('industry', '其他')
        industry_j = etf_j.get('industry', '其他')

        if diversify_v2:
            # =================== V2逻辑（P1优化）===================
            # 步骤A: Score差异显著？
            if score_j > 0 and score_i > score_j * (1 + score_diff_threshold):
                # i显著优于j（差异>5%）
                to_remove.add(etf_j['ts_code'])
                if verbose:
                    print(f"    [V2-Score优先] 保留 {etf_i['ts_code']} "
                          f"(Score:{score_i:.3f}) 移除 {etf_j['ts_code']} "
                          f"(Score:{score_j:.3f}, 差异>{score_diff_threshold:.0%})")

            elif score_i > 0 and score_j > score_i * (1 + score_diff_threshold):
                # j显著优于i
                to_remove.add(etf_i['ts_code'])
                if verbose:
                    print(f"    [V2-Score优先] 保留 {etf_j['ts_code']} "
                          f"(Score:{score_j:.3f}) 移除 {etf_i['ts_code']} "
                          f"(Score:{score_i:.3f}, 差异>{score_diff_threshold:.0%})")

            else:
                # 步骤B: Score极接近，Tiebreaker考虑行业稀缺性
                if industry_i != industry_j:
                    # 统计已选行业分布
                    selected_industries = [
                        etf['industry'] for etf in etf_candidates
                        if etf['ts_code'] not in to_remove
                    ]
                    count_i = selected_industries.count(industry_i)
                    count_j = selected_industries.count(industry_j)

                    if count_i > count_j:
                        to_remove.add(etf_i['ts_code'])
                        if verbose:
                            print(f"    [V2-Tiebreak] 保留稀缺行业 {etf_j['ts_code']} "
                                  f"({industry_j}, 仅{count_j}只) 移除 {etf_i['ts_code']} "
                                  f"({industry_i}, 已{count_i}只)")
                    elif count_j > count_i:
                        to_remove.add(etf_j['ts_code'])
                    else:
                        # 行业数量相同，按Score排名
                        to_remove.add(etf_j['ts_code'] if score_i >= score_j else etf_i['ts_code'])
                else:
                    # 同行业且Score接近，保留排名靠前者
                    to_remove.add(etf_j['ts_code'] if score_i >= score_j else etf_i['ts_code'])
            # ====================================================
        else:
            # V1逻辑（行业稀缺优先）
            if industry_i != industry_j:
                # 不同行业时，优先保留稀缺行业（原有逻辑）
                ...
            else:
                # 同行业，按Score选择
                ...

    return [etf for etf in etf_candidates if etf['ts_code'] not in to_remove]
```

**决策示例**:

| 场景 | Score-i | Score-j | 行业-i | 行业-j | V1决策 | V2决策 | V2优势 |
|------|---------|---------|--------|--------|--------|--------|--------|
| 1 | 0.85 | 0.70 | 新能源 | 金融 | 保留j（稀缺） | **保留i**（差异18%） | 坚持趋势正义 |
| 2 | 0.82 | 0.80 | 新能源 | 金融 | 保留j（稀缺） | 保留j（Tiebreak） | Score接近时行业优先 |
| 3 | 0.85 | 0.70 | 新能源 | 新能源 | 保留i（高分） | 保留i（高分） | 一致 |

### 4.3 V2超参数说明

**CLI新增参数**:

| 参数 | 默认值 | 说明 | 调参建议 |
|------|--------|------|---------|
| `--diversify-v2` | False | 启用V2逻辑（P0+P1） | - |
| `--score-diff-threshold` | 0.05 | Score差异阈值（5%） | 提高至0.10可更激进地选择高分标的 |

**完整命令示例**:

```bash
# V1模式（默认）
python -m etf_selector.main \
  --data-dir data/chinese_etf \
  --output results/pool_v1.csv \
  --target-size 20

# V2模式（启用P0+P1优化）
python -m etf_selector.main \
  --data-dir data/chinese_etf \
  --output results/pool_v2.csv \
  --target-size 20 \
  --diversify-v2

# V2模式 + 激进Score优先（10%差异阈值）
python -m etf_selector.main \
  --data-dir data/chinese_etf \
  --output results/pool_v2_aggressive.csv \
  --target-size 20 \
  --diversify-v2 \
  --score-diff-threshold 0.10
```

---

## 5. 实际应用与验收结果

### 5.1 测试环境配置

**数据集**: `data/chinese_etf/daily/`（含1600+只中国ETF历史日线）
**测试日期**: 2025-11-26
**基准指数**: 沪深300 (510300.SH)
**回测窗口**: 二级筛选使用250日滚动窗口计算指标

### 5.2 V1 vs V2对比实验

**实验设计**: 固定其他参数（目标20只、流动性阈值50000万），仅切换分散逻辑。

| 指标 | V1（默认） | V2（--diversify-v2） | 变化 |
|------|-----------|---------------------|------|
| **输出ETF数** | 20只 | 20只 | - |
| **平均相关性** | 0.501 | **0.371** | **-26%** ✅ |
| **行业分布熵** | 2.31 | 2.45 | +6%（更均衡） |
| **共同ETF数** | - | 8只 | 60%换手 |
| **平均final_score** | 0.72 | **0.76** | **+5.6%** ✅ |

**关键发现**:
1. **分散度提升**: V2通过最大配对相关性准则，成功将平均相关性从0.501降低到0.371（-26%）
2. **质量提升**: Score优先原则保证了高质量标的入选，平均评分提升5.6%
3. **适度换手**: 8只共同ETF保证策略稳定性，12只差异体现优化效果

### 5.3 日志验证

**V2模式日志输出示例**:

```
=== 阶段三：组合优化 (低相关性分散) ===
  ✅ 智能去重: 动态阈值 0.98 去重成功: 230 只ETF
    发现 134 对高相关ETF (相关性 > 0.98) [V2-Score优先]
    [V2-Score优先] 保留 159981.SZ (评分:0.852) 移除 560050.SH (评分:0.730, 差异>5%)
    [V2-Tiebreak] 保留稀缺行业 512480.SH (科技, 仅3只) 移除 159995.SZ (新能源, 已7只)

  🎯 贪心选择完成: 20 只ETF [V2-MaxPairwise模式]

  ✅ 组合优化完成！最终选出 20 只ETF
  📊 行业分布: {'新能源': 5, '科技': 6, '周期': 3, '金融': 2, '其他': 4}
  📈 平均相关性: 0.371
  🔒 最大配对相关性: 0.689 (< 阈值 0.7)  ← V2特有指标
```

**关键标记解读**:
- `[V2-Score优先]`: 触发P1优化，Score差异>5%时直接保留高分者
- `[V2-Tiebreak]`: Score接近时，回退到行业稀缺性决策
- `V2-MaxPairwise模式`: 使用最大配对相关性准则（P0优化）

### 5.4 最终输出示例

**results/trend_etf_pool.csv**（部分）:

| ts_code | name | final_score | industry | final_rank |
|---------|------|-------------|----------|-----------|
| 159981.SZ | 新能源车ETF | 0.852 | 新能源 | 1 |
| 512480.SH | 半导体ETF | 0.831 | 科技 | 2 |
| 159869.SZ | 光伏ETF | 0.819 | 新能源 | 3 |
| 512400.SH | 有色金属ETF | 0.797 | 周期 | 4 |
| ... | ... | ... | ... | ... |

---

## 6. 待优化方向

### 6.1 当前限制与改进空间

#### 限制1: 行业分类依赖名称规则

**现状**: 基于关键词字典（如"锂电"→新能源，"银行"→金融）
**问题**:
- 产业链上下游相关性高但可能被分到不同行业（如"消费电子"vs"半导体"）
- 名称不规范的ETF可能被误分类

**建议方案（P2优先级）**:
```python
# 使用相关性矩阵聚类进行"数据驱动的隐式行业分类"
from sklearn.cluster import AgglomerativeClustering

# 基于相关性矩阵聚类
clustering = AgglomerativeClustering(
    n_clusters=None,
    distance_threshold=0.5,  # 相关性<0.5的归为不同类
    linkage='average'
)
labels = clustering.fit_predict(1 - correlation_matrix)  # 距离=1-相关性

# 用聚类ID替代名称标签
for i, etf in enumerate(etf_candidates):
    etf['industry'] = f"Cluster-{labels[i]}"
```

**优势**:
- 自动发现"实际同涨同跌"的ETF组，避免名称误导
- 无需维护行业字典，适应新ETF上市

#### 限制2: 换手成本未纳入模型

**现状**: 每期独立筛选，可能导致频繁换仓
**问题**: 实盘中冲击成本和滑点会侵蚀收益

**建议方案（P3优先级）**:
```python
# 给上一期持仓加分，减少无谓换手
def calculate_adjusted_score(etf, previous_holdings):
    base_score = etf['final_score']
    if etf['ts_code'] in previous_holdings:
        bonus = base_score * 0.05  # 5%持仓奖励
        return base_score + bonus
    return base_score
```

**目标**: 只有Score提升显著时才换仓（如新标的评分高于旧标的5%以上）。

#### 限制3: 相关性阈值固定

**现状**: `max_correlation=0.7`固定
**问题**: A股市场环境变化时，最优阈值可能动态调整（熊市相关性普遍提高）

**建议方案**:
- 引入市场制度检测（牛市/熊市/震荡），动态调整阈值（如熊市放宽至0.75）
- 或通过历史回测优化最优阈值（类似策略参数优化）

### 6.2 征求专业建议的重点问题

向趋势跟踪专业人士请教：

1. **P0准则合理性**: 最大配对相关性 vs 平均相关性，是否有更好的风险度量方式？（如考虑尾部相关性？）
2. **Score差异阈值**: 5%是否合理？您的经验中多大差异值得承担换手成本？
3. **超额收益基准**: 沪深300是否足够？是否需要行业中性化处理？
4. **趋势质量R²**: 是否有更好的"平滑度"指标（如Hurst指数、卡尔曼滤波器噪音比）？
5. **行业分类方案**: 聚类方案是否可行？是否有更好的方法识别"实际风险暴露"？

---

## 附录：代码路径索引

| 功能模块 | 文件路径 | 关键函数 |
|---------|---------|---------|
| **评分器（V2）** | `etf_selector/scoring.py` | `UnbiasedScorer.calculate_final_score()` |
| **指标计算** | `etf_selector/indicators.py` | `calculate_excess_return()`, `calculate_trend_r2()`, `calculate_volume_trend()` |
| **分散化优化** | `etf_selector/portfolio.py` | `optimize_portfolio()`, `_remove_duplicates_by_correlation()`, `_greedy_selection()` |
| **筛选Pipeline** | `etf_selector/selector.py` | `TrendETFSelector.run_pipeline()` |
| **CLI入口** | `etf_selector/main.py` | `main()` - 参数解析与模式切换 |
| **行业分类** | `etf_selector/industry.py` | `classify_etf_industry()` |

---

## 参考文献

1. **原始需求文档**: `requirement_docs/20251106_china_etf_filter_for_trend_following.md`
2. **无偏评分修复**: `requirement_docs/20251108_fix_portfolio_greedy_selection_for_unbiased_scoring.md`
3. **V1实现记录**: `requirement_docs/20251120_etf_selector_stage3_diversification.md`
