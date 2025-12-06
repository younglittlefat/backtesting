# ETF Selector 评分权重系统统一重构

## 背景

### 问题描述

ETF Selector 原有两套独立的评分系统，配置复杂且存在以下问题：

1. **V1 Legacy 系统**：使用 `weights_v1_legacy` 配置，采用 primary/secondary 两级结构
   - primary（主要指标）：adx_score, trend_consistency, price_efficiency, liquidity_score
   - secondary（次要指标）：momentum_3m, momentum_12m

2. **V2 Optimized 系统**：使用 `weights_v2` 配置，采用不同的指标组合
   - core_trend（核心趋势）：excess_return_20d, excess_return_60d
   - trend_quality（趋势质量）
   - strength（趋势强度，实际就是 ADX）
   - volume（成交量趋势）
   - idr（风险调整后超额收益）

3. **问题**：
   - 两套系统使用不同的指标命名（如 V1 的 `adx_score` vs V2 的 `strength`，实际是同一指标）
   - 需要通过 `scoring_system.mode: "legacy"/"optimized"` 切换，无法灵活组合
   - 配置结构不统一，学习成本高
   - 无法直观看出哪些指标需要基准数据（benchmark）

### 重构目标

1. 统一两套评分系统为单一配置结构
2. 保留层级结构，按指标类型分组，便于理解和配置
3. 自动检测是否需要基准数据（当超额收益类指标权重 > 0 时）
4. 向后兼容旧版 V1/V2 配置文件

## 方案设计

### 指标分类

将所有 11 个评分指标按类型分为 4 组：

| 分组 | 指标 | 说明 | 是否需要基准 |
|------|------|------|-------------|
| **trend**（趋势类） | adx_score | ADX趋势强度 | 否 |
| | trend_consistency | 趋势一致性 | 否 |
| | trend_quality | 趋势质量(R²) | 否 |
| **return**（收益类） | momentum_3m | 3个月动量 | 否 |
| | momentum_12m | 12个月动量 | 否 |
| | excess_return_20d | 20日超额收益 | **是** |
| | excess_return_60d | 60日超额收益 | **是** |
| **liquidity**（流动性类） | liquidity_score | 流动性评分 | 否 |
| | price_efficiency | 价格效率 | 否 |
| | volume_trend | 成交量趋势 | 否 |
| **risk_adjusted**（风险调整类） | idr | 风险调整后超额收益 | **是** |

### 权重计算方式

采用两级权重结构：
- **组权重（weight）**：该指标组在总评分中的占比
- **子权重（sub_weights）**：组内各指标的相对权重

**最终权重 = 组权重 × 子权重**

例如：trend 组权重 0.50，adx_score 子权重 0.50，则 adx_score 最终权重 = 0.50 × 0.50 = 0.25

### 自动基准检测

当以下任一指标的最终权重 > 0 时，系统自动加载基准数据：
- `excess_return_20d`
- `excess_return_60d`
- `idr`

无需手动配置 `enable_benchmark_relative` 等开关。

## 实际实现

### 修改的文件

| 文件 | 修改内容 |
|------|---------|
| `etf_selector/config.py` | 新增 11 个统一权重字段 `weight_*`，添加辅助方法 |
| `etf_selector/config_loader.py` | 支持解析 V3 层级格式，保留 V1/V2 兼容转换 |
| `etf_selector/scoring.py` | 新增 `ScoringWeights` 和 `UnifiedScorer` 类 |
| `etf_selector/selector.py` | 使用统一评分系统替代 V1/V2 分支逻辑 |
| `etf_selector/configs/default.json` | 更新为 V3 层级配置格式 |

### 核心代码结构

#### 1. ScoringWeights 数据类（scoring.py）

```python
@dataclass
class ScoringWeights:
    """统一评分权重配置"""
    # 趋势类
    adx_score: float = 0.0
    trend_consistency: float = 0.0
    trend_quality: float = 0.0
    # 收益类
    momentum_3m: float = 0.0
    momentum_12m: float = 0.0
    excess_return_20d: float = 0.0
    excess_return_60d: float = 0.0
    # 流动性类
    liquidity_score: float = 0.0
    price_efficiency: float = 0.0
    volume_trend: float = 0.0
    # 风险调整类
    idr: float = 0.0
```

#### 2. FilterConfig 辅助方法（config.py）

```python
def get_scoring_weights(self) -> Dict[str, float]:
    """获取评分权重配置字典"""
    return {
        'adx_score': self.weight_adx_score,
        'trend_consistency': self.weight_trend_consistency,
        # ... 其他指标
    }

def needs_benchmark(self) -> bool:
    """是否需要基准数据"""
    return (
        self.weight_excess_return_20d > 0 or
        self.weight_excess_return_60d > 0 or
        self.weight_idr > 0
    )

def get_active_indicators(self) -> List[str]:
    """获取所有权重>0的指标名称"""
    weights = self.get_scoring_weights()
    return [k for k, v in weights.items() if v > 0]
```

#### 3. 配置加载转换逻辑（config_loader.py）

支持三种配置格式的自动识别和转换：

1. **V3 层级格式**（推荐）：`weights.trend.weight` + `weights.trend.sub_weights.*`
2. **扁平格式**：`weights.adx_score` 等直接设置
3. **旧版格式**：`weights_v1_legacy.*` 或 `weights_v2.*`（向后兼容）

### V1/V2 到新版的指标映射

| V1 Legacy | V2 Optimized | 新版统一 |
|-----------|--------------|---------|
| `adx_score_weight` | `strength_weight` | `adx_score` |
| `trend_consistency_weight` | - | `trend_consistency` |
| `price_efficiency_weight` | - | `price_efficiency` |
| `liquidity_score_weight` | - | `liquidity_score` |
| `momentum_3m_score_weight` | - | `momentum_3m` |
| `momentum_12m_score_weight` | - | `momentum_12m` |
| - | `core_trend_weight` × `excess_return_20d_weight` | `excess_return_20d` |
| - | `core_trend_weight` × `excess_return_60d_weight` | `excess_return_60d` |
| - | `trend_quality_weight` | `trend_quality` |
| - | `volume_weight` | `volume_trend` |
| - | `idr_weight` | `idr` |

## 配置范例

### 范例 1：V3 层级格式（推荐）

```json
{
  "version": "3.0",
  "description": "ETF Selector 统一配置",

  "scoring_system": {
    "enable_unbiased_scoring": true,
    "benchmark": {
      "ts_code": "510300.SH"
    },

    "weights": {
      "trend": {
        "_description": "趋势类指标",
        "weight": 0.50,
        "sub_weights": {
          "adx_score": 0.50,
          "trend_consistency": 0.30,
          "trend_quality": 0.20
        }
      },

      "return": {
        "_description": "收益类指标",
        "weight": 0.20,
        "sub_weights": {
          "momentum_3m": 0.30,
          "momentum_12m": 0.70,
          "excess_return_20d": 0.0,
          "excess_return_60d": 0.0
        }
      },

      "liquidity": {
        "_description": "流动性/成交量类指标",
        "weight": 0.30,
        "sub_weights": {
          "liquidity_score": 0.30,
          "price_efficiency": 0.50,
          "volume_trend": 0.20
        }
      },

      "risk_adjusted": {
        "_description": "风险调整类指标（需要基准）",
        "weight": 0.0,
        "sub_weights": {
          "idr": 1.0
        }
      }
    }
  }
}
```

上述配置的最终权重计算：
- adx_score: 0.50 × 0.50 = **0.25**
- trend_consistency: 0.50 × 0.30 = **0.15**
- trend_quality: 0.50 × 0.20 = **0.10**
- momentum_3m: 0.20 × 0.30 = **0.06**
- momentum_12m: 0.20 × 0.70 = **0.14**
- liquidity_score: 0.30 × 0.30 = **0.09**
- price_efficiency: 0.30 × 0.50 = **0.15**
- volume_trend: 0.30 × 0.20 = **0.06**
- **总和**: 0.25 + 0.15 + 0.10 + 0.06 + 0.14 + 0.09 + 0.15 + 0.06 = **1.00** ✓

### 范例 2：单一指标评分

只使用 ADX 趋势强度评分：

```json
{
  "scoring_system": {
    "weights": {
      "trend": {
        "weight": 1.0,
        "sub_weights": {
          "adx_score": 1.0,
          "trend_consistency": 0,
          "trend_quality": 0
        }
      },
      "return": { "weight": 0, "sub_weights": {} },
      "liquidity": { "weight": 0, "sub_weights": {} },
      "risk_adjusted": { "weight": 0, "sub_weights": {} }
    }
  }
}
```

### 范例 3：使用超额收益指标（自动启用基准）

```json
{
  "scoring_system": {
    "benchmark": {
      "ts_code": "510300.SH"
    },
    "weights": {
      "trend": {
        "weight": 0.40,
        "sub_weights": {
          "adx_score": 0.60,
          "trend_quality": 0.40
        }
      },
      "return": {
        "weight": 0.40,
        "sub_weights": {
          "excess_return_20d": 0.40,
          "excess_return_60d": 0.60
        }
      },
      "liquidity": {
        "weight": 0.20,
        "sub_weights": {
          "volume_trend": 1.0
        }
      },
      "risk_adjusted": { "weight": 0, "sub_weights": {} }
    }
  }
}
```

由于 `excess_return_20d` 和 `excess_return_60d` 权重 > 0，系统会自动加载 `510300.SH` 基准数据。

### 范例 4：旧版配置（向后兼容）

V1 Legacy 格式仍然支持：

```json
{
  "scoring_system": {
    "mode": "legacy",
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
  }
}
```

系统会自动转换为统一格式：
- adx_score: 0.80 × 0.40 = 0.32
- trend_consistency: 0.80 × 0.30 = 0.24
- price_efficiency: 0.80 × 0.20 = 0.16
- liquidity_score: 0.80 × 0.10 = 0.08
- momentum_3m: 0.20 × 0.30 = 0.06
- momentum_12m: 0.20 × 0.70 = 0.14

## 验证方法

运行单一指标评分验证：

```bash
# 只使用 adx_score
python -m etf_selector.main --config experiment/etf/selector_score/single_primary/single_adx_score.json

# 只使用 trend_consistency
python -m etf_selector.main --config experiment/etf/selector_score/single_primary/single_trend_consistency.json
```

输出 CSV 将只包含权重 > 0 的指标分量列（如 `adx_score_component`），不再输出无关的 normalized 列。

## 注意事项

1. **权重验证**：所有权重总和必须为 1.0（允许 ±0.01 误差）
2. **基准数据**：使用超额收益类指标时，确保 `benchmark.ts_code` 配置正确
3. **向后兼容**：旧版 V1/V2 配置文件无需修改，可继续使用
4. **输出变化**：新版只输出实际使用的指标分量，CSV 列数可能减少
