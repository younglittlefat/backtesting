# 趋势ETF筛选系统设计需求文档

**创建日期**: 2025-11-06
**项目**: Backtesting.py 趋势标的筛选系统
**版本**: v1.0

---

## 1. 项目概述

### 1.1 目标
从大量ETF标的（如1800只A股ETF）中，系统化筛选出最适合趋势跟踪策略（如MACD+止损）的标的池，以提高策略整体收益和稳定性。

### 1.2 核心原理
**三级漏斗筛选模型**：
```
[1800只ETF]
  → 初级筛选（流动性、上市时间）
    → 核心筛选（趋势性量化）
      → 组合优化（相关性分析）
        → [20-50只优质标的池]
```

**核心理念**: 不让策略测试所有标的，而是找到天生具有趋势性的标的，让策略在适合的"舞台"上发挥最大效能。

---

## 2. 筛选流程设计

### 2.1 第一级：初级筛选 - 排除"硬伤"

#### 2.1.1 流动性筛选
**目的**: 确保交易可执行性，降低滑点和冲击成本

**指标**: 日均成交额
- **计算**: `avg_turnover = data['成交额'].rolling(30).mean()`
- **阈值**: `avg_turnover > 1亿元` (可调至最低5000万)
- **预期结果**: 剔除60-70%标的

#### 2.1.2 上市时间筛选
**目的**: 确保数据充足且价格稳定

**指标**: 上市天数
- **计算**: `days_listed = (today - listing_date).days`
- **阈值**: `days_listed > 180` (6个月)

---

### 2.2 第二级：核心筛选 - 量化趋势性

#### 2.2.1 ADX趋势强度筛选

**原理**: ADX (Average Directional Index) 衡量趋势强度（非方向）

**计算步骤**:
```python
def calculate_adx(high, low, close, period=14):
    # 步骤1: 计算方向运动和真实波幅
    plus_dm = high.diff()  # +DM = 今日高 - 昨日高
    minus_dm = -low.diff()  # -DM = 昨日低 - 今日低

    # 应用规则
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[(plus_dm <= minus_dm)] = 0
    minus_dm[(minus_dm < plus_dm)] = 0

    # 真实波幅 TR
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 步骤2: 平滑移动平均 (Wilder's smoothing)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr

    # 步骤3: 计算DX和ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    return adx
```

**筛选标准**:
- 计算过去250个交易日（1年）的ADX均值
- 保留ADX均值排名前20%的ETF

#### 2.2.2 双均线回测筛选

**原理**: 用简单趋势策略检验标的对趋势交易的适应性

**计算逻辑**:
```python
def dual_ma_backtest(data, short=20, long=50):
    """
    双均线策略回测
    返回: 年化收益率, 最大回撤, 收益回撤比
    """
    # 计算均线
    ma_short = data['close'].rolling(short).mean()
    ma_long = data['close'].rolling(long).mean()

    # 生成信号: 1=持仓, 0=空仓
    signal = (ma_short > ma_long).astype(int).shift(1)

    # 计算收益率
    returns = data['close'].pct_change()
    strategy_returns = signal * returns

    # 计算净值曲线
    equity = (1 + strategy_returns).cumprod()

    # 年化收益率
    total_days = len(data)
    total_return = equity.iloc[-1] - 1
    annual_return = (1 + total_return) ** (252 / total_days) - 1

    # 最大回撤
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    max_dd = drawdown.min()

    # 收益回撤比
    return_dd_ratio = annual_return / abs(max_dd) if max_dd != 0 else 0

    return annual_return, max_dd, return_dd_ratio
```

**筛选标准**:
- 回测周期: 3-5年历史数据
- 主要指标: `收益回撤比 = 年化收益率 / 最大回撤`
- 保留收益回撤比排名前30%的ETF

#### 2.2.3 波动率筛选

**原理**: 趋势跟踪需要适度波动，过低无利可图，过高风险巨大

**计算方法**:
```python
def calculate_volatility(returns, window=252):
    """
    计算年化波动率
    """
    # 日收益率标准差
    daily_vol = returns.rolling(window).std()
    # 年化
    annual_vol = daily_vol * np.sqrt(252)
    return annual_vol.iloc[-1]
```

**筛选标准**:
- 波动率范围: 20% < 年化波动率 < 60%

#### 2.2.4 动量筛选

**原理**: 强者恒强，选择正在上涨的标的

**计算方法**:
```python
def calculate_momentum(close, periods=[63, 252]):
    """
    计算多期动量
    periods: [3个月, 12个月]
    """
    momentum = {}
    for p in periods:
        momentum[f'{p}d'] = (close.iloc[-1] / close.iloc[-p] - 1)
    return momentum
```

**筛选标准**:
- 计算3个月和12个月动量
- 保留动量值为正且排名前50%的ETF

---

### 2.3 第三级：组合优化 - 相关性分析

**原理**: 构建低相关性组合，平滑资金曲线，降低风险

**计算方法**:
```python
def build_diversified_portfolio(etf_list, returns_df, max_corr=0.7, target_size=20):
    """
    基于相关性构建分散化组合
    """
    # 计算相关系数矩阵
    corr_matrix = returns_df.corr()

    portfolio = []
    # 选择收益回撤比最高的作为起点
    portfolio.append(etf_list[0])

    for etf in etf_list[1:]:
        if len(portfolio) >= target_size:
            break

        # 计算与已选标的的平均相关性
        avg_corr = corr_matrix.loc[etf, portfolio].mean()

        # 如果相关性足够低，加入组合
        if avg_corr < max_corr:
            portfolio.append(etf)

    return portfolio
```

**筛选标准**:
- 相关系数阈值: < 0.7
- 目标组合数量: 20-30只ETF
- 确保行业/主题分散

---

## 3. 技术实现

### 3.1 数据结构

```python
# ETF数据结构
etf_data = {
    'code': str,           # ETF代码
    'name': str,           # ETF名称
    'listing_date': date,  # 上市日期
    'ohlcv': pd.DataFrame, # OHLCV数据
    'metrics': {
        'avg_turnover': float,      # 日均成交额
        'adx_mean': float,          # ADX均值
        'return_dd_ratio': float,   # 收益回撤比
        'volatility': float,        # 年化波动率
        'momentum_3m': float,       # 3个月动量
        'momentum_12m': float,      # 12个月动量
    }
}
```

### 3.2 主流程代码

```python
class TrendETFSelector:
    """
    趋势ETF筛选器
    """
    def __init__(self, etf_universe, start_date, end_date):
        self.etf_universe = etf_universe
        self.start_date = start_date
        self.end_date = end_date
        self.results = {}

    def run_pipeline(self):
        """执行完整筛选流程"""
        print(f"初始标的数: {len(self.etf_universe)}")

        # 第一级: 初级筛选
        stage1 = self.stage1_basic_filter()
        print(f"第一级筛选后: {len(stage1)}")

        # 第二级: 核心筛选
        stage2 = self.stage2_trend_filter(stage1)
        print(f"第二级筛选后: {len(stage2)}")

        # 第三级: 组合优化
        final = self.stage3_portfolio_optimization(stage2)
        print(f"最终标的池: {len(final)}")

        return final

    def stage1_basic_filter(self):
        """第一级: 流动性和上市时间筛选"""
        filtered = []
        for etf in self.etf_universe:
            # 流动性
            avg_turnover = etf.calc_avg_turnover(days=30)
            if avg_turnover < 100_000_000:  # 1亿
                continue

            # 上市时间
            if etf.days_since_listing() < 180:  # 6个月
                continue

            filtered.append(etf)
        return filtered

    def stage2_trend_filter(self, etf_list):
        """第二级: 趋势性量化筛选"""
        metrics = []

        for etf in etf_list:
            data = etf.get_ohlcv(self.start_date, self.end_date)

            # 计算各项指标
            adx = calculate_adx(data.high, data.low, data.close)
            adx_mean = adx.mean()

            ann_ret, max_dd, ret_dd_ratio = dual_ma_backtest(data)

            returns = data.close.pct_change()
            volatility = calculate_volatility(returns)

            momentum = calculate_momentum(data.close)

            # 应用筛选条件
            if adx_mean < np.percentile([m['adx'] for m in metrics], 80):
                continue

            if 0.2 <= volatility <= 0.6 and momentum['63d'] > 0:
                metrics.append({
                    'etf': etf,
                    'adx': adx_mean,
                    'ret_dd_ratio': ret_dd_ratio,
                    'volatility': volatility,
                    'momentum_3m': momentum['63d'],
                    'momentum_12m': momentum['252d']
                })

        # 按收益回撤比排序
        metrics.sort(key=lambda x: x['ret_dd_ratio'], reverse=True)
        return [m['etf'] for m in metrics[:100]]  # 保留前100

    def stage3_portfolio_optimization(self, etf_list, target_size=20):
        """第三级: 相关性优化"""
        # 计算收益率矩阵
        returns_df = pd.DataFrame({
            etf.code: etf.get_returns() for etf in etf_list
        })

        portfolio = build_diversified_portfolio(
            etf_list, returns_df,
            max_corr=0.7,
            target_size=target_size
        )

        return portfolio
```

### 3.3 使用示例

```python
# 初始化
selector = TrendETFSelector(
    etf_universe=load_all_etfs(),
    start_date='2020-01-01',
    end_date='2024-12-31'
)

# 执行筛选
selected_etfs = selector.run_pipeline()

# 导出结果
export_to_csv(selected_etfs, 'trend_etf_pool.csv')

# 定期更新 (每季度运行)
schedule.every().quarter.do(selector.run_pipeline)
```

---

## 4. 数据可用性评估

### 4.1 现有数据概况

**数据位置**: `data/csv/`
**评估日期**: 2025-11-06

#### 数据规模
- **ETF基本信息**: 1,803只 (`basic_info/etf_basic_info.csv`)
- **日线数据文件**: 1,893个 (`daily/etf/*.csv`)
- **平均历史数据**: 约500个交易日/标的 (约2年)
- **数据更新至**: 2025-11-03

#### 数据结构

**基本信息表字段**:
```csv
ts_code,symbol,name,fullname,market,tracking_index,management,
fund_type,list_date,found_date,status
```

**日线数据表字段**:
```csv
trade_date,instrument_name,open,high,low,close,pre_close,change,
pct_chg,volume,amount,adj_factor,adj_open,adj_high,adj_low,adj_close
```

#### ETF类型分布
```
股票型:    1,402只 (77.7%)  ← 主要筛选对象
混合型:      173只 (9.6%)
债券型:      105只 (5.8%)
REITs:        75只 (4.2%)
货币市场型:   27只 (1.5%)
商品型:       18只 (1.0%)
```

### 4.2 筛选需求对照检查

| 筛选需求 | 所需字段 | 数据可用性 | 备注 |
|---------|---------|-----------|------|
| **第一级：初级筛选** |
| 流动性筛选 | `amount` | ✅ 完全满足 | 成交额字段可直接使用 |
| 上市时间筛选 | `list_date` | ✅ 完全满足 | 格式: YYYYMMDD |
| **第二级：核心筛选** |
| ADX计算 | `high`, `low`, `close` | ✅ 完全满足 | OHLC数据完整 |
| 双均线回测 | `adj_open/high/low/close` | ✅ 完全满足 | 复权数据完整，与backtesting.py兼容 |
| 波动率计算 | `adj_close` 或 `pct_chg` | ✅ 完全满足 | 两种方式均可 |
| 动量计算 | `adj_close` | ✅ 完全满足 | 需注意数据长度 |
| **第三级：组合优化** |
| 相关性分析 | `adj_close` | ✅ 完全满足 | 复权价格可构建相关矩阵 |
| 行业分类 | `name` (名称) | ⚠️ 部分满足 | 需通过名称关键词匹配 |

### 4.3 数据质量说明

#### ✅ 优势
1. **数据完整性高**: 所有必需字段均完整，包括复权价格和成交额
2. **格式兼容性好**: 可直接用于backtesting.py框架，无需复杂转换
3. **规模充足**: 1,800+标的，足够筛选出优质标的池
4. **历史深度够**: 平均2年数据，满足趋势分析需求

#### ⚠️ 注意事项
1. **货币ETF需过滤**: 27只货币市场型ETF价格波动极小，不适合趋势跟踪
2. **新上市标的**: 约200+只ETF上市不足6个月，会被第一级筛选自动过滤
3. **行业分类缺失**: 无标准化行业字段，需通过名称关键词匹配

**解决方案 - 行业分类**:
```python
# 基于名称的行业关键词匹配
industry_keywords = {
    '科技': ['科技', '半导体', '芯片', '软件', '人工智能', 'AI', '5G'],
    '医药': ['医药', '医疗', '生物', '健康', '制药'],
    '金融': ['金融', '银行', '证券', '保险', '券商'],
    '消费': ['消费', '食品', '白酒', '零售', '商业'],
    '新能源': ['新能源', '光伏', '储能', '锂电', '电池'],
    '军工': ['军工', '国防', '航空', '航天'],
    '地产': ['地产', '房地产', '建筑', '基建'],
    '周期': ['煤炭', '有色', '钢铁', '化工', '石油'],
}

def classify_industry(etf_name):
    for industry, keywords in industry_keywords.items():
        if any(kw in etf_name for kw in keywords):
            return industry
    return '其他'
```

### 4.4 数据预处理要求

#### 优先级1: 必须实现
```python
# 1. 过滤非股票型ETF
etf_universe = etf_basic[etf_basic['fund_type'] == '股票型']

# 2. 日期格式转换
data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d')
data['list_date'] = pd.to_datetime(data['list_date'], format='%Y%m%d')

# 3. 设置索引和排序
data = data.sort_values('trade_date').set_index('trade_date')

# 4. 处理缺失值
data = data.dropna(subset=['adj_close', 'volume', 'amount'])

# 5. 过滤成交额为0的异常日
data = data[data['amount'] > 0]
```

#### 优先级2: 建议实现
```python
# 6. 行业分类
etf_basic['industry'] = etf_basic['name'].apply(classify_industry)

# 7. 数据验证
assert len(data) >= 180, "数据不足180天"
assert (data['adj_close'] > 0).all(), "存在非正价格"
```

### 4.5 评估结论

**综合评估**: ✅ **数据完全满足筛选系统开发需求，可立即开始实现**

**关键优势**:
- 所有核心筛选指标均可直接计算
- 数据质量和完整性良好
- 与backtesting.py框架无缝对接

**唯一缺陷及解决方案**:
- 行业分类缺失 → 通过名称关键词匹配解决（影响小）

**建议开发路径**:
1. **MVP阶段** (1-2周): 实现前两级筛选，暂不考虑行业分散
2. **完整版** (3-4周): 添加行业分类和第三级筛选
3. **优化版** (后续): 性能优化和自动化调度

---

## 5. TODO 列表

### 5.1 核心功能开发
- [ ] **数据层**
  - [ ] 实现ETF数据加载模块（支持Tushare/本地CSV）
  - [ ] 实现OHLCV数据验证和清洗
  - [ ] 实现缺失数据处理机制

- [ ] **计算模块**
  - [ ] 实现ADX指标计算函数（含单元测试）
  - [ ] 实现双均线回测引擎（复用backtesting.py框架）
  - [ ] 实现波动率计算函数
  - [ ] 实现动量计算函数
  - [ ] 实现相关系数矩阵计算

- [ ] **筛选引擎**
  - [ ] 实现TrendETFSelector主类
  - [ ] 实现三级筛选流程
  - [ ] 实现筛选参数配置系统（YAML/JSON）
  - [ ] 实现并行计算优化（multiprocessing）

- [ ] **组合构建**
  - [ ] 实现低相关性组合构建算法
  - [ ] 实现行业/主题分散验证
  - [ ] 实现组合回测和性能评估

### 5.2 工程化
- [ ] **性能优化**
  - [ ] 使用numba/cython加速指标计算
  - [ ] 实现增量计算（避免重复计算历史数据）
  - [ ] 实现结果缓存机制

- [ ] **输出与可视化**
  - [ ] 生成筛选报告（Markdown/HTML）
  - [ ] 绘制筛选漏斗图
  - [ ] 绘制最终组合的相关性热力图
  - [ ] 导出标的池到CSV/Excel

- [ ] **自动化与调度**
  - [ ] 实现定期自动筛选（每季度）
  - [ ] 实现筛选结果对比（新旧标的池）
  - [ ] 实现邮件/webhook通知

### 5.3 测试与验证
- [ ] **单元测试**
  - [ ] ADX计算准确性测试
  - [ ] 双均线回测逻辑测试
  - [ ] 边界条件测试（数据不足、异常值等）

- [ ] **集成测试**
  - [ ] 完整流程端到端测试
  - [ ] 不同市场环境下的鲁棒性测试

- [ ] **实证验证**
  - [ ] 在历史数据上验证筛选效果
  - [ ] 对比筛选前后策略收益差异
  - [ ] 标的池稳定性分析（换手率）

### 5.4 文档与部署
- [ ] 编写使用手册和API文档
- [ ] 创建配置文件模板和示例
- [ ] 编写部署脚本（conda环境）
- [ ] 添加到主项目CI/CD流程

---

## 6. 关键设计决策

### 6.1 参数推荐
| 参数 | 推荐值 | 说明 |
|------|--------|------|
| ADX周期 | 14 | 标准参数，平衡灵敏度和稳定性 |
| ADX均值窗口 | 250天 | 1年，捕捉完整牛熊周期 |
| 双均线参数 | MA(20,50) | 短期+中期，适合日线级别 |
| 流动性阈值 | 1亿元 | A股市场标准，可调至5000万 |
| 波动率范围 | 20%-60% | 适合大多数投资者风险承受能力 |
| 相关系数阈值 | < 0.7 | 保证一定分散度 |
| 最终组合数量 | 20-30只 | 平衡分散度和管理成本 |

### 6.2 更新频率
- **筛选周期**: 每季度重新运行（市场风格会变）
- **数据更新**: 每日更新OHLCV数据
- **参数优化**: 每年回顾并调整筛选参数

### 6.3 扩展性
- 支持多市场（A股、港股、美股）
- 支持多策略类型（趋势/均值回归）
- 支持自定义筛选指标

---

## 7. 预期成果

### 7.1 量化指标
- 标的池数量: 从1800只缩减到20-30只
- 筛选耗时: < 10分钟（单机并行计算）
- 标的池季度换手率: < 30%（稳定性）

### 7.2 策略改进
- 策略年化收益率提升: 预期 +20-50%
- 最大回撤降低: 预期 -10-20%
- 夏普比率提升: 预期 +0.3-0.8

### 7.3 风险控制
- 组合平均相关性: < 0.6
- 单一标的最大权重: < 10%（均衡配置）
- 行业分散度: 至少覆盖5个行业

---

## 8. 筛选系统与回测系统联动方案

### 8.1 问题背景

**Q: 筛选结果如何与回测脚本 `run_backtest.sh` 联动？它们之间的管道是怎样的？**

A: 筛选系统和回测系统通过**标准化的标的列表文件**作为接口，实现无缝对接。以下是完整的联动方案。

---

### 8.2 联动架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     趋势ETF筛选系统 (Selector)                    │
│                                                                 │
│  输入: data/csv/                                                │
│  处理: 三级筛选流程                                              │
│  输出: results/selector/trend_etf_pool_YYYYMMDD.csv             │
│         ├── ts_code (标的代码)                                  │
│         ├── name (标的名称)                                     │
│         ├── industry (行业分类)                                 │
│         ├── adx_mean (ADX均值)                                 │
│         ├── return_dd_ratio (收益回撤比)                        │
│         ├── volatility (波动率)                                │
│         ├── momentum_3m (3个月动量)                            │
│         └── rank (综合排名)                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    【标的列表文件】
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  回测系统 (run_backtest.sh)                      │
│                                                                 │
│  输入: results/selector/trend_etf_pool_YYYYMMDD.csv             │
│  处理: 批量回测 + 参数优化                                       │
│  输出: results/backtest/                                        │
│         ├── etf/stats/*.csv (详细统计)                          │
│         ├── etf/plots/*.html (可视化图表)                       │
│         └── summary/backtest_summary_YYYYMMDD.csv (汇总)        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    【回测结果分析】
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    结果验证与迭代优化                             │
│                                                                 │
│  - 对比筛选前后回测效果                                          │
│  - 分析标的池稳定性                                              │
│  - 调整筛选参数并重新运行                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

### 8.3 标的列表文件格式

#### 输出格式（筛选器 → 回测系统）

**文件路径**: `results/selector/trend_etf_pool_YYYYMMDD.csv`

**字段定义**:
```csv
ts_code,name,industry,adx_mean,return_dd_ratio,volatility,momentum_3m,momentum_12m,rank
159915.SZ,创业板ETF,科技,28.5,1.85,0.35,0.12,0.25,1
512690.SH,酒ETF,消费,32.1,1.72,0.42,0.08,0.18,2
515790.SH,光伏ETF,新能源,35.2,1.65,0.48,-0.05,0.32,3
...
```

**必需字段**（回测系统需要）:
- `ts_code`: 标的代码（格式: XXXXXX.SH / XXXXXX.SZ）
- `name`: 标的名称（用于显示）

**可选字段**（用于分析）:
- `industry`: 行业分类
- `adx_mean`: ADX均值（趋势强度）
- `return_dd_ratio`: 收益回撤比
- `volatility`: 年化波动率
- `momentum_3m/12m`: 动量指标
- `rank`: 综合排名

---

### 8.4 联动实现代码

#### 8.4.1 筛选器输出接口

```python
class TrendETFSelector:
    """趋势ETF筛选器"""

    def export_results(self, selected_etfs: List[ETF], output_path: str):
        """
        导出筛选结果为标准格式CSV

        Args:
            selected_etfs: 筛选后的ETF列表
            output_path: 输出文件路径
        """
        results = []
        for rank, etf in enumerate(selected_etfs, start=1):
            results.append({
                'ts_code': etf.code,
                'name': etf.name,
                'industry': etf.industry,
                'adx_mean': round(etf.metrics['adx_mean'], 2),
                'return_dd_ratio': round(etf.metrics['return_dd_ratio'], 2),
                'volatility': round(etf.metrics['volatility'], 4),
                'momentum_3m': round(etf.metrics['momentum_3m'], 4),
                'momentum_12m': round(etf.metrics['momentum_12m'], 4),
                'rank': rank
            })

        df = pd.DataFrame(results)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✓ 筛选结果已保存: {output_path}")
        print(f"  共 {len(results)} 只ETF")

        return output_path

    def run_and_export(self, output_dir='results/selector'):
        """执行筛选并导出结果"""
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 执行三级筛选
        selected_etfs = self.run_pipeline()

        # 生成文件名（带日期）
        today = datetime.now().strftime('%Y%m%d')
        output_file = f"{output_dir}/trend_etf_pool_{today}.csv"

        # 导出结果
        return self.export_results(selected_etfs, output_file)
```

#### 8.4.2 回测系统输入接口

**方式1: 通过标的列表文件批量回测**

```bash
# 读取筛选器输出的标的列表，批量回测
./run_backtest.sh \
  --stock-list results/selector/trend_etf_pool_20251106.csv \
  --strategy sma_cross \
  --optimize \
  --cost-model cn_etf \
  --aggregate-output results/backtest/summary_trend_pool.csv
```

**方式2: 直接指定代码列表**

```bash
# 从筛选结果中提取ts_code，作为参数传递
codes=$(tail -n +2 results/selector/trend_etf_pool_20251106.csv | cut -d',' -f1 | tr '\n' ',')

./run_backtest.sh \
  --stock "$codes" \
  --strategy sma_cross \
  --optimize
```

**方式3: 通过Python包装脚本**

```python
# scripts/run_selector_backtest.py
"""筛选+回测一体化脚本"""

import subprocess
from pathlib import Path
from datetime import datetime

def run_full_pipeline():
    """执行完整的筛选+回测流程"""

    # Step 1: 运行筛选器
    print("=" * 70)
    print("Step 1: 运行趋势ETF筛选器...")
    print("=" * 70)

    from etf_selector import TrendETFSelector

    selector = TrendETFSelector(
        data_dir='data/csv',
        start_date='2020-01-01',
        end_date='2024-12-31'
    )

    pool_file = selector.run_and_export()
    print(f"\n✓ 筛选完成: {pool_file}\n")

    # Step 2: 读取筛选结果
    df = pd.read_csv(pool_file)
    codes = df['ts_code'].tolist()

    print(f"筛选出 {len(codes)} 只ETF:")
    for idx, row in df.head(10).iterrows():
        print(f"  {row['rank']}. {row['ts_code']} - {row['name']} "
              f"(收益回撤比: {row['return_dd_ratio']})")
    if len(codes) > 10:
        print(f"  ... 以及其他 {len(codes)-10} 只")

    # Step 3: 运行回测
    print("\n" + "=" * 70)
    print("Step 2: 批量回测筛选标的...")
    print("=" * 70)

    today = datetime.now().strftime('%Y%m%d')
    summary_file = f"results/backtest/summary_trend_pool_{today}.csv"

    cmd = [
        './run_backtest.sh',
        '--stock', ','.join(codes),
        '--strategy', 'sma_cross',
        '--optimize',
        '--cost-model', 'cn_etf',
        '--aggregate-output', summary_file,
        '--start-date', '2023-01-01'
    ]

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)

    if result.returncode == 0:
        print(f"\n✓ 回测完成: {summary_file}")

        # Step 4: 分析结果
        print("\n" + "=" * 70)
        print("Step 3: 分析回测结果...")
        print("=" * 70)
        analyze_backtest_results(pool_file, summary_file)
    else:
        print(f"\n✗ 回测失败 (错误码: {result.returncode})")
        return 1

    return 0

def analyze_backtest_results(pool_file: str, backtest_file: str):
    """对比筛选指标和回测结果"""
    pool_df = pd.read_csv(pool_file)
    backtest_df = pd.read_csv(backtest_file)

    # 合并数据
    merged = pd.merge(
        pool_df[['ts_code', 'name', 'adx_mean', 'return_dd_ratio', 'rank']],
        backtest_df[['代码', '收益率(%)', '夏普比率', '最大回撤(%)']],
        left_on='ts_code',
        right_on='代码',
        how='inner'
    )

    # 按回测收益率排序
    merged = merged.sort_values('收益率(%)', ascending=False)

    print("\n📊 Top 10 回测表现:")
    print(merged[['rank', 'name', 'adx_mean', 'return_dd_ratio',
                   '收益率(%)', '夏普比率']].head(10).to_string(index=False))

    # 统计分析
    print(f"\n📈 统计摘要:")
    print(f"  平均收益率: {merged['收益率(%)'].mean():.2f}%")
    print(f"  平均夏普比率: {merged['夏普比率'].mean():.2f}")
    print(f"  正收益率标的: {(merged['收益率(%)'] > 0).sum()}/{len(merged)}")

    # 相关性分析
    corr = merged[['adx_mean', 'return_dd_ratio', '收益率(%)', '夏普比率']].corr()
    print(f"\n🔗 筛选指标与回测结果相关性:")
    print(f"  ADX均值 vs 回测收益率: {corr.loc['adx_mean', '收益率(%)']:.3f}")
    print(f"  收益回撤比 vs 回测收益率: {corr.loc['return_dd_ratio', '收益率(%)']:.3f}")

if __name__ == '__main__':
    exit(run_full_pipeline())
```

---

### 8.5 run_backtest.sh 需要的扩展

为了更好地支持筛选结果输入，需要为 `run_backtest.sh` 添加新参数：

```bash
# 在 run_backtest.sh 中添加
--stock-list <csv_file>      从CSV文件读取标的列表（第一列为ts_code）
```

**实现建议**:

```bash
# 在 run_backtest.sh 的参数解析部分添加
STOCK_LIST_VALUE=""
STOCK_LIST_ARGS=()

# 解析参数
--stock-list)
    STOCK_LIST_VALUE="$2"
    # 读取CSV第一列（跳过标题行），转为逗号分隔
    if [ -f "$STOCK_LIST_VALUE" ]; then
        STOCK=$(tail -n +2 "$STOCK_LIST_VALUE" | cut -d',' -f1 | tr '\n' ',' | sed 's/,$//')
        echo -e "${GREEN}从文件读取 ${STOCK_LIST_VALUE} 中的标的列表${NC}"
    else
        echo -e "${RED}错误: 标的列表文件不存在: $STOCK_LIST_VALUE${NC}"
        exit 1
    fi
    shift 2
    ;;
```

---

### 8.6 完整工作流示例

#### 场景1: 手动两步执行

```bash
# Step 1: 运行筛选器
conda activate backtesting
python -m etf_selector.main \
  --data-dir data/csv \
  --output-dir results/selector \
  --start-date 2020-01-01 \
  --end-date 2024-12-31

# 输出: results/selector/trend_etf_pool_20251106.csv (20只ETF)

# Step 2: 批量回测筛选结果
./run_backtest.sh \
  --stock-list results/selector/trend_etf_pool_20251106.csv \
  --strategy sma_cross \
  --optimize \
  --aggregate-output results/backtest/summary_trend_pool.csv

# 输出:
#   - results/etf/stats/*.csv (20个文件)
#   - results/summary/backtest_summary_20251106.csv
```

#### 场景2: 一体化脚本执行

```bash
# 使用包装脚本一键完成筛选+回测
python scripts/run_selector_backtest.py

# 自动完成:
#   1. 筛选 → results/selector/trend_etf_pool_20251106.csv
#   2. 回测 → results/backtest/summary_trend_pool_20251106.csv
#   3. 分析 → 打印相关性分析报告
```

#### 场景3: 定期自动化执行

```bash
# 添加到crontab，每周日凌晨执行
0 2 * * 0 /path/to/scripts/run_selector_backtest.py >> /var/log/etf_selector.log 2>&1
```

---

### 8.7 输出目录结构

```
results/
├── selector/                          # 筛选结果
│   ├── trend_etf_pool_20251106.csv   # 本次筛选标的池
│   ├── trend_etf_pool_20251001.csv   # 历史筛选记录
│   └── selection_report_20251106.html # 筛选报告（可选）
│
└── backtest/                          # 回测结果
    ├── etf/                           # 按类别分类
    │   ├── stats/
    │   │   ├── 159915.SZ_sma_cross.csv
    │   │   └── ...
    │   └── plots/
    │       ├── 159915.SZ_sma_cross.html
    │       └── ...
    │
    └── summary/
        ├── backtest_summary_20251106_221928.csv  # 普通回测汇总
        └── summary_trend_pool_20251106.csv       # 筛选标的池回测汇总
```

---

### 8.8 数据流追溯性

为了确保可追溯性，在回测汇总文件中添加元数据：

```csv
# results/backtest/summary_trend_pool_20251106.csv
# 元数据（注释行）:
# source: results/selector/trend_etf_pool_20251106.csv
# selection_date: 2025-11-06
# selection_criteria: ADX>25, volatility=[0.2,0.6], momentum_3m>0
# backtest_date: 2025-11-06
# strategy: sma_cross
# optimized: True

代码,标的名称,类型,策略,回测开始日期,回测结束日期,收益率(%),夏普比率,最大回撤(%)
159915.SZ,创业板ETF,etf,sma_cross,2023-01-03,2025-11-06,45.2,1.32,-18.5
...
```

---

### 8.9 核心联动优势

✅ **标准化接口**: CSV文件，易于人工查看和程序处理
✅ **模块解耦**: 筛选和回测独立，可分别优化
✅ **可追溯性**: 每次筛选和回测都有时间戳和元数据
✅ **灵活性**: 支持手动执行、自动化脚本、定期调度
✅ **可扩展性**: 可轻松添加新的筛选策略或回测策略

---

### 8.10 待实现功能清单

- [ ] 在 `run_backtest.sh` 中实现 `--stock-list` 参数
- [ ] 实现 `scripts/run_selector_backtest.py` 一体化脚本
- [ ] 在筛选器中实现 `export_results()` 方法
- [ ] 在回测汇总CSV中添加元数据注释
- [ ] 实现结果对比分析脚本 `analyze_backtest_results()`
- [ ] 添加定期执行的cron任务示例文档

---

## 9. 参考资料

- ADX指标: Wilder, J. W. (1978). New Concepts in Technical Trading Systems
- 动量策略: Jegadeesh and Titman (1993). Returns to Buying Winners and Selling Losers
- 相关性与分散: Markowitz, H. (1952). Portfolio Selection
- Python实现: pandas-ta, ta-lib库

---

**文档状态**: 初稿
**审核**: 待审核
**预计开发周期**: 2-3周
