# ETF Selector 阶段三：行业与标的分散实现说明

## 背景
- 目标：在无偏评分完成的二级排序后，通过低相关与行业均衡构建可交易标的池
  （见 requirement_docs/20251106_china_etf_filter_for_trend_following.md）。
- 历史问题：无偏模式缺少收益回撤比导致贪心阶段空集，已在
  requirement_docs/20251108_fix_portfolio_greedy_selection_for_unbiased_scoring.md
  修复并统一使用 `final_score` 兜底。
- 入口：`TrendETFSelector.run_pipeline()` 将二级结果交给
  `PortfolioOptimizer.optimize_portfolio()`，默认阈值 `max_correlation=0.7`，目标规模由
  CLI `--target-size` 传入。

## 阶段三逻辑（可直接讲给策略人听）
- 输入是什么：已经按“无偏评分”排好序的一串 ETF，同时附带行业标签。行业是基于名称的
  关键词分类（如“锂电”→新能源，“银行”→金融），便于做稀缺行业优先。
- 目标是什么：在保证组合够“散”的前提下，挑出 `target_size`（示例 20）只 ETF。
  “散”体现在两层：先踢掉高度相似的（>0.98 相关），再控制入选标的与已有组合的相关性
  低于 `max_correlation=0.7`。
- 三步拆解：
  1) 智能去重（高相似先踢掉）
     - 计算全体候选的日收益率相关矩阵。
     - 阈值从 0.98 → 0.95 → 0.92 → 0.90 逐级放松，只要还能保留至少目标数的 80% 就停。
     - 对每一对高相关 ETF：
       * 若行业不同，优先留下行业数量更少的那一只（行业稀缺优先）。
       * 若行业相同，按质量指标比大小。优先使用回测产生的 `return_dd_ratio`；若是无偏模
         式且该值缺失，则用二级的 `final_score`。这样保证即便不跑回测也有决策依据。
     - 举例：锂电 ETF A 与锂电 ETF B 相关性 0.99，且两只都在新能源行业。若 A 的
       `final_score` 更高，则保留 A、踢掉 B；若 A 是新能源、B 是金融，并且金融在当前组合
       更稀缺，则即便 B 评分稍低也保留 B 以拉开行业差异。
  2) 低相关挑选（保证与已选均值相关性 <0.7）
     - 从排序靠前且能在矩阵中找到数据的 ETF 开始做种子。
     - 依次向下看列表，计算该候选与已选组合的平均相关性，低于 0.7 就加入。
     - 如果极端情况矩阵缺列或为空，就直接取前 N 名，保证永远有结果输出。
  3) 行业均衡（可选兜底）
     - 若超出了目标数量，可按行业桶均分（向下取整，多余按排序顺延），再按原排序回排，
       避免均衡动作打乱质量顺序。

### 为什么这样设计
- 高度相似的 ETF 先踢掉，避免组合内部“反复买同一件事”。
- 行业稀缺优先保证多行业暴露；在同一行业内用质量指标裁剪，减少“挑哪只”带来的随意性。
- 贪心用平均相关性（而非最大相关性或单对相关性）作为准则，避免偶发高相关单点阻塞组合。
- 所有步骤都有降级路径：指标缺失用评分兜底，矩阵缺失用截取前 N，确保命令始终有产出。

### 术语补充（关键指标怎么来的）
- `return_dd_ratio`：二级可选的双均线回测指标，定义为年化收益 / 最大回撤。
  只有在开启 `--enable-ma-filter` 时才计算，来自 `calculate_backtest_metrics()` 的
  20/50 日双均线回测（etf_selector/backtest_engine.py）。
- `final_score`：默认使用的“无偏综合评分”，替代收益相关指标，构成：
  - 主要项 80%：ADX 强度、趋势一致性、价格效率、流动性评分（在二级按百分位归一）。
  - 次要项 20%：动量 3M/12M（权重 30% / 70%，降低收益选择性偏差）。
  - 计算管线：二级在 `_stage2_trend_filter()` 调用 `UnbiasedScorer` 和
    `calculate_etf_scores()` 产生（etf_selector/scoring.py）。

## 关键代码片段
```python
# 动态阈值去重与质量指标兜底
thresholds = [0.98, 0.95, 0.92, 0.90]
ret_dd_i = etf_i.get('return_dd_ratio', np.nan)
if pd.isna(ret_dd_i) and pd.isna(ret_dd_j):
    ret_dd_i = etf_i.get('final_score', 0)
    metric_name = "评分"
elif pd.isna(ret_dd_i):
    ret_dd_i = -999  # 无效值排后
```
来源：etf_selector/portfolio.py:235-347。

```python
# 贪心起点与降级策略
for etf in etf_candidates:
    if etf['ts_code'] in correlation_matrix.index:
        selected.append(etf)
        break
if len(selected) == 0:
    return etf_candidates[:target_size]
```
来源：etf_selector/portfolio.py:535-544。

## 实际执行结果（2025-11-20）
命令：
```bash
python -m etf_selector.main \
  --data-dir data/chinese_etf \
  --output results/trend_etf_pool.csv \
  --target-size 20 \
  --min-turnover 50000 \
  --momentum-min-positive
```
- 阶段统计：一级 364 → 二级 364 → 三级结果 20。
- 去重/分散：动态阈值 0.98 一次成功，候选 364 → 230；贪心在 `max_correlation=0.7`
  下选出 20。
- 行业分布：新能源 7、科技 6、周期 2、金融 1、其他 4；平均相关性 0.595。
- 输出：`results/trend_etf_pool.csv`（20 只ETF）。


=====================

以下是我询问其他专业agent得到的优化建议，以Q & A的形式呈现。

Q1：（提出了前文总结的内容）

A1:
这是一个非常扎实且具有实战意义的筛选框架，看得出你已经在工程实现（兜底机制、动态阈值）和策略逻辑（去重、分散）之间做了很深入的平衡。

作为一个量化趋势交易员，我将从\*\*“风险暴露纯度”、“A股市场特性”以及“策略鲁棒性”\*\*三个维度，对你的方案进行客观辩证的分析，并提供优化建议。

-----

### 一、 深度辩证：当前方案的潜在风险

虽然目前的逻辑在工程上闭环了，但在交易逻辑上存在几个需要警惕的“隐形陷阱”：

#### 1\. “平均相关性”的陷阱（最严重的逻辑隐患）

**现状**：你使用了“与已选组合的**平均**相关性 \< 0.7”作为入选标准。
**风险**：平均值会掩盖局部的极端风险。

> **举例**：假设你已选了 5 只国债 ETF（彼此低相关）和 1 只半导体 ETF。
> 现在进来一只新的芯片 ETF，它与国债相关性为 0，与半导体相关性为 0.99。
> **计算结果**：平均相关性可能只有 0.16（远小于 0.7），于是系统将其纳入。
> **后果**：你的组合在“半导体”这个方向上**加了双倍杠杆**，而你以为自己很分散。
> **结论**：对于风险控制，**最大配对相关性（Max Pairwise Correlation）** 远比平均相关性重要。

#### 2\. “行业稀缺” vs “趋势正义”的矛盾

**现状**：在去重阶段，若两标的相关性高，优先保留“行业稀缺”的标的，而非分数高的。
**风险**：趋势跟踪的核心信仰是“跟随强势”。A股经常出现极致的结构性行情（如某年的白酒、某年的新能源）。

> **场景**：新能源（强趋势，拥挤）vs 银行（弱趋势，稀缺）。
> 如果为了“稀缺性”强行保留了一个弱势行业的标的，踢掉了一个强势行业的第二梯队标的，这实际上是在**逆势交易**（人为做左侧平衡）。
> **结论**：在趋势策略中，**Score（动量/强度）的优先级应高于 Scarcity（稀缺性）**。稀缺性应仅用于 Score 相近时的 Tie-breaker（打破平局）。

#### 3\. 标签分类的脆弱性

**现状**：基于名称关键词（如“锂电”-\>新能源）。
**风险**：A股 ETF 名称存在误导性，且产业链上下游相关性差异巨大。例如“消费电子”和“半导体”往往同涨同跌，但在你的字典里可能是两个行业，导致去重失败。

-----

### 二、 优化方案与优先级

建议按以下顺序进行优化，优先级由高到低：

#### 优先级 P0：修正贪心算法的“相关性准则”

**目标**：防止局部风险堆积。
**修改逻辑**：
将 `Avg(Correlation) < 0.7` 改为 **`Max(Pairwise Correlation) < Threshold`**。
即：新候选标的与**已选池中任意一只**标的的相关性，都不能超过阈值（例如 0.75 或 0.8）。

  * **为什么？** 这样能保证组合内任意两只 ETF 都是“不一样”的。
  * **代码思路调整**：
    ```python
    # 原逻辑
    # if current_avg_corr < 0.7: accept()

    # 优化逻辑
    # 计算 candidate 与 selected_list 中每一只的相关性
    max_corr = correlation_matrix.loc[candidate, selected_list].max()
    if max_corr < 0.75: # 阈值可以比平均值稍微放宽一点
        accept()
    ```

#### 优先级 P1：重构“去重阶段”的决策树

**目标**：坚持趋势跟踪的本质，不为了分散而牺牲强度。
**修改逻辑**：
在 `Step 1 智能去重` 中，当两只 ETF 高度相关（\>0.95）时：

1.  **比较 Score**：如果 Score 差异显著（例如差值 \> 10% 或 排名差 \> 5），直接保留 Score 高的。**不要管行业稀缺性**。这是为了保证我们永远持有最强的标的。
2.  **比较行业**：只有在 Score 极其接近时，才优先保留“行业稀缺”的那一只。

<!-- end list -->

  * **辩证思考**：如果是做资产配置（Asset Allocation），你的原方案是对的（追求贝塔多样性）。但你是做**趋势跟踪（Trend Following）**，必须向动量低头。

#### 优先级 P2：引入基于数据的“隐式行业分类” (Cluster-based)

**目标**：解决名字分类不准的问题。
**修改逻辑**：
不依赖名称标签，而是利用相关性矩阵本身进行**聚类（Clustering）**。

1.  在全量候选池上跑一个简单的聚类算法（如 Hierarchical Clustering 或 Affinity Propagation）。
2.  将聚类 ID 作为“行业标签”。
3.  这样，“消费电子”和“半导体”会被自动归为一类，无论它们名字叫什么。

#### 优先级 P3：增加“换手缓冲” (Turnover Buffer)

**目标**：解决实盘中的“无谓震荡换仓”。
**修改逻辑**：
在每一期的选择中，给予**上一期持仓的标的**一个加分项（Bonus Score），或者在贪心选择时优先遍历上一期持仓。

  * 例如：`Adjusted_Score = Final_Score * 1.05` (如果它是上期持仓)。
  * 这能避免因为 Score 微小的波动（第 20 名变第 21 名）导致频繁买卖，降低冲击成本。

-----

### 三、 优化后的 Pipeline 伪代码建议

这是结合了上述 P0 和 P1 的优化流程：

```python
def optimized_selection(candidates, target_size, max_pairwise_corr=0.8):
    """
    candidates: list of dict, 已按 Final Score 降序排列
    """
    
    # --- 阶段 1: 强相关去重 (Hard Filter) ---
    # 逻辑：高相关(>0.95)的一对中，强者生存。
    # 只有在强者极其接近时，才考虑行业。
    clean_candidates = []
    skip_indices = set()
    
    for i in range(len(candidates)):
        if i in skip_indices: continue
        
        keep_i = True
        for j in range(i + 1, len(candidates)):
            if j in skip_indices: continue
            
            # 计算两两相关性
            corr = get_correlation(candidates[i], candidates[j])
            
            if corr > 0.95:
                # 发现高度重叠，进入PK环节
                score_i = candidates[i]['final_score']
                score_j = candidates[j]['final_score']
                
                # 1. 动量优先原则：如果分差大于阈值，分数高的留下
                if score_i > score_j * 1.05: 
                    skip_indices.add(j) # 踢掉 j
                elif score_j > score_i * 1.05:
                    keep_i = False      # 踢掉 i
                    break               # i 已经被淘汰，不用比了
                else:
                    # 2. 只有分差极小时，才看行业稀缺性/费率/流动性
                    if is_scarce_industry(candidates[i]) and not is_scarce_industry(candidates[j]):
                        skip_indices.add(j)
                    else:
                        skip_indices.add(j) # 默认保留排名靠前的 i
        
        if keep_i:
            clean_candidates.append(candidates[i])

    # --- 阶段 2: 贪心选择 (Greedy Selection) ---
    # 逻辑：使用最大配对相关性控制风险
    final_portfolio = []
    
    for etf in clean_candidates:
        if len(final_portfolio) >= target_size:
            break
            
        # 检查与当前组合中 *任意一只* 的相关性
        is_correlated = False
        for selected in final_portfolio:
            pair_corr = get_correlation(etf, selected)
            if pair_corr > max_pairwise_corr:
                is_correlated = True
                break # 只要和一个冲突，就不要
        
        if not is_correlated:
            final_portfolio.append(etf)
            
    # --- 阶段 3: 兜底 (Fallback) ---
    # 如果选不满，说明阈值太紧，此时可以 relax 阈值或者直接补齐 top N
    if len(final_portfolio) < target_size:
        remaining_needed = target_size - len(final_portfolio)
        # 逻辑：从落选者中选分最高的补齐，不管相关性了（保证仓位）
        # ...补齐逻辑...
        
    return final_portfolio
```

### 四、 总结

你现在的方案**下限很高**（不会选出太烂的东西，也不会过度集中在同一只票上），但**上限受限**（可能因为过度追求形式上的分散而错失最强主线的爆发力，且存在平均相关性的逻辑漏洞）。

**下一步行动建议**：

1.  **必须做**：将 `Step 2` 中的“平均相关性判断”改为“与现有持仓的最大相关性判断”。这是风控底线。
2.  **强烈建议**：在 `Step 1` 去重时，移除“行业稀缺优先”，改为“坚决的动量优先（分数优先）”。让市场告诉你哪个板块值得配，而不是人为觉得它稀缺。

如果需要，我可以帮你写一段关于 **Hierarchical Risk Parity (HRP)** 的逻辑，那是一种更数学化的替代贪心算法的选股/权重分配方式，但在目前阶段，修正上述两点性价比最高。


-------

Q2：你的优化P1的基础还是final_score，那么它的计算就很重要。你看看现在的计算方式有哪些可以优化的地方？也列出优先级

A2：
既然你的筛选框架是针对**中国A股**的，那么现有的 `final_score` 计算逻辑（基于传统的 ADX 和 3M/12M 动量）存在一个显著的**水土不服**问题：**它忽略了 A 股高 Beta 和板块轮动的特性。**

传统的动量模型（如 Jegadeesh & Titman）在美股这种长牛慢牛市场很有效，但在 A 股，**“涨得好”不等于“涨得稳”，更不等于“跑赢了指数”**。

以下是针对 A 股趋势跟踪特性的 `final_score` 优化方案及优先级：

-----

### 优先级 P0：引入“相对强弱” (Relative Strength / Alpha)

**现状问题**：目前的动量是“绝对动量”（Absolute Momentum）。
**痛点**：A 股齐涨齐跌特性极强。如果沪深 300 涨了 5%，你的 ETF 涨了 5%，它的绝对动量看起来不错，但在趋势交易员眼中，这是**弱势**的（因为它只是跟风）。你需要找到那些**大盘跌它微跌、大盘涨它暴涨**的“异类”。

**优化方案**：
计算动量时，**扣除基准指数（如沪深300）的收益**，或者计算**RSRS（相对强弱指标）**。

**计算公式建议**：
$$\text{Score}_{\text{RS}} = \text{Return}_{\text{ETF}}(N) - \text{Return}_{\text{Benchmark}}(N)$$
或者使用更平滑的相对净值斜率。

**代码实现思路**：

```python
# 需要引入沪深300 (000300.SH) 的数据作为 benchmark
# 计算 N 日超额收益
excess_return_20d = etf_pct_change_20d - benchmark_pct_change_20d
# 将 excess_return 代替原本的 raw_return 进入评分系统
```

-----

### 优先级 P1：动量的“波动率标准化” (Volatility-Adjusted Momentum)

**现状问题**：直接使用 3M/12M 收益率。
**痛点**：A 股妖股多。某 ETF 一个月翻倍，但每天振幅 10%，ADX 很高，收益很高。这种标的对于趋势跟踪策略是**剧毒**，因为你的止损线会被轻易击穿，且很难上仓位。你需要的是**45度角稳步攀升**的标的。

**优化方案**：
用**夏普比率（Sharpe-like）或K-Ratio**的逻辑替代纯收益率。即：**收益率 / 波动率**。

**计算公式建议**：
使用 **IDR (Information Discreteness Ratio)** 或 **R-Squared (判定系数)**：
$$\text{Score}_{\text{Quality}} = \text{Slope}(\text{LogPrice}) \times R^2$$
或者简单点：
$$\text{AdjMomentum} = \frac{\text{Return}(N)}{\text{StdDev}(N)}$$

  * **解释**：$R^2$（价格与时间回归的拟合度）越高，说明上涨越接近直线，回撤越小。在 A 股，选 $R^2$ 高的票比选涨幅高的票，生存率高一倍。

-----

### 优先级 P2：调整时间窗口，适应 A 股“快轮动”

**现状问题**：使用 12M（年线）作为主要动量（权重 70%）。
**痛点**：A 股的单一行业趋势很少能持续 12 个月（除了 19-20 年的茅台/新能源）。大部分是 **3-6 个月** 的中级波段。12M 动量因子在 A 股会有严重的**滞后性**（你在山顶买入，因为 12 个月前它涨得好）。

**优化方案**：
缩短考核周期，增加近期权重的敏感度。

  * **建议权重**：
      * **20日 (1M)**：探测启动（20% 权重）
      * **60日 (3M)**：确认趋势（50% 权重，核心）
      * **120日 (6M)**：长期保护（30% 权重）
  * **移除**：12M 动量（或降级为仅仅是“过滤条件”而非“打分项”）。

-----

### 优先级 P3：成交量/资金流因子的提权

**现状问题**：Liquidity Score 仅作为流动性门槛。
**痛点**：A 股是资金市。**量在价先**。单纯看价格不够，要看**量价配合**。

**优化方案**：
引入 **OBV（能量潮）斜率** 或 **量价相关性**。

  * 如果价格创新高，但 OBV 没创新高（背离），要在分数上打折。
  * 或者简单计算：**上涨日的平均成交量 / 下跌日的平均成交量**。这个比值越大，说明主力资金在买入。

-----

### 综上：优化后的 `final_score` 计算公式（建议版）

建议重构 `calculate_etf_scores()`，采用以下加权逻辑：

**1. 核心趋势项 (Core Trend) - 权重 40%**

  * **指标**：**20日与60日超额收益率（Excess Return）的加权**。
  * *逻辑*：跑赢沪深300才是真趋势。

**2. 趋势质量项 (Trend Quality) - 权重 35%**

  * **指标**：**60日价格回归的 $R^2$ (R-Squared) 或 K-Ratio**。
  * *逻辑*：奖励“稳步上涨”，惩罚“大起大落”。这是最重要的防守型进攻指标。
  * *注*：原来的“Trend Consistency”和“Price Efficiency”可以归并到这里。

**3. 强度项 (Strength) - 权重 15%**

  * **指标**：**ADX (14)**。
  * *逻辑*：保留你原有的逻辑，ADX 确实能衡量趋势的“烈度”。

**4. 资金项 (Volume) - 权重 10%**

  * **指标**：**成交量趋势评分**（如 20日均量 / 60日均量）。
  * *逻辑*：必须有增量资金支持。

#### 代码实现的伪代码参考

```python
import numpy as np
from scipy.stats import linregress

def calculate_optimized_score(df, benchmark_df):
    """
    df: 单个ETF的日线数据
    benchmark_df: 沪深300日线数据
    """
    # 1. 相对强弱 (P0)
    # 对齐日期，计算累计收益
    etf_ret_60 = df['close'].pct_change(60).iloc[-1]
    bm_ret_60 = benchmark_df['close'].pct_change(60).iloc[-1]
    excess_ret = etf_ret_60 - bm_ret_60 # 超额收益
    
    # 2. 趋势质量 R-Squared (P1)
    # 取最近60天收盘价做线性回归
    y = np.log(df['close'].tail(60).values)
    x = np.arange(len(y))
    slope, intercept, r_value, p_value, std_err = linregress(x, y)
    # r_value**2 就是 R平方，越接近1越平滑
    trend_quality = r_value ** 2 
    
    # 3. 修正后的时间窗口 (P2)
    # 结合 20日动量和 60日动量
    momentum_score = (0.4 * df['close'].pct_change(20).iloc[-1]) + \
                     (0.6 * df['close'].pct_change(60).iloc[-1])
                     
    # 4. 综合打分 (归一化需要在全体计算后进行)
    # 这里仅展示原始逻辑合成
    # 注意：excess_ret 和 momentum_score 需要在全市场进行 Rank 或 Z-Score 标准化后再加权
    
    raw_score = (0.4 * normalize(excess_ret)) + \
                (0.35 * normalize(trend_quality)) + \
                (0.15 * normalize(adx_value)) + \
                (0.10 * normalize(volume_ratio))
                
    return raw_score
```

### 总结

1.  **立刻做 (P0 & P2)**：把动量计算从“绝对”改为“**相对沪深300的超额**”，并把时间重心从 12M 移到 **2M-3M**。这能让你避开大盘下跌时的“假抗跌”，并抓住 A 股的轮动节奏。
2.  **接着做 (P1)**：用 **$R^2$** 替代纯动量来衡量质量。这能大幅提高你持仓的夏普比率，让你拿得住单子。