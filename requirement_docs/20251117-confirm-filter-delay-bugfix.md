# 2025-11-17 确认过滤延迟入场修复说明

## 背景
- 用户反馈：执行 `kama_cross` 策略并开启 `--enable-confirm-filter --confirm-bars 2` 时，所有标的收益均为 0。
- 发现在策略层面与信号生成层面，`confirm_bars>1` 时的持续确认逻辑只在金叉当根检查，使得确认永远无法满足；另外信号生成器仍按金叉当根给出信号，回测与实盘不一致。

## 症状
- `run_backtest.sh --strategy kama_cross --enable-confirm-filter --confirm-bars 2` → 无交易、收益 0。
- `generate_signals.py` 在开启确认时继续输出 BUY/HOLD，即使回测没有成交。

## 修复概述
1. 将 `ConfirmationFilter` 升级为“延迟入场器”，当 `confirm_bars>1` 时仅在“连续 n 根保持在上方且窗口内至少有一次上穿”的当根放行。
2. `kama_cross` 与 `sma_cross_enhanced` 使用新的延迟入场逻辑：金叉后等待确认完成再入场，并在入场当根重新检查 Phase 1/Phase 2 过滤器；同时避免同向抖动（SMA 反手时先平旧仓）。
3. 信号生成器（单/双价格模式）对接相同语义，新增对 `kama_cross` 的双价格支持，确保 BUY/SELL/HOLD 判定与回测一致。

## 关键改动
| 文件 | 行号 | 说明 |
| --- | --- | --- |
| `strategies/filters/confirmation_filters.py:12-99` | 新增延迟入场判定逻辑，仅处理买入侧；`confirm_bars<=1` 视为即时确认。 |
| `strategies/kama_cross.py:372-465` | 引入 `entry_signal`，按“最近 n 根全部在 KAMA 上方 + 窗口内出现金叉”决定入场；入场当根复检效率/斜率过滤器。 |
| `strategies/sma_cross_enhanced.py:198-257` | 与 KAMA 同步的延迟入场逻辑，并在反手时先平旧仓，避免多次重复执行。 |
| `generate_signals.py:387-481` | 单价格模式下，SMA/KAMA 均依据新的确认逻辑生成 BUY/SELL/HOLD。 |
| `generate_signals.py:712-804` | 双价格模式下复用同样的延迟逻辑，并修复误用 `df` 导致的 `NameError`。 |
| `generate_signals.py:1351,1601` | CLI/执行路径支持 `kama_cross` 策略，与回测入口一致。 |

## 行为对比
| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| KAMA + `confirm_bars=2` | 金叉当根即调用 `ConfirmationFilter`，因上一根必定在 KAMA 下方，确认永远失败 → 无交易/收益 0。 | 金叉后等待 2 根确认，通过 `entry_signal` 触发入场；实际收益恢复正常。 |
| SMA 增强 + `confirm_bars=2` | 同样永不满足确认；信号生成器却仍打印 BUY，引发“回测 0、信号有”矛盾。 | 策略与信号生成器都在第 2 根才入场，行为一致；无冗余平仓/开仓抖动。 |
| 信号生成（双价格） | `NameError: df 未定义`（KAMA 分支误用变量）导致全量 ERROR。 | 使用 `adj_df` 计算、`real_price` 输出；BUY/SELL/HOLD 正常生成。 |

## 验证
1. **回测**
   ```bash
   ./run_backtest.sh \
     --stock-list results/trend_etf_pool.csv \
     --strategy kama_cross --optimize \
     --data-dir data/chinese_etf/daily \
     --output-dir results/exp_kama_confirm_upgraded \
     --enable-confirm-filter --confirm-bars 2 \
     --instrument-limit 5 --verbose
   ```
   - 5/5 标的产出正常收益（如 515880.SH 收益 398.33%）。

2. **信号生成（双价格）**
   ```bash
   python generate_signals.py \
     --stock-list results/trend_etf_pool.csv \
     --strategy kama_cross \
     --data-dir data/chinese_etf/daily \
     --load-params config/test/kama_base_strategy_params.json \
     --lookback-days 250 \
     --csv results/exp_signal_kama_dual.csv
   ```
   - 输出 HOLD/SELL 与回测结果一致，无 ERROR。

3. **信号生成（单价格冒烟）**
   ```bash
   python generate_signals.py \
     --stock-list results/trend_etf_pool.csv \
     --strategy kama_cross \
     --data-dir data/chinese_etf/daily \
     --load-params config/test/kama_base_strategy_params.json \
     --disable-dual-price --lookback-days 250
   ```
   - 结果与双价格模式一致，仅用于验证向后兼容。

## 后续建议
- 若需要在 SMA/KAMA 中引入 `confirm_bars_sell` 延迟卖出，请同步修改策略与信号生成器，确保回测与实盘一致。
- 信号生成默认采用双价格模式；仅在调试或特定场景下使用 `--disable-dual-price`。
