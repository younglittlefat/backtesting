# Chandelier Exit (吊灯止损) 实施需求

**文档日期**: 2025-11-18
**作者**: Claude Code
**状态**: 待实施（细化方案已冻结，等待开发排期）

---

## 1. 原理与价值

### 1.1 核心原理

Chandelier Exit 由 Charles Le Beau 提出，并在 Alexander Elder 的著作中广泛传播。其思想是使用最近 `period` 天的最高/最低价（HHV/LLV）加上 ATR 缓冲，生成更加贴近价格结构的止损位：

```
做多吊灯止损:
chandelier_long = HHV(high, period) - ATR(period) × multiplier

做空吊灯止损:
chandelier_short = LLV(low, period) + ATR(period) × multiplier
```

其中：
- `HHV(high, period)`: 指定周期内的最高价
- `LLV(low, period)`: 指定周期内的最低价
- `ATR(period)`: 周期内的平均真实波动幅度

### 1.2 关键优势

1. **结合价格结构与波动性**：ATR 止损基于入场价，容易在趋势初期被震荡打掉；Chandelier 基于近期最高价，允许健康回调并保护利润。
2. **更适合趋势跟踪**：趋势初期提供宽松空间，趋势后期则随着最高价上移收紧止损线。
3. **参数鲁棒性强**：`period=22, multiplier=3.0` 的默认组合已被业界验证 20+ 年，无需高频调参。

### 1.3 推荐参数

- **标准配置**：`chandelier_period = 22`（约一个交易月）、`chandelier_multiplier = 3.0`，兼顾保护与持仓。
- **激进配置**：`chandelier_period = 22`、`chandelier_multiplier = 2.5`，适合波动率>5%的题材 ETF，更早锁定利润。

### 1.4 与 ATR 止损的对比

- **趋势初期回调**：ATR 止损可能在 100→94 元的正常回撤中被触发；Chandelier 随最高价 105 元推移，只要未跌破 96 元就继续持有。
- **趋势后期回撤**：ATR 止损以入场价为锚（如 120→114 元，风险 5%）；Chandelier 以最高价为锚（120→111 元，风险 7.5%），更宽松，避免过早止盈。

### 1.5 适用场景

✅ 中长期趋势跟踪策略（持仓数周至数月）、波动适中的 ETF、追求“骑住大趋势”的组合。

⚠️ 不建议用于短线、高频或明显震荡的交易环境。

---

## 2. 实施计划

- **优先级**: P0，与 ATR 自适应止损并行推进，可在相同实验批次完成对比。
- **预期收益**: 夏普比 +10~20%，最大回撤 -5~10%。
- **实施工作量**: 1.5 周（含代码与 Phase 1 回测实验）。
- **技术风险**: 低，依赖 ATR 指标与最高价滚动窗口，无额外依赖。
- **推荐理由**: 与 ETF 趋势策略高度匹配，参数稳定，可与 Loss Protection 组合，补足 ATR 以入场价为锚的短板。

---

## 3. 策略实现示例

```python
class SmaCrossWithChandelierExit(Strategy):
    """SMA双均线策略 + Chandelier Exit止损"""

    # 基础参数
    n1 = 10
    n2 = 20

    # Chandelier参数
    chandelier_period = 22
    chandelier_multiplier = 3.0

    def init(self):
        # 双均线
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

        # ATR指标
        self.atr = self.I(
            ATR_manual,
            self.data.High,
            self.data.Low,
            self.data.Close,
            self.chandelier_period,
        )

        # 最高价指标 (用于Chandelier计算)
        self.hhv = self.I(
            lambda x: pd.Series(x).rolling(self.chandelier_period).max(),
            self.data.High,
        )

    def next(self):
        # 持仓中: 检查Chandelier Exit
        if self.position.is_long:
            chandelier_stop = self.hhv[-1] - self.atr[-1] * self.chandelier_multiplier
            if self.data.Close[-1] < chandelier_stop:
                self.position.close()
                return

        # 入场逻辑: 短期均线上穿长期均线 (金叉)
        if crossover(self.sma1, self.sma2):
            if self.position:
                self.position.close()
            self.buy(size=0.9)

        # 出场逻辑: 短期均线下穿长期均线 (死叉)
        elif crossover(self.sma2, self.sma1) and self.position:
            self.position.close()
```

---

## 4. 集成路线

1. **BaseEnhancedStrategyV2**: 在 `stop_loss_method` 中新增 `chandelier`，共用 ATR 指标，额外维护 HHV/LLV 滚动序列，并在 `_check_stop_loss()` 中按照 HHV − ATR × multiplier 触发退出。
2. **CLI & 配置**: 扩展 `--stop-loss-method chandelier`、`--chandelier-period`、`--chandelier-multiplier`，默认值 `22/3.0`；`run_backtest.sh` 中提供示例：

   ```bash
   ./run_backtest.sh \
     --stock-list results/trend_etf_pool.csv \
     --strategy sma_cross_enhanced \
     --stop-loss-method chandelier \
     --chandelier-period 22 \
     --chandelier-multiplier 3.0 \
     --data-dir data/chinese_etf/daily
   ```

3. **验收与文档**: Phase 1 实验比较 ATR vs Fixed vs Chandelier，更新 CLAUDE.md 与策略 README，收敛推荐参数与使用指令。

---

## 5. TODO 列表

1. 实现 HHV/LLV + ATR 组合止损逻辑并接入 `BaseEnhancedStrategyV2`。
2. 在 SMA/MACD 策略中增加 `stop_loss_method="chandelier"` 的运行路径与单元测试。
3. 为 `backtest_runner` CLI 加入 `--chandelier-period/--chandelier-multiplier` 参数，并在 `filter_builder` / `argparser` 中连通配置。
4. 设计 Phase 1 回测：固定 vs ATR vs Chandelier（20 只 ETF，2023-11~2025-11），输出指标表和曲线。
5. 将结果写入 `experiment/etf/...` 与 `CLAUDE.md`，同步内外部文档，落地调优建议。

---

**备注**: Chandelier Exit 细化内容已从 `20251118_advanced_stop_loss_strategies.md` 拆分至当前文档，便于独立排期与跟踪。
