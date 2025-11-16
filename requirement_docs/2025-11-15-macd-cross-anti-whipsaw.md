# MACD 交叉策略“贴线反复”交易问题与优化方案（2025-11-15）

## 背景
- 策略：MACD 金叉/死叉（参数来自 `config/macd_strategy_params.json` → fast=12, slow=26, signal=9）。
- 现象：2025-11-13 当天新建仓位后，2025-11-14 即出现卖出信号，原因是 MACD 与信号线非常接近，发生微弱死叉，导致“买入隔日即被小幅回撤洗出”的无效交易。
- 相关持仓（节选，`positions/etf_macd_cross_portfolio.json`）：
  ```json
  {
    "positions": [
      {
        "ts_code": "561160.SH",
        "shares": 4900,
        "entry_price": 0.914,
        "entry_date": "2025-11-13"
      },
      {
        "ts_code": "510210.SH",
        "shares": 4400,
        "entry_price": 1.005,
        "entry_date": "2025-11-13"
      }
    ]
  }
  ```
- 生成 2025-11-14 信号时，日志出现卖出建议，理由为“MACD 死叉卖出信号！MACD(12,26,9) 线下穿信号线”，与“贴线反复”吻合。

## 复核数据与结论
为避免错判，使用与策略一致的 MACD 实现做二次核对（脚本：`scripts/debug_macd_check.py`，数据源：`data/chinese_etf/daily`，复权价用于指标计算）。

运行命令：
```bash
python scripts/debug_macd_check.py \
  --tickers 561160.SH 510210.SH \
  --data-dir data/chinese_etf/daily \
  --end-date 2025-11-14 \
  --rows 8
```

结果（节选）：

- 561160.SH（锂电池ETF）
  ```
  Date            Close        MACD      Signal        Hist
  2025-11-07      0.800    0.054923    0.047957    0.006966
  2025-11-10      0.767    0.054160    0.049198    0.004962
  2025-11-11      0.762    0.052531    0.049864    0.002666
  2025-11-12      0.726    0.047794    0.049450   -0.001657
  2025-11-13      0.820    0.051037    0.049768    0.001269
  2025-11-14      0.776    0.049467    0.049708   -0.000240
  ```
  - 结论：2025-11-14 出现 SELL（MACD 轻微下穿 Signal）。
  - 统计：Hist 20 日标准差 ≈ 0.00914，最后一日 |Hist| ≈ 0.00024，仅为约 2.6% 的 std（极弱信号）。

- 510210.SH（上证指数ETF）
  ```
  Date            Close        MACD      Signal        Hist
  2025-11-10      1.402    0.025661    0.024236    0.001425
  2025-11-11      1.388    0.025106    0.024410    0.000696
  2025-11-12      1.385    0.024164    0.024361   -0.000197
  2025-11-13      1.407    0.024930    0.024475    0.000455
  2025-11-14      1.382    0.023245    0.024229   -0.000984
  ```
  - 结论：2025-11-14 出现 SELL（MACD 下穿 Signal）。
  - 统计：Hist 20 日标准差 ≈ 0.002932，最后一日 |Hist| ≈ 0.000984，为 std 的约 33.6%（仍属较弱）。

复核结论：两个标的在 2025-11-14 的确发生了“极弱/较弱”的死叉，属于“贴线反复”范畴，直接触发卖出较容易造成无效交易。

## 根因分析
- MACD 与信号线在最近两日非常接近，零轴附近的微小波动易造成“日内/隔日方向切换”。
- 目前运行时配置（`config/macd_strategy_params.json` → `runtime_config.filters`）默认关闭了斜率、ADX、成交量、确认过滤器，对贴线微交叉非常敏感。
- 现有的确认/斜率过滤器仅在买入路径上生效（卖出路径未对称应用），导致卖出对微弱死叉几乎“零门槛”。

## 优化方案（优先级由易到难）
本项目决定直接落地以下四项（不再尝试 ADX/斜率/成交量/买入确认等方案）：

1) 自适应滞回阈值（Hysteresis, 可开关）
   - 目标：避免 MACD 与 Signal 贴线附近的无效交叉（减少频繁反向）。
   - 规则：`|Hist| > k × rolling_std(Hist, W)` 才承认交叉（默认 k=0.5, W=20）。
   - 额外：保留“绝对阈值模式”作为后备（`|Hist| > abs_eps`）。
   - 开关与参数：
     - `enable_hysteresis` (bool)
     - `hysteresis_mode` = `std`/`abs`（默认 `std`）
     - `hysteresis_k` (float, 默认 0.5)
     - `hysteresis_window` (int, 默认 20)
     - `hysteresis_abs` (float, 默认 0.001，用于 `abs` 模式)

2) 卖出确认（Sell Confirmation）
   - 目标：对称于买入确认，在弱死叉出现时不立即卖出。
   - 规则：死叉触发后需连续 `confirm_bars_sell` 根满足 `MACD < Signal` 才执行卖出。
   - 参数：
     - `confirm_bars_sell` (int, 默认 2)

3) 最短持有期（Min Holding Period）
   - 目标：避免建仓隔日即被微小反向洗出。
   - 规则：入场后 `min_hold_bars` 根 K 线内忽略相反信号。
   - 参数：
     - `min_hold_bars` (int, 默认 3)

4) 零轴约束（Zero-Axis Constraint, 可开关）
   - 目标：降低零轴附近噪声（零轴附近最易贴线反复）。
   - 规则（对称版）：仅在两条线同处零轴上方时允许买入、同处零轴下方时允许卖出。
   - 开关与参数：
     - `enable_zero_axis` (bool)
     - `zero_axis_mode`（预留，默认 `symmetric` 表示买卖对称）

## 建议的起始参数
- 统一使用以下默认值（后续可在 config 中调整）：
  - `enable_hysteresis=true`, `hysteresis_mode=std`, `hysteresis_k=0.5`, `hysteresis_window=20`
  - `confirm_bars_sell=2`
  - `min_hold_bars=3`
  - `enable_zero_axis=true`, `zero_axis_mode=symmetric`

## 预期收益
- 显著降低“建仓隔日即卖出”的无效交易；减少频繁交易与摩擦成本。
- 在震荡阶段显著抑制来回穿越；趋势阶段仍可较及时响应。

## 实施与对齐（配置/CLI/回测与实盘一致性）
为保证回测与实盘一致，新增参数全部通过配置文件统一管理，并同时对回测与实盘 CLI 透出：

1) 配置文件（示例：`config/macd_strategy_params.json`）
```json
{
  "macd_cross": {
    "params": {
      "fast_period": 12,
      "slow_period": 26,
      "signal_period": 9
    },
    "runtime_config": {
      "anti_whipsaw": {
        "enable_hysteresis": true,
        "hysteresis_mode": "std",
        "hysteresis_k": 0.5,
        "hysteresis_window": 20,
        "hysteresis_abs": 0.001,
        "confirm_bars_sell": 2,
        "min_hold_bars": 3,
        "enable_zero_axis": true,
        "zero_axis_mode": "symmetric"
      }
    }
  }
}
```

4) 调试日志与可观测性
- 策略级（回测时可选开启）
  - `debug_signal_filter`（类属性，默认 false）：当原始金叉/死叉被 Anti‑Whipsaw 拦截时，在 `MacdCross.next()` 打印一条 `[过滤] ...` 日志（包含原因与 Bar 序号）。建议仅在问题定位时开启。
- 实盘信号生成
  - 若当日存在“原始交叉但被过滤”，在逐标的输出中追加一行原因说明（如 `触发死叉但被过滤：零轴约束(SELL), 滞回阈值(...)`）。
- 交易执行（持仓管理）
  - 当因为“最短持有期”忽略卖出时，输出 `[过滤] 最短持有期: <ts_code> 已持有X<Y 根，忽略本次卖出`。
```

2) 实盘信号生成（`generate_daily_signals.sh` → `generate_signals.py`）
   - generate_signals.py 读取上述 `runtime_config.anti_whipsaw` 并注入策略参数；
   - 新增 CLI 选项仅作为“覆盖配置”的手段（保持灵活性），默认从配置读取：
     - `--enable-hysteresis`, `--hysteresis-mode std|abs`, `--hysteresis-k`, `--hysteresis-window`, `--hysteresis-abs`
     - `--confirm-bars-sell`
     - `--min-hold-bars`
     - `--enable-zero-axis`, `--zero-axis-mode`

3) 回测流程（`run_backtest.sh` → `backtest_runner`）
   - backtest_runner 新增相同 CLI 参数并透传到策略；
   - 回测时默认也从配置读取（与实盘一致），CLI 仅用于覆盖；
   - `run_backtest.sh` 将这些参数加入帮助与命令构建逻辑，确保二者一致。

## 验证与验收标准
1) 数据集：`results/trend_etf_pool.csv` 对应标的池，回放近 12~24 个月。
2) 指标：
   - 一天内反向卖出比例较基线下降 ≥ 60%（优先）
   - 总交易次数下降（不牺牲过多收益）
   - 夏普下降 ≤ 5%，最大回撤上升 ≤ 10%，收益下降 ≤ 5%
3) 对比组：
   - 基线：当前策略（全部过滤器关闭）
   - 方案 A：仅启用“自适应滞回阈值”（k=0.5，W=20）
   - 方案 B：方案 A + “卖出确认”（2）
   - 方案 C：方案 B + “最短持有期”（3）+ “零轴约束”

## 复现实验步骤
1) 信号复核（已完成示例）：
   ```bash
   python scripts/debug_macd_check.py \
     --tickers 561160.SH 510210.SH \
     --data-dir data/chinese_etf/daily \
     --end-date 2025-11-14 \
     --rows 8
   ```
2) 日常信号生成（出现“卖出建议”的时间点）：
   ```bash
   ./generate_daily_signals.sh --analyze \
     --strategy macd_cross \
     --stock-list results/trend_etf_pool.csv \
     --portfolio-file positions/etf_macd_cross_portfolio.json \
     --load-params config/macd_strategy_params.json \
     --data-dir data/chinese_etf/daily \
     --end-date 20251114
   ```
3) 回测对比：按“验证与验收标准”的对比组设置参数（优先从配置读取，必要时用 CLI 覆盖），统计上述指标。

## 后续实施建议
- 开发顺序：
  1) 在策略中实现四项功能与参数（含默认值与开关）；
  2) generate_signals / backtest_runner 注入参数（优先从配置读取）；
  3) run_backtest.sh / generate_daily_signals.sh 扩展帮助与命令拼装，确保二者流程一致；
  4) 跑对比回测，按验收标准评估；
  5) 实盘灰度上线（先观察 1~2 周）。

--- 

附：本次复核采用 MACD(12,26,9)，与策略一致；数据源为复权价，确保与策略计算口径一致。***
