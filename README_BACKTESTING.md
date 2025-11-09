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
./run_backtest.sh  --stock-list results/trend_etf_pool.csv --strategy sma_cross --optimize --data-dir data/chinese_etf/daily --save-params config/strategy_params.json

## # Day 0: 初始化持仓
./generate_daily_signals.sh --init 100000 --portfolio-file positions/etf_portfolio.json

## 根据超参获取今天信号
./generate_daily_signals.sh --analyze --stock-list results/trend_etf_pool.csv --portfolio-file positions/etf_portfolio.json

