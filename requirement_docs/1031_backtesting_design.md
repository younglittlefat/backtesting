# 中国市场回测系统设计文档

## 1. 项目概述

### 1.1 目标
构建一个针对中国场内 ETF 与公募基金（无A股个股数据）的自动化回测体系，使用 `backtesting.py` 框架评估多策略表现，并通过 `run_backtest.sh` 脚本批量运行策略与生成结果。目标是在保持既有框架的同时，切换到 `data/chinese_stocks/` 下的完整日线 OHLCV 数据集。

### 1.2 数据源
- 数据根目录：`data/chinese_stocks/`
- 子目录结构：`daily/etf/*.csv`、`daily/fund/*.csv`
- 数据文件示例：
  - ETF：`data/chinese_stocks/daily/etf/159001.SZ.csv`
  - 基金：`data/chinese_stocks/daily/fund/000001.OF.csv`
- 数据覆盖范围：2016-01-04 起至最新交易日（不同标的存在差异）
- 原始来源：国内行情平台（字段已包含完整 OHLCV 信息）

### 1.3 数据格式
文件为 UTF-8 编码的标准 CSV，列结构如下：

```
trade_date,open,high,low,close,pre_close,change,pct_chg,volume,amount
20160104,99.9990,100.0000,99.9880,99.9920,100.0100,-0.0180,-0.0180,6135,61351.48
```

- `trade_date`: 交易日期，格式 `YYYYMMDD`
- `open/high/low/close`: 日内价格（含小数）
- `volume`: 成交量（股/份额）
- `amount`: 成交额（单位与来源保持一致）
- 额外字段 `pre_close/change/pct_chg` 用于校验涨跌幅，可在回测中忽略或作为指标使用

### 1.4 标的分类与命名

| 分类 | 目录 | 证券代码样式 | 说明 |
|------|------|--------------|------|
| ETF  | `daily/etf`  | `159001.SZ` | 以场内 ETF 为主，交易单位为份额 |
| 基金 | `daily/fund` | `000001.OF` | 场外基金净值，部分存在同日多次估值 |

命令行层面使用不含扩展名的代码（如 `159001.SZ`）作为标识，脚本负责编码与文件名映射。

### 1.5 MySQL 数据库洞察

- `instrument_basic` 表保存统一基础信息，含 `ts_code`、`name`、`market` 等字段，指数类默认以上交所/深交所记录为主，可直接补充中文简称。
- `instrument_daily` 按 `data_type` 保存行情数据：ETF/指数提供价格与涨跌幅列，基金额外包含 `unit_nav`、`adj_nav` 等净值字段，便于生成复权指标。
- `fund_dividend` 与 `fund_share` 记录基金分红与份额规模，目前 ETF 未见分红记录，如需前后复权需结合这两个表核对关键日期。
- 实测 `adj_nav` 仅在基金标的中非空（约 300 万条），ETF/指数则需基于 `pct_change` 加 `close` 自行累计复权因子。
- 数据库已初始化 `market_data`、`stock_info` 等扩展表，虽未参与本次导出，但可在后续用于补充股票类标的或市场统计。

## 2. 策略选择

### 2.1 推荐策略
三种策略仍基于 backtesting.py 的经典示例，但需验证在 ETF/基金上的适用性。

1. **双均线交叉 (SmaCross)**  
   - 适合趋势型 ETF（如宽基指数、行业 ETF）  
   - 参数建议：`n1` ∈ [5, 30]，`n2` ∈ [20, 120]  
   - 应增加净值型资产的交易成本设置（部分基金需较高滑点）

2. **ATR 追踪止损 (SmaCrossWithTrailing)**  
   - 用于波动较大的行业 ETF  
   - 调整 ATR 周期与倍数适应中国市场的波动率

3. **多均线组合 (Sma4Cross)**  
   - 针对 ETF 进行参数寻优与周期对比  
   - 可通过热力图分析寻找适合不同板块的周期组合

### 2.2 策略适配注意事项
- ETF 份额无涨跌停限制，但存在申购赎回费用与折溢价问题，需在策略中以自定义费用或滑点模拟。
- 公募基金持有期存在赎回费率，回测时可在 `Strategy.next()` 中手动调整 `commission`。
- 对于净值型基金，成交量字段可忽略，但应注意日内无法多次交易的现实约束。

## 3. 系统架构设计

### 3.1 目录结构
```
backtesting/
├── data/
│   └── chinese_stocks/
│       └── daily/
│           ├── etf/
│           │   └── *.csv
│           └── fund/
│               └── *.csv
├── strategies/
│   ├── __init__.py
│   ├── sma_cross.py
│   ├── sma_trailing.py
│   └── sma4_cross.py
├── utils/
│   ├── __init__.py
│   └── data_loader.py      # 扩展支持中国数据
├── results/
│   ├── reports/
│   ├── plots/
│   └── stats/
├── run_backtest.sh
└── backtest_runner.py
```

### 3.2 模块职责调整

#### 3.2.1 数据加载 (`utils/data_loader.py`)
- 新增通用 `load_ohlcv_csv` 函数，支持读取 `trade_date` → `Date` 并转换为 `datetime`.
- 扫描子目录（etf/fund）递归识别文件，构建 `{代码: 路径, 元数据}` 映射。
- 根据 `volume/amount` 等字段自动判断是否可用于日内策略。
- 暂停旧的 Lixinger 转换逻辑（保留备用），默认走中国数据路径。

#### 3.2.2 策略模块 (`strategies/*`)
- 策略逻辑保持不变，但在类属性中加入可选的交易成本参数。
- 添加 `metadata` 字典，用于在结果汇总中标记标的类型（ETF / Fund）。

#### 3.2.3 回测执行器 (`backtest_runner.py`)
- 默认 `--data-dir` 切换为 `data/chinese_stocks`.
- `--stock` 参数接受实际代码或 `all`，支持多级选择（如 `category:etf`）。
- 结果汇总时展示中文名称映射：`159001.SZ -> 华夏上证50ETF`（可由元数据文件或 CSV 列提供）。

#### 3.2.4 Shell脚本 (`run_backtest.sh`)
- 帮助信息更新为“中国市场回测”。
- 增加 `--category` / `--instrument` 选项，或通过 `--stock` 多值输入运行多个标的。
- 调用 `backtest_runner.py` 时传递新的参数组合，并允许指定输出目录前缀（如 `results/china_etf`）。

## 4. 实现细节

### 4.1 数据清洗
1. 将 `trade_date` 转为 `%Y-%m-%d` 格式并设为索引。
2. 强制转换价格列为浮点数，Volume/Amount 转为整数或浮点（视文件而定）。
3. 按日期升序排序，去除缺失或重复行。
4. 当同日存在多条记录（部分基金），保留最后一条或进行加权平均。

### 4.2 货币与单位
- ETF 价格单位为人民币元，Volume 为份额，Amount 为人民币。
- 基金净值通常小于 5，Volume/Amount 字段可用于识别二级市场或场外估值。
- `commission` 默认值需根据基金/ETF 现实费率调整（建议：ETF 0.0005，基金 0.0~0.015）。

### 4.3 输出内容
- 统计 CSV 保持中文列名，但新增 “标的代码”、“标的类型” 字段。
- 图表文件命名格式：`{instrument}_{strategy}_{timestamp}.html`。
- 若需要区分人民币，可在结果中增加 `货币: CNY` 字段说明。

### 4.4 日期过滤
- 支持 `--start-date YYYY-MM-DD` 与 `--end-date` 参数，过滤后输出有效区间。
- 若过滤后数据量 < 60 行（不足以跑均线策略），提前报错。

## 5. 使用场景

### 5.1 基础回测
```bash
# 对 159001.SZ 运行双均线策略
./run_backtest.sh -s 159001.SZ -t sma_cross

# 对 000001.OF 运行带止损策略
./run_backtest.sh -s 000001.OF -t sma_trailing
```

### 5.2 批量回测
```bash
# 批量跑所有 ETF
./run_backtest.sh --category etf -t all

# 指定多个标的
./run_backtest.sh -s 159001.SZ,510500.SH -t sma_cross
```

### 5.3 参数优化
```bash
# 优化某只 ETF 的均线组合
./run_backtest.sh -s 510300.SH -t sma_cross -o

# 基金净值策略调参
./run_backtest.sh -s 000001.OF -t sma4_cross -o --start-date 2020-01-01
```

### 5.4 日期过滤
```bash
./run_backtest.sh -s 510300.SH --start-date 2018-01-01 --end-date 2023-12-31
```

### 5.5 输出目录管理
回测结果默认写入 `results/`，建议按类别划分子目录：
```
results/
├── etf/
│   ├── stats/
│   └── plots/
└── fund/
    ├── stats/
    └── plots/
```

## 6. 技术考虑

### 6.1 性能
- 数据文件数量庞大（基金 >3000 只），需按需加载。
- `list_available_stocks` 需缓存扫描结果，避免重复递归读取。
- 在优化模式下，建议限制参数空间或采用随机搜索。

### 6.2 错误处理
- 缺失列或格式异常时提供明确错误信息，注明文件路径。
- 当 Volume/Amount 为 0 时，提示用户策略不应依赖成交量指标。
- 对无效日期范围或空数据，抛出 `ValueError` 并输出建议。

### 6.3 可扩展性
- 将数据解析逻辑独立到 `parsers/` 子模块，未来可接入港股、期货。
- 策略与数据之间通过 metadata 耦合，便于针对不同标的启用差异化手续费。

### 6.4 用户体验
- `run_backtest.sh` 输出中文提示，区分信息/警告/错误。
- 当批量回测多个标的时，提供进度条或计数提示。
- 在结果汇总中加入“标的类型 / 中文名称 / 年化收益 / 最大回撤”等列。

## 7. 测试计划

### 7.1 单元测试
- `test_data_loader.py`: 验证 `trade_date` 解析、OHLCV 类型转换、子目录扫描。
- `test_backtest_runner.py`: 测试 `--category`、`--stock` 多值解析、日期过滤。
- `test_strategies.py`: 针对 ETF 数据运行典型场景，验证信号与手续费处理。

### 7.2 集成测试
- 构建小型数据集（3 只 ETF + 2 只基金）跑全流程，检查输出文件存在性。
- 在优化模式下验证统计 CSV 中包含最优参数列。

### 7.3 数据验证
- 随机抽样 10 只标的，对比 CSV 行数与 DataFrame 行数一致。
- 验证涨跌幅计算：`close / pre_close - 1` 与 `pct_chg` 误差不超过 1bp。

## 8. 交付物
- `utils/data_loader.py`：新增通用 OHLCV 加载流程与多目录扫描能力。
- `backtest_runner.py`：更新 CLI 参数、结果汇总格式和默认数据目录。
- `run_backtest.sh`：支持中国标的输入、类别过滤、中文帮助文本。
- `strategies/*`：根据需要调整手续费、参数范围。
- 文档：更新 README & 运行指南，描述中国市场数据差异。

## 9. 时间估算
- 数据加载器改造：4h
- CLI 与脚本更新：3h
- 策略与手续费调整：2h
- 测试与验证：3h
- 文档与示例更新：2h  
**合计：14h**

## 10. 风险与挑战
- 数据文件数量过大导致扫描性能下降 → 使用缓存/懒加载。
- 场外基金缺乏真实成交量 → 某些指标失效，需要策略侧特殊处理。
- 不同标的价格量级差异大（货币基金 vs 行业 ETF） → 设置统一基准或归一化。
- 回测结果可能因为复权或净值拆分问题出现断层 → 需在数据加载阶段检测异常涨跌幅。
- 当前 `etf` / `fund` 收盘价视为已隐含复权效果，加载流程不额外执行复权调整；若未来接入未复权个股数据，应先在数据层完成前/后复权再进入策略。

## 11. 新功能规划：`run_backtest.sh` 支持中国标的

### 11.1 功能描述
将 `run_backtest.sh` 与 `backtest_runner.py` 从“美股双标的回测”升级为“支持中国 ETF / 基金全量回测”。该功能包括数据目录切换、标的分类选择、策略批量运行与输出结构调整。

### 11.2 TODO 列表
1. **数据目录切换**  
   - [ ] 将脚本与 Python 执行器的默认 `--data-dir` 改为 `data/chinese_stocks`.  
   - [ ] 新增参数 `--category {etf,fund,all}`；当用户指定类别时限制扫描目录。

2. **标的解析与映射**  
   - [ ] 更新 `list_available_stocks` 支持递归遍历并返回 `{code, path, category}`。  
   - [ ] 支持 `--stock` 同时接收逗号分隔的多个代码或 `all`。  
   - [x] 支持通过 CLI 参数限制回测标的数量（`--instrument-limit`）。  
   - 已在 `backtest_runner.py` 与 `run_backtest.sh` 中增加 `--instrument-limit`，可截取筛选顺序中前 N 个标的用于回测。  
   - [ ] 引入可选的中文名映射（JSON/CSV），在汇总输出中展示。

3. **数据加载适配**  
   - [ ] 新增 `load_ohlcv_csv`，解析 `trade_date`、生成标准 OHLCV。  
   - [ ] 根据 `category` 应用默认佣金（ETF 使用 0.0005，基金使用 0.0）。  
   - [ ] 保留原 `load_lixinger_data` 作为备用，但默认走新的解析流程。  
   - [ ] 调整 scripts/export_mysql_to_csv.py，利用 instrument_basic 表补齐 instrument_name 字段，并随日线 CSV 一并落盘。  
   - [ ] 在导出阶段基于 `instrument_daily` 的行情与 `adj_nav` 数据计算 `adj_factor`、`adj_close` 复权指标，并补充对应单元测试。  

4. **输出与日志**  
   - [ ] 更新结果文件命名与目录结构，区分 ETF/Fund（如 `results/etf/stats`）。  
   - [ ] 在 CLI 汇总表中新增列：`标的类型`、`中文名称`、`货币`。  
   - [ ] 统一脚本提示语为“中国市场回测系统”，提示用户余额在 CNY。

5. **验证流程**  
   - [ ] 为最少 2 个 ETF、1 个基金编写回测示例，确保脚本能顺利运行。  
   - [ ] 更新 README/AGENTS 文档，指导如何指定中国标的与类别。  
   - [ ] 记录潜在数据异常（如交易暂停导致的缺口），并在日志中输出警告。

6. **低波动标的过滤**  
   - [x] 在数据加载或回测入口处计算近段时间的年化波动率或价差，若低于阈值（如年化标准差 < 2%），标记为“低波动”并跳过回测。  
   - [x] 支持维护可配置黑名单（默认包含 159001.SZ 等货币基金类标的）。  
   - [x] 在 CLI 输出中明确告知被过滤的标的及原因，避免用户困惑。  
   - [x] 聚合摘要中记录被跳过的标的数量，为未来扩展留痕。  
   - 已在 `utils/data_loader.py` 中新增 `LowVolatilityConfig` 与年化波动率计算逻辑。  
   - `backtest_runner.py` 提供 `--min-annual-vol`、`--vol-lookback`、`--low-vol-blacklist` 等参数并输出过滤统计。  
   - `pytest backtesting/test/test_low_vol_filter.py` 对 159001.SZ 样本完成验收验证。

### 11.3 验收标准
- 默认执行 `./run_backtest.sh` 能列出中国标的并完成至少一个 ETF 的回测。  
- `python backtest_runner.py -s all --category etf` 能批量输出结果到新目录结构。  
- 文档与脚本帮助信息均不再提及 `data/american_stocks`。  
- 所有自动化测试通过，且针对中国数据的新增测试覆盖数据解析与 CLI 逻辑。
