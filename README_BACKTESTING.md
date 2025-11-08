## ETF标的预筛选
python -m etf_selector.main --output results/trend_etf_pool.csv --target-size 10 --min-turnover 100000 --min-volatility 0.15 --max-volatility 0.80 --adx-percentile 70 --ret-dd-percentile 70 --momentum-min-positive

## 根据筛选标的回测得出最佳超参
./run_backtest.sh  --stock-list results/trend_etf_pool.csv --strategy sma_cross --optimize --data-dir data/csv/daily --save-params config/strategy_params.json

## # Day 0: 初始化持仓
./generate_daily_signals.sh --init 100000 --portfolio-file positions/portfolio.json

## 根据超参获取今天信号
./generate_daily_signals.sh --analyze --stock-list results/trend_etf_pool.csv --portfolio-file positions/portfolio.json

