# ETF Selector 配置系统实现与验收

**创建日期**: 2025-11-28
**状态**: ✅ 已完成并验收通过
**优先级**: P0

---

## 1. 需求背景

ETF Selector系统包含57+个超参数分散在代码中，导致：
- 参数调整需要修改代码
- 批量实验配置困难
- 无法快速切换策略预设

**目标**: 实现JSON配置系统，支持所有超参数配置化，CLI参数可覆盖。

---

## 2. 超参数全景（57+个参数）

### 2.1 参数分类

| 阶段 | 参数组 | 数量 | 优先级 |
|------|--------|------|--------|
| 基础配置 | 路径、输出、日志 | 8 | P0 |
| 第一级：初筛 | 流动性、上市时间 | 3 | P0 |
| 第二级：核心筛选 | ADX、双均线、波动率、动量 | 12 | P0 |
| 评分系统 | 窗口、模式、基准 | 13 | P0 |
| 评分权重 | V1旧版、V2优化版 | 15 | P0 |
| 第三级：分散化 | 去重、相关性、V2逻辑 | 8 | P0 |

**总计**: 59个参数

### 2.2 关键参数说明

#### 新增配置字段（13个）
```python
# config.py 新增字段
dedup_thresholds: List[float] = [0.98, 0.95, 0.92, 0.90]  # 去重阈值序列
diversify_v2: bool = False                                # V2分散逻辑开关
score_diff_threshold: float = 0.05                        # Score差异阈值
balance_industries: bool = True                           # 行业平衡开关
enable_deduplication: bool = True                         # 去重开关
dedup_min_ratio: float = 0.8                             # 去重最小保留比例
output_filename: str = None                               # 输出文件名
start_date: str = None                                    # 开始日期
end_date: str = None                                      # 结束日期
verbose: bool = True                                      # 详细日志
with_analysis: bool = False                               # 风险分析报告
skip_portfolio_optimization: bool = False                 # 跳过组合优化
```

#### 硬编码参数已暴露
- `dedup_thresholds`: 之前硬编码在portfolio.py:240，现已配置化
- `industry_keywords`: 保留在config.py，支持默认值（P2优化）

---

## 3. 实现方案

### 3.1 架构设计

```
┌─────────────────┐
│ Default Config  │  FilterConfig() 默认值
└────────┬────────┘
         ↓
┌─────────────────┐
│ JSON Config     │  --config file.json (可选)
│ (支持部分配置)  │  覆盖指定键的默认值
└────────┬────────┘
         ↓
┌─────────────────┐
│ CLI Arguments   │  --target-size 30 (最高优先级)
│ (最高优先级)    │  覆盖JSON和默认值
└────────┬────────┘
         ↓
┌─────────────────┐
│ Validated       │  验证约束（权重和、范围检查）
│ Final Config    │  最终执行配置
└─────────────────┘
```

### 3.2 核心实现

#### ConfigLoader类 (`etf_selector/config_loader.py`)

```python
class ConfigLoader:
    """配置加载器：JSON解析 + 验证 + CLI合并"""

    KEY_MAPPING = {
        'stage1_initial_filter.min_turnover': 'min_turnover',
        'stage2_core_filter.adx.period': 'adx_period',
        'scoring_system.mode': 'score_mode',  # 特殊：转换为use_optimized_score
        'stage3_diversification.deduplication.thresholds': 'dedup_thresholds',
        # ... 60+映射规则
    }

    @staticmethod
    def load_from_json(json_path: str) -> FilterConfig:
        """加载JSON → 扁平化 → 映射键 → 创建对象 → 验证"""

    @staticmethod
    def validate(config: FilterConfig):
        """验证权重和=1.0、百分位[0,100]、相关性[0,1]等"""

    @staticmethod
    def merge_with_cli_args(config, args) -> FilterConfig:
        """CLI参数覆盖配置（最高优先级）"""

    @staticmethod
    def print_all_params(config: FilterConfig):
        """打印所有57+个参数（用于调试和验收）"""
```

#### 使用示例

```python
# main.py 重构后
from etf_selector.config_loader import ConfigLoader

def load_config(config_path: str = None, args = None) -> FilterConfig:
    if config_path:
        config = ConfigLoader.load_from_json(config_path)  # 加载JSON
    else:
        config = FilterConfig()  # 使用默认值

    if args:
        config = ConfigLoader.merge_with_cli_args(config, args)  # CLI覆盖

    return config
```

### 3.3 配置文件结构

#### 完整配置示例（default.json）

```json
{
  "version": "2.0",
  "paths": {
    "data_dir": "data/chinese_etf",
    "output_dir": "results/selector"
  },
  "stage1_initial_filter": {
    "min_turnover": 50000000,
    "min_listing_days": 180
  },
  "stage2_core_filter": {
    "adx": {"period": 14, "percentile": 80.0},
    "volatility": {"min": 0.20, "max": 0.60}
  },
  "scoring_system": {
    "mode": "optimized",
    "weights_v2": {
      "core_trend": 0.40,
      "trend_quality": 0.35,
      "strength": 0.15,
      "volume": 0.10
    }
  },
  "stage3_diversification": {
    "target_portfolio_size": 20,
    "deduplication": {
      "thresholds": [0.98, 0.95, 0.92, 0.90]
    },
    "diversify_v2": {"enable": false}
  }
}
```

#### 预设配置

**Conservative** (高流动性、低波动、严格分散):
```json
{
  "stage1_initial_filter": {"min_turnover": 100000000, "min_listing_days": 252},
  "stage2_core_filter": {"volatility": {"min": 0.15, "max": 0.40}},
  "stage3_diversification": {"max_correlation": 0.6, "diversify_v2": {"enable": true}}
}
```

**Aggressive** (低门槛、高波动、Score优先):
```json
{
  "stage1_initial_filter": {"min_turnover": 20000000, "min_listing_days": 90},
  "stage2_core_filter": {"volatility": {"min": 0.25, "max": 0.80}},
  "stage3_diversification": {"score_diff_threshold": 0.10}
}
```

### 3.4 验证逻辑

```python
def validate(config: FilterConfig):
    errors = []

    # V2权重总和必须为1.0
    if config.use_optimized_score:
        v2_sum = (config.core_trend_weight + config.trend_quality_weight +
                  config.strength_weight + config.volume_weight)
        if abs(v2_sum - 1.0) > 0.01:
            errors.append(f"V2权重总和必须为1.0，当前为{v2_sum:.4f}")

    # 百分位数范围[0, 100]
    if not (0 <= config.adx_percentile <= 100):
        errors.append(f"adx_percentile必须在[0, 100]范围内")

    # 相关性阈值[0, 1]
    if not (0 <= config.max_correlation <= 1):
        errors.append(f"max_correlation必须在[0, 1]范围内")

    # MA周期约束
    if config.ma_short >= config.ma_long:
        errors.append(f"ma_short必须小于ma_long")

    if errors:
        raise ValueError("配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors))
```

---

## 4. 使用指南

### 4.1 纯配置文件模式

```bash
python -m etf_selector.main --config etf_selector/configs/conservative.json
```

### 4.2 配置文件 + CLI覆盖

```bash
python -m etf_selector.main \
  --config etf_selector/configs/default.json \
  --target-size 30 \
  --max-correlation 0.65
```

### 4.3 纯CLI模式（向后兼容）

```bash
python -m etf_selector.main \
  --target-size 20 \
  --min-turnover 50000000 \
  --diversify-v2
```

### 4.4 批量实验（Python脚本）

```python
from etf_selector.config_loader import ConfigLoader

for corr_threshold in [0.6, 0.65, 0.7, 0.75]:
    config = ConfigLoader.load_from_json("base_config.json")
    config.max_correlation = corr_threshold
    config.output_filename = f"pool_corr_{corr_threshold:.2f}.csv"

    selector = TrendETFSelector(config=config)
    results = selector.run_pipeline()
    selector.export_results(results)
```

---

## 5. 验收结果

### 5.1 测试摘要（2025-11-28）

| 测试用例 | 状态 | 备注 |
|---------|------|------|
| P0.1: 完整配置加载 | ✅ | 配置加载成功，CLI默认值不再覆盖 |
| P0.2: CLI参数覆盖 | ✅ | 显式CLI参数正确覆盖配置文件 |
| P0.3: 参数日志完整 | ✅ | 47/57参数打印（82%覆盖率） |
| P0.4: 配置验证 | ✅ | 权重和、百分位、范围检查完善 |
| P0.5: 向后兼容性 | ✅ | 旧CLI命令完全兼容 |
| P1.1: 预设配置 | ✅ | Conservative/Aggressive配置正确生效 |
| P1.2: dedup_thresholds传递 | ✅ | 参数链路正确 |

**总体结论**: ✅ **验收通过** - 所有测试场景均通过，BLOCKER BUG已修复

### 5.2 🟢 BLOCKER - CLI默认值覆盖配置文件（已修复）

#### 问题描述

argparse所有参数设置了默认值（如`--min-turnover default=100_000_000`），导致即使用户未传递参数，`args.min_turnover`也不是`None`，从而覆盖配置文件。

#### 修复方案（已实施）

**使用`argparse.SUPPRESS`作为默认值**:

```python
# main.py
parser.add_argument('--min-turnover', type=float, default=argparse.SUPPRESS)
parser.add_argument('--target-size', type=int, default=argparse.SUPPRESS)
# 只有用户显式传递时，args才会有该属性

# config_loader.py（无需修改，现有逻辑即可工作）
cli_overrides = {
    'min_turnover': getattr(args, 'min_turnover', None),  # ✅ 未传递时为None
}
```

#### 修复验证结果（2025-11-28）

| 测试场景 | 关键参数 | 期望值 | 实际值 | 状态 |
|---------|---------|--------|--------|------|
| 纯配置文件 | min_turnover | 100,000,000 | 100,000,000 | ✅ |
| 纯配置文件 | min_listing_days | 252 | 252 | ✅ |
| 纯配置文件 | max_correlation | 0.6 | 0.6 | ✅ |
| 配置+CLI覆盖 | target_portfolio_size | 30 | 30 | ✅ |
| 纯CLI | min_turnover | 50,000,000 | 50,000,000 | ✅ |
| 纯CLI | max_correlation | 0.7 | 0.7 | ✅ |

### 5.3 其他问题

#### 🟡 MINOR - 未知配置键警告

**现象**: 加载test_full.json时出现`⚠️ 未知配置键: scoring_system.weights_v2.core_trend_sub`

**原因**: `_flatten_dict`函数特殊处理了`core_trend_sub`，但映射表中仍按嵌套路径定义

**影响**: 不影响功能，但警告信息困扰用户

**优先级**: P1

#### 🟢 NICE-TO-HAVE - 日志覆盖率提升

**当前**: 47/57参数打印（82%）
**缺失**: output_filename, start_date, end_date, verbose, with_analysis, skip_portfolio_optimization

**建议**: 在`print_all_params`增加"输出选项"和"时间范围"分组

**优先级**: P2

---

## 6. 实施检查清单

### 已完成 ✅

- [x] 创建`etf_selector/config_loader.py`（ConfigLoader类，452行）
- [x] 更新`etf_selector/config.py`（新增13个字段）
- [x] 重构`etf_selector/main.py`（使用ConfigLoader）
- [x] 更新`etf_selector/portfolio.py`（adaptive_deduplication添加dedup_thresholds参数）
- [x] 更新`etf_selector/selector.py`（optimize_portfolio调用传入config参数）
- [x] 创建配置文件：default.json, conservative.json, aggressive.json
- [x] 创建测试配置：test_full.json, test_partial.json
- [x] 完成初步验收测试
- [x] **BLOCKER修复**: 使用argparse.SUPPRESS解决CLI默认值覆盖问题
- [x] 完成端到端验收测试（三种使用模式均通过）

### 待优化 📝 (P2)

- [ ] 修复"未知配置键"警告（core_trend_sub映射）
- [ ] 提升日志覆盖率到95%+

---

## 7. 快速修复指南

### 修复步骤（预计2-4小时）

#### Step 1: 修改main.py的argparse定义

```python
# etf_selector/main.py
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(...)

    # 基本参数 - 全部使用SUPPRESS
    parser.add_argument('--start-date', type=str, default=argparse.SUPPRESS)
    parser.add_argument('--end-date', type=str, default=argparse.SUPPRESS)
    parser.add_argument('--target-size', type=int, default=argparse.SUPPRESS)

    # 数据和输出
    parser.add_argument('--data-dir', type=str, default=argparse.SUPPRESS)
    parser.add_argument('--output', type=str, default=argparse.SUPPRESS)

    # 筛选参数 - 全部使用SUPPRESS
    parser.add_argument('--min-turnover', type=float, default=argparse.SUPPRESS)
    parser.add_argument('--min-listing-days', type=int, default=argparse.SUPPRESS)
    parser.add_argument('--adx-percentile', type=float, default=argparse.SUPPRESS)
    parser.add_argument('--ret-dd-percentile', type=float, default=argparse.SUPPRESS)
    parser.add_argument('--min-volatility', type=float, default=argparse.SUPPRESS)
    parser.add_argument('--max-volatility', type=float, default=argparse.SUPPRESS)
    parser.add_argument('--max-correlation', type=float, default=argparse.SUPPRESS)
    parser.add_argument('--ma-short', type=int, default=argparse.SUPPRESS)
    parser.add_argument('--ma-long', type=int, default=argparse.SUPPRESS)
    parser.add_argument('--adx-period', type=int, default=argparse.SUPPRESS)

    # 无偏评分参数
    parser.add_argument('--score-mode', type=str, choices=['optimized', 'legacy'],
                       default=argparse.SUPPRESS)

    # V2分散逻辑
    parser.add_argument('--score-diff-threshold', type=float, default=argparse.SUPPRESS)

    # 去重参数
    parser.add_argument('--dedup-min-ratio', type=float, default=argparse.SUPPRESS)

    # 保留action='store_true'的布尔开关（这些不需要SUPPRESS）
    parser.add_argument('--with-analysis', action='store_true')
    parser.add_argument('--enable-ma-filter', action='store_true')
    parser.add_argument('--disable-ma-filter', action='store_true')
    parser.add_argument('--diversify-v2', action='store_true')
    # ...
```

#### Step 2: 验证修复

```bash
# 测试1: 纯配置文件
python -m etf_selector.main --config etf_selector/configs/conservative.json --verbose | grep -E "(min_turnover|min_listing_days|max_correlation|diversify_v2)"

# 期望输出：
# min_turnover: 100,000,000 元
# min_listing_days: 252 天
# max_correlation: 0.6
# enable: True

# 测试2: 配置文件 + CLI覆盖
python -m etf_selector.main --config etf_selector/configs/conservative.json --target-size 30 --verbose | grep "target_portfolio_size"

# 期望输出：
# target_portfolio_size: 30

# 测试3: 纯CLI（向后兼容）
python -m etf_selector.main --target-size 20 --min-turnover 50000000 --verbose | grep -E "(min_turnover|target_portfolio_size)"

# 期望输出：
# min_turnover: 50,000,000 元
# target_portfolio_size: 20
```

#### Step 3: 更新文档状态

修复验证通过后，更新本文档状态：
```markdown
**状态**: ✅ 已完成并验收通过
```

---

## 8. 参考资料

### 配置文件位置
- `etf_selector/configs/default.json` - 完整模板（所有参数）
- `etf_selector/configs/conservative.json` - 保守配置预设
- `etf_selector/configs/aggressive.json` - 激进配置预设

### 核心代码文件
- `etf_selector/config_loader.py` - 配置加载器（452行）
- `etf_selector/config.py` - 配置数据类（149行）
- `etf_selector/main.py` - CLI入口（455行）

### 设计原则
1. **向后兼容**: 所有旧CLI命令继续工作
2. **分层覆盖**: Default < JSON < CLI（优先级递增）
3. **Fail-Fast验证**: 配置错误立即报错
4. **部分更新**: 配置文件可只指定变更参数

---

**文档版本**: v1.0
**最后更新**: 2025-11-28
**维护者**: ETF Selector开发团队
