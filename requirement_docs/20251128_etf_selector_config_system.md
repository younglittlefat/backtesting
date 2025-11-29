# ETF Selector 配置系统实现与验收

**创建日期**: 2025-11-28
**状态**: ✅ 已完成并验收通过
**最后更新**: 2025-11-29
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

### 3.2 配置文件结构（嵌套层级格式）

配置文件采用嵌套层级结构，清晰表达参数之间的从属关系：

#### 完整配置示例（default.json）

```json
{
  "version": "2.0",
  "description": "ETF Selector Complete Configuration Template",

  "paths": {
    "data_dir": "data/chinese_etf",
    "output_dir": "results/selector",
    "output_filename": null
  },

  "time_range": {
    "start_date": "20190102",
    "end_date": "20211231"
  },

  "stage1_initial_filter": {
    "min_turnover": 50000,
    "min_listing_days": 180,
    "turnover_lookback_days": 30
  },

  "stage2_core_filter": {
    "adx": {
      "period": 14,
      "lookback_days": 250,
      "percentile": 80.0
    },
    "ma_backtest": {
      "enable": false,
      "short_period": 20,
      "long_period": 50,
      "ret_dd_percentile": 70.0
    },
    "volatility": {
      "min": 0.20,
      "max": 0.60,
      "lookback_days": 252
    },
    "momentum": {
      "periods": [63, 252],
      "min_positive": true
    },
    "filter_mode": {
      "skip_percentile_filtering": true,
      "skip_range_filtering": true
    }
  },

  "scoring_system": {
    "enable_unbiased_scoring": true,
    "mode": "legacy",
    "benchmark": {
      "ts_code": "510300.SH"
    },

    "windows": {
      "excess_return": {
        "short": 20,
        "long": 60
      },
      "volume": {
        "short": 20,
        "long": 60
      },
      "trend_quality": 60,
      "trend_consistency": 63,
      "price_efficiency": 252,
      "liquidity_score": 30
    },

    "weights_v2": {
      "core_trend": 0.40,
      "trend_quality": 0.35,
      "strength": 0.15,
      "volume": 0.10,
      "idr": 0.0,
      "core_trend_sub": {
        "excess_return_20d": 0.40,
        "excess_return_60d": 0.60
      }
    },

    "weights_v1_legacy": {
      "primary": {
        "weight": 0.80,
        "sub_weights": {
          "adx_score": 0.40,
          "trend_consistency": 0.30,
          "price_efficiency": 0.20,
          "liquidity_score": 0.10
        }
      },
      "secondary": {
        "weight": 0.20,
        "sub_weights": {
          "momentum_3m": 0.30,
          "momentum_12m": 0.70
        }
      }
    }
  },

  "stage3_diversification": {
    "target_portfolio_size": 20,
    "max_correlation": 0.7,
    "min_industries": 3,
    "deduplication": {
      "enable": true,
      "min_ratio": 0.8,
      "thresholds": [0.98, 0.95, 0.92, 0.90]
    },
    "diversify_v2": {
      "enable": false,
      "score_diff_threshold": 0.05
    },
    "balance_industries": true
  },

  "output_options": {
    "verbose": true,
    "with_analysis": false,
    "skip_portfolio_optimization": false
  }
}
```

### 3.3 权重配置层级说明

#### weights_v1_legacy（旧版评分系统）

评分公式：`final_score = primary.weight × primary_score + secondary.weight × secondary_score`

其中：
- **primary_score** = `adx_score × ADX + trend_consistency × TC + price_efficiency × PE + liquidity_score × LQ`
- **secondary_score** = `momentum_3m × M3M + momentum_12m × M12M`

**约束条件**：
1. `primary.sub_weights` 四个子权重之和必须等于 1.0
2. `secondary.sub_weights` 两个子权重之和必须等于 1.0
3. `primary.weight + secondary.weight` 必须等于 1.0

**单因子测试示例**（仅使用 ADX 评分）：

```json
"weights_v1_legacy": {
  "primary": {
    "weight": 1.0,
    "sub_weights": {
      "adx_score": 1.0,
      "trend_consistency": 0,
      "price_efficiency": 0,
      "liquidity_score": 0
    }
  },
  "secondary": {
    "weight": 0,
    "sub_weights": {
      "momentum_3m": 0.5,
      "momentum_12m": 0.5
    }
  }
}
```

#### windows（计算窗口参数）

采用嵌套结构将相关参数分组：

```json
"windows": {
  "excess_return": {
    "short": 20,
    "long": 60
  },
  "volume": {
    "short": 20,
    "long": 60
  },
  "trend_quality": 60,
  "trend_consistency": 63,
  "price_efficiency": 252,
  "liquidity_score": 30
}
```

### 3.4 核心实现

#### ConfigLoader类 (`etf_selector/config_loader.py`)

```python
class ConfigLoader:
    """配置加载器：JSON解析 + 验证 + CLI合并"""

    KEY_MAPPING = {
        # 嵌套层级映射
        'scoring_system.windows.excess_return.short': 'excess_return_short_window',
        'scoring_system.windows.excess_return.long': 'excess_return_long_window',
        'scoring_system.windows.volume.short': 'volume_short_window',
        'scoring_system.windows.volume.long': 'volume_long_window',

        'scoring_system.weights_v1_legacy.primary.weight': 'primary_weight',
        'scoring_system.weights_v1_legacy.primary.sub_weights.adx_score': 'adx_score_weight',
        'scoring_system.weights_v1_legacy.primary.sub_weights.trend_consistency': 'trend_consistency_weight',
        'scoring_system.weights_v1_legacy.primary.sub_weights.price_efficiency': 'price_efficiency_weight',
        'scoring_system.weights_v1_legacy.primary.sub_weights.liquidity_score': 'liquidity_score_weight',
        'scoring_system.weights_v1_legacy.secondary.weight': 'secondary_weight',
        'scoring_system.weights_v1_legacy.secondary.sub_weights.momentum_3m': 'momentum_3m_score_weight',
        'scoring_system.weights_v1_legacy.secondary.sub_weights.momentum_12m': 'momentum_12m_score_weight',
        # ... 其他映射规则
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
```

---

## 4. 使用指南

### 4.1 纯配置文件模式

```bash
python -m etf_selector.main --config etf_selector/configs/default.json
```

### 4.2 配置文件 + CLI覆盖

```bash
python -m etf_selector.main \
  --config etf_selector/configs/default.json \
  --target-size 30 \
  --max-correlation 0.65
```

### 4.3 单因子测试

创建配置文件测试单个评分因子（如仅使用 ADX）：

```bash
python -m etf_selector.main --config experiment/etf/selector_score/single_adx.json
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

### 5.1 测试摘要（2025-11-29 更新）

| 测试用例 | 状态 | 备注 |
|---------|------|------|
| P0.1: 完整配置加载 | ✅ | 嵌套层级格式正确解析 |
| P0.2: CLI参数覆盖 | ✅ | 显式CLI参数正确覆盖配置文件 |
| P0.3: 权重验证 | ✅ | primary/secondary 子权重和=1 检查通过 |
| P0.4: 单因子测试 | ✅ | single_primary.json 成功运行 |
| P0.5: 向后兼容性 | ✅ | 旧CLI命令完全兼容 |

**总体结论**: ✅ **验收通过**

### 5.2 2025-11-29 层级配置优化

#### 改进内容

1. **weights_v1_legacy 结构优化**
   - 旧格式：扁平化，子权重与父权重混在一起
   - 新格式：嵌套层级，明确表达 primary/secondary 与其子因子的从属关系

2. **windows 结构优化**
   - 旧格式：`excess_return_short`, `excess_return_long`, `volume_short`, `volume_long`
   - 新格式：`excess_return.short`, `excess_return.long`, `volume.short`, `volume.long`

3. **修复 core_trend_sub 警告**
   - 问题：加载配置时出现 `⚠️ 未知配置键: scoring_system.weights_v2.core_trend_sub`
   - 解决：在 `_map_json_keys` 中跳过嵌套字典标记

---

## 6. 实施检查清单

### 已完成 ✅

- [x] 创建`etf_selector/config_loader.py`（ConfigLoader类）
- [x] 更新`etf_selector/config.py`（新增13个字段）
- [x] 重构`etf_selector/main.py`（使用ConfigLoader）
- [x] 创建配置文件：default.json, conservative.json, aggressive.json
- [x] **BLOCKER修复**: 使用argparse.SUPPRESS解决CLI默认值覆盖问题
- [x] 完成端到端验收测试
- [x] **层级配置优化**: weights_v1_legacy 和 windows 采用嵌套结构
- [x] **修复警告**: core_trend_sub 未知配置键警告已修复

---

## 7. 参考资料

### 配置文件位置
- `etf_selector/configs/default.json` - 完整模板（所有参数）
- `etf_selector/configs/conservative.json` - 保守配置预设
- `etf_selector/configs/aggressive.json` - 激进配置预设

### 核心代码文件
- `etf_selector/config_loader.py` - 配置加载器
- `etf_selector/config.py` - 配置数据类
- `etf_selector/main.py` - CLI入口

### 设计原则
1. **向后兼容**: 所有旧CLI命令继续工作
2. **分层覆盖**: Default < JSON < CLI（优先级递增）
3. **Fail-Fast验证**: 配置错误立即报错
4. **语义清晰**: 嵌套层级结构表达参数从属关系

---

**文档版本**: v1.1
**最后更新**: 2025-11-29
**维护者**: ETF Selector开发团队
