# Shell 脚本简化重构

**日期**: 2025-11-27
**作者**: Claude Code
**状态**: ✅ 已完成

## 背景

项目中有两个核心 Shell 脚本用于启动回测和信号生成：
- `run_backtest.sh` - 1092 行
- `generate_daily_signals.sh` - 596 行

这些脚本存在以下问题：
1. **重复代码严重**：每个参数都需要声明变量、解析 case 分支、构建命令——同样的模式重复 50+ 次
2. **维护成本高**：新增参数需要同时修改 Shell 和 Python 两处
3. **下划线/连字符兼容重复**：如 `--enable-hysteresis` 和 `--enable_hysteresis` 分别写了两个 case
4. **帮助文档冗长**：手写 200+ 行帮助文档

## 解决方案

### 方案选择

评估了三种方案后选择**方案二：迁移到 Python 入口脚本**：

| 方案 | 描述 | 优缺点 |
|-----|------|--------|
| 方案一 | 声明式配置 + 循环处理 | 仍需维护 Shell 代码 |
| **方案二** | 迁移到 Python 入口 | ✅ 最简洁，利用 argparse |
| 方案三 | Shell 模块化拆分 | 复杂度仍较高 |

### 实现思路

1. Shell 脚本仅负责：
   - 环境检查（conda 路径、环境、Python 脚本）
   - 参数透传（`"$@"`）
   - 显示启动/完成信息

2. Python 端负责：
   - 参数解析（argparse）
   - 帮助文档生成
   - 参数验证
   - 业务逻辑

3. 创建 `UnderscoreHyphenArgumentParser` 支持下划线参数格式

## 变更详情

### 文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `run_backtest.sh` | 重写 | 1092 → 100 行 |
| `run_backtest.sh.bak` | 新增 | 原始脚本备份 |
| `generate_daily_signals.sh` | 重写 | 596 → 98 行 |
| `generate_daily_signals.sh.bak` | 新增 | 原始脚本备份 |
| `backtest_runner/utils/argparse_utils.py` | 新增 | 共享参数解析工具 |
| `backtest_runner/utils/__init__.py` | 修改 | 导出新工具类 |
| `backtest_runner/config/argparser.py` | 修改 | 使用共享模块 |
| `generate_signals.py` | 修改 | 使用 UnderscoreHyphenArgumentParser |

### 代码量对比

| 脚本 | 原始行数 | 简化后 | 减少比例 |
|------|---------|--------|---------|
| `run_backtest.sh` | 1092 | 100 | **91%** |
| `generate_daily_signals.sh` | 596 | 98 | **84%** |
| **总计** | **1688** | **198** | **88%** |

### 新增工具类

```python
# backtest_runner/utils/argparse_utils.py

class UnderscoreHyphenArgumentParser(argparse.ArgumentParser):
    """
    自定义 ArgumentParser，支持下划线和连字符两种参数格式。

    例如: --enable-hysteresis 和 --enable_hysteresis 都被接受，
    内部统一转换为连字符格式处理。
    """

    def parse_args(self, args=None, namespace=None):
        """解析参数前，将下划线转换为连字符"""
        if args is None:
            args = sys.argv[1:]

        normalized_args = []
        for arg in args:
            if arg.startswith('--') and '_' in arg:
                if '=' in arg:
                    param, value = arg.split('=', 1)
                    normalized_args.append(param.replace('_', '-') + '=' + value)
                else:
                    normalized_args.append(arg.replace('_', '-'))
            else:
                normalized_args.append(arg)

        return super().parse_args(normalized_args, namespace)
```

### 简化后的 Shell 脚本结构

```bash
#!/bin/bash
# 简化版脚本结构（约 100 行）

set -e

# Conda 配置
CONDA_PATH="/home/zijunliu/miniforge3/condabin/conda"
CONDA_ENV="backtesting"
PYTHON_SCRIPT="$PROJECT_ROOT/backtest_runner.py"

# 环境检查函数
check_environment() {
    # 检查 conda、环境、脚本是否存在
}

# 主函数
main() {
    check_environment

    # 显示启动信息（非 --help 时）

    # 直接透传所有参数给 Python 脚本
    "$CONDA_PATH" run -n "$CONDA_ENV" python "$PYTHON_SCRIPT" "$@"

    # 显示完成信息
}

main "$@"
```

## 测试验证

### run_backtest.sh 测试结果

| 测试场景 | 结果 |
|---------|------|
| 帮助文档显示 | ✅ PASS |
| 基础回测（单只 ETF） | ✅ PASS |
| 带过滤器回测 | ✅ PASS |
| KAMA 策略特有参数 | ✅ PASS |
| 下划线参数格式 | ✅ PASS |
| 股票列表文件输入 | ✅ PASS |
| 错误处理 | ✅ PASS |

### generate_daily_signals.sh 测试结果

| 测试场景 | 结果 |
|---------|------|
| 帮助文档显示 | ✅ PASS |
| 初始化持仓 | ✅ PASS |
| 查看持仓状态 | ✅ PASS |
| 分析模式 | ✅ PASS |
| 下划线参数格式 | ✅ PASS |
| 列出快照 | ✅ PASS |
| 错误处理 | ✅ PASS |

## 使用方式

### 向后兼容

所有原有命令行用法完全保持兼容：

```bash
# 回测示例
./run_backtest.sh --stock-list results/trend_etf_pool.csv -t kama_cross \
    --enable-loss-protection --data-dir data/chinese_etf/daily

# 信号生成示例
./generate_daily_signals.sh --analyze \
    --stock-list results/trend_etf_pool.csv \
    --portfolio-file positions/portfolio.json \
    --data-dir data/chinese_etf/daily
```

### 下划线格式支持

现在支持下划线和连字符两种格式（以下等价）：

```bash
# 连字符格式
./run_backtest.sh --enable-hysteresis --hysteresis-mode std

# 下划线格式
./run_backtest.sh --enable_hysteresis --hysteresis_mode std

# 混合格式
./run_backtest.sh --enable-hysteresis --hysteresis_mode std
```

## 备份与回滚

原始脚本已备份：

```
run_backtest.sh.bak           # 原始 1092 行版本
generate_daily_signals.sh.bak # 原始 596 行版本
```

如需回滚：

```bash
cp run_backtest.sh.bak run_backtest.sh
cp generate_daily_signals.sh.bak generate_daily_signals.sh
```

运行一段时间确认无问题后，可删除备份文件：

```bash
rm run_backtest.sh.bak generate_daily_signals.sh.bak
```

## 收益总结

1. **代码量减少 88%**：从 1688 行降至 198 行
2. **维护成本降低**：新增参数只需修改 Python 端
3. **参数格式统一**：自动支持下划线和连字符
4. **帮助文档自动生成**：无需手动维护
5. **类型检查更完善**：Python argparse 提供更好的参数验证
