## 获取最新日期的ETF、基金日线
python scripts/fetch_tushare_data_v2.py --start_date 20251107 --end_date 20251107 --daily_data --basic_info --data_type etf
python scripts/fetch_tushare_data_v2.py --start_date 20251107 --end_date 20251107 --daily_data --basic_info --data_type fund

## 获取基金全周期分红信息
python scripts/fetch_tushare_data_v2.py --fetch_dividend --data_type fund

## 输出最新etf日线到目录（最近两年）
python scripts/export_mysql_to_csv.py --start_date 20231107 --end_date 20251107 --data_type etf --output_dir data/chinese_etf --export_daily --export_basic

## ETF标的预筛选
python -m etf_selector.main --data-dir data/chinese_etf --output results/trend_etf_pool.csv --target-size 20 --min-turnover 100000 --min-volatility 0.15 --max-volatility 0.80 --adx-percentile 70 --momentum-min-positive

## 根据筛选标的回测得出最佳超参
### 策略1：双均线+止损
./run_backtest.sh  --stock-list results/trend_etf_pool.csv --strategy sma_cross_enhanced --optimize --data-dir data/chinese_etf/daily --save-params config/sma_strategy_params.json --output-dir results/exp_sma_enable_loss_protect --enable-loss-protection

### 策略2：MACD交叉策略 + 止损
./run_backtest.sh --stock-list results/trend_etf_pool.csv --strategy macd_cross --optimize --data-dir data/chinese_etf/daily --save-params config/macd_strategy_params.json --enable-loss-protection --output-dir results/exp_macd_enable_loss_protect

## # Day 0: 初始化持仓
./generate_daily_signals.sh --init 100000 --portfolio-file positions/etf_sma_cross_portfolio.json
./generate_daily_signals.sh --init 100000 --portfolio-file positions/etf_macd_cross_portfolio.json

## 根据超参获取今天信号
./generate_daily_signals.sh --analyze --strategy sma_cross_enhanced --stock-list results/trend_etf_pool.csv --portfolio-file positions/etf_sma_cross_portfolio.json --load-params config/sma_strategy_params.json --data-dir data/chinese_etf/daily
./generate_daily_signals.sh --analyze --strategy macd_cross --stock-list results/trend_etf_pool.csv --portfolio-file positions/etf_macd_cross_portfolio.json --load-params config/macd_strategy_params.json --data-dir data/chinese_etf/daily

