"""
基金数据抓取器

处理基金基本信息、净值、分红、规模数据的获取
"""

import time
import pandas as pd
from tqdm import tqdm
from .base_fetcher import BaseFetcher
from .rate_limiter import RateLimiter
from .data_processor import DataProcessor


class FundFetcher(BaseFetcher):
    """基金数据抓取器"""

    def __init__(self, pro_api, db_manager, rate_limiter: RateLimiter,
                 data_processor: DataProcessor, logger=None):
        """
        初始化基金抓取器

        Args:
            pro_api: Tushare Pro API实例
            db_manager: 数据库管理器
            rate_limiter: 频率限制器
            data_processor: 数据处理器
            logger: 日志记录器
        """
        super().__init__(pro_api, db_manager, logger)
        self.rate_limiter = rate_limiter
        self.data_processor = data_processor

    def fetch_basic_info(self) -> int:
        """
        获取公募基金基本信息（仅白名单内基金公司）

        Returns:
            int: 成功获取的基金数量
        """
        try:
            self.logger.info("开始获取公募基金基本信息（仅白名单内基金公司）")

            # 获取场外基金（公募基金）
            df = self.pro.fund_basic(market='O', status='L')

            if df.empty:
                self.logger.warning("未获取到公募基金基本信息")
                return 0

            # 应用白名单过滤
            original_count = len(df)
            df = df[df['management'].apply(
                lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False
            )]
            filtered_count = len(df)

            self.logger.info(f"基金白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")

            if df.empty:
                self.logger.warning("白名单过滤后无公募基金数据")
                return 0

            success_count = 0
            # 添加进度条显示
            progress_bar = tqdm(df.iterrows(), total=len(df), desc="获取基金基本信息", unit="条")

            for _, row in progress_bar:
                try:
                    # 映射字段
                    data = {
                        'symbol': row.get('ts_code', '').split('.')[0] if row.get('ts_code') else None,
                        'market': 'O',  # 场外
                        'fullname': row.get('name'),
                        'management': row.get('management'),
                        'custodian': row.get('custodian'),
                        'fund_type': row.get('fund_type'),
                        'invest_type': row.get('invest_type'),
                        'found_date': row.get('found_date'),
                        'due_date': row.get('due_date'),
                        'm_fee': row.get('m_fee'),
                        'c_fee': row.get('c_fee'),
                        'min_amount': row.get('min_amount'),
                        'benchmark': row.get('benchmark'),
                        'status': row.get('status', 'L')
                    }

                    # 过滤None值和NaN值
                    data = self._clean_data(data)

                    success = self.db_manager.add_instrument_basic(
                        data_type='fund',
                        ts_code=row['ts_code'],
                        name=row['name'],
                        **data
                    )

                    if success:
                        success_count += 1

                    # 更新进度条显示成功数量
                    progress_bar.set_postfix({"成功": success_count})

                except Exception as e:
                    self.logger.error(f"添加基金基本信息失败 {row.get('ts_code', 'unknown')}: {e}")
                    continue

            progress_bar.close()
            self.logger.info(f"公募基金基本信息获取完成，成功{success_count}条（白名单内）")
            return success_count

        except Exception as e:
            self.logger.error(f"获取公募基金基本信息失败: {e}")
            return 0

    def fetch_nav_by_date(self, nav_date: str, max_retries: int = 3) -> int:
        """
        获取指定日期的基金净值数据（仅白名单内基金公司）

        Args:
            nav_date: 净值日期(YYYYMMDD)
            max_retries: 最大重试次数

        Returns:
            int: 成功获取的数据条数
        """
        for retry in range(max_retries):
            try:
                self.logger.info(f"获取基金净值数据: {nav_date} (第{retry+1}次尝试)")

                df = self.pro.fund_nav(nav_date=nav_date)

                if df.empty:
                    self.logger.warning(f"未获取到{nav_date}的基金净值数据")
                    return 0

                success_count = 0
                whitelisted_count = 0
                # 添加进度条
                progress_bar = tqdm(df.iterrows(), total=len(df),
                                  desc=f"基金净值[{nav_date}]", unit="条", leave=False)

                for _, row in progress_bar:
                    try:
                        # 检查基金是否在白名单内
                        ts_code = row['ts_code']
                        management = self._get_fund_management_from_db(ts_code)

                        if not self._is_whitelisted_fund_company(management):
                            continue  # 跳过非白名单基金

                        whitelisted_count += 1

                        # 映射字段
                        data = {
                            'unit_nav': row.get('unit_nav'),
                            'accum_nav': row.get('accum_nav'),
                            'adj_nav': row.get('adj_nav'),
                            'accum_div': row.get('accum_div'),
                            'net_asset': row.get('net_asset'),
                            'total_netasset': row.get('total_netasset'),
                            'ann_date': row.get('ann_date')
                        }

                        # 过滤None值和NaN值
                        data = self._clean_data(data)

                        success = self.db_manager.add_instrument_daily(
                            data_type='fund',
                            ts_code=ts_code,
                            trade_date=row['nav_date'],
                            **data
                        )

                        if success:
                            success_count += 1

                        # 更新进度条显示
                        progress_bar.set_postfix({"白名单": whitelisted_count, "成功": success_count})

                    except Exception as e:
                        self.logger.error(f"添加基金净值数据失败 {row.get('ts_code', 'unknown')}: {e}")
                        continue

                progress_bar.close()
                self.logger.info(f"基金净值数据获取完成 {nav_date}，白名单内{whitelisted_count}只，成功{success_count}条")
                return success_count

            except Exception as e:
                self.logger.error(f"获取基金净值数据失败 {nav_date} (第{retry+1}次): {e}")
                if retry < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return 0

        return 0

    def fetch_nav_by_instrument(self, start_date: str, end_date: str) -> int:
        """
        按基金工具遍历获取净值数据（无需数据分割，仅白名单内基金公司）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            int: 成功获取的数据条数
        """
        try:
            # 获取公募基金基本信息列表
            df_basic = self.pro.fund_basic(market='O', status='L')
            if df_basic.empty:
                self.logger.warning("未获取到基金基本信息")
                return 0

            # 应用白名单过滤
            original_count = len(df_basic)
            df_basic = df_basic[df_basic['management'].apply(
                lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False
            )]
            filtered_count = len(df_basic)

            self.logger.info(f"按工具获取基金净值 - 白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")

            if df_basic.empty:
                self.logger.warning("白名单过滤后无基金数据")
                return 0

            success_count = 0
            all_data = []
            fund_count = len(df_basic)

            # 创建进度条
            progress_bar = tqdm(total=fund_count, desc="按基金获取净值数据", unit="个基金")

            for _, fund_info in df_basic.iterrows():
                ts_code = fund_info['ts_code']

                try:
                    # 直接获取该基金的全周期净值数据
                    df = self.pro.fund_nav(ts_code=ts_code)

                    if not df.empty:
                        # 按日期范围过滤数据
                        df = df[(df['nav_date'] >= start_date) & (df['nav_date'] <= end_date)]

                        # 批量处理数据
                        for _, row in df.iterrows():
                            data = {
                                'data_type': 'fund',
                                'ts_code': row['ts_code'],
                                'trade_date': row['nav_date'],
                                'unit_nav': row.get('unit_nav'),
                                'accum_nav': row.get('accum_nav'),
                                'adj_nav': row.get('adj_nav'),
                                'accum_div': row.get('accum_div'),
                                'net_asset': row.get('net_asset'),
                                'total_netasset': row.get('total_netasset'),
                                'ann_date': row.get('ann_date')
                            }
                            data = self._clean_data(data)
                            all_data.append(data)

                    # 批量插入
                    if len(all_data) >= self.data_processor.batch_size:
                        batch_success = self.db_manager.batch_insert_instrument_daily(
                            all_data, batch_size=self.data_processor.batch_size
                        )
                        success_count += batch_success
                        all_data = []

                    time.sleep(0.001)

                except Exception as e:
                    self.logger.error(f"获取基金净值失败 {ts_code}: {e}")

                finally:
                    progress_bar.update(1)
                    progress_bar.set_postfix({
                        "基金": ts_code,
                        "成功": success_count
                    })

            # 插入剩余数据
            if all_data:
                batch_success = self.db_manager.batch_insert_instrument_daily(
                    all_data, batch_size=self.data_processor.batch_size
                )
                success_count += batch_success

            progress_bar.close()
            self.logger.info(f"按基金遍历获取净值数据完成: {success_count}条（白名单内）")
            return success_count

        except Exception as e:
            self.logger.error(f"按基金遍历获取净值数据失败: {e}")
            return 0

    def fetch_dividend_data(self, start_date: str, end_date: str) -> int:
        """
        获取基金分红数据（按基金代码循环获取）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            int: 成功获取的记录数
        """
        total_count = 0

        # 从Tushare API获取基金列表
        try:
            self.logger.info("从Tushare API获取公募基金列表")
            df_funds = self.pro.fund_basic(market='O', status='L')  # 场外基金，存续状态

            if df_funds.empty:
                self.logger.warning("从Tushare API未获取到基金列表")
                return 0

            self.logger.info(f"从API获取到{len(df_funds)}只基金")

            # 应用白名单过滤
            original_count = len(df_funds)
            df_funds = df_funds[df_funds['management'].apply(
                lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False
            )]
            filtered_count = len(df_funds)

            self.logger.info(f"基金白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")

            if df_funds.empty:
                self.logger.warning("白名单过滤后无基金数据")
                return 0

        except Exception as e:
            self.logger.error(f"获取基金列表失败: {e}")
            return 0

        self.logger.info(f"开始遍历{len(df_funds)}个白名单基金获取分红数据")

        # 添加频率控制参数
        max_requests_per_minute = 300  # 设置为300，留出安全余量
        request_count = 0
        start_time = time.time()
        processed_count = 0

        # 为每个基金获取分红数据
        progress_bar = tqdm(df_funds.iterrows(), total=len(df_funds), desc="获取基金分红数据", unit="个基金")

        for _, fund_info in progress_bar:
            ts_code = fund_info['ts_code']
            fund_name = fund_info['name']
            processed_count += 1

            try:
                # 调用Tushare API前检查频率
                if request_count >= max_requests_per_minute:
                    # 计算已用时间
                    elapsed_time = time.time() - start_time
                    if elapsed_time < 60:  # 如果还没到1分钟
                        sleep_time = 60 - elapsed_time + 5  # 多等5秒作为缓冲
                        remaining_funds = len(df_funds) - processed_count + 1
                        estimated_minutes = remaining_funds / max_requests_per_minute

                        self.logger.info(f"【频率控制】已处理 {processed_count-1}/{len(df_funds)} 个基金")
                        self.logger.info(f"【频率控制】当前分钟已请求 {request_count} 次，休息 {sleep_time:.1f} 秒")
                        self.logger.info(f"【频率控制】预计还需 {estimated_minutes:.1f} 分钟完成剩余 {remaining_funds} 个基金")

                        time.sleep(sleep_time)

                    # 重置计数器和时间
                    request_count = 0
                    start_time = time.time()

                # 调用Tushare API获取该基金的分红数据
                df = self.pro.fund_div(ts_code=ts_code)
                request_count += 1

                if df is not None and not df.empty:
                    # 按日期范围过滤数据
                    df = df[(df['ex_date'] >= start_date) & (df['ex_date'] <= end_date)]

                    if not df.empty:
                        # 转换为记录列表
                        dividend_records = []
                        for _, row in df.iterrows():
                            dividend_record = row.to_dict()
                            dividend_records.append(dividend_record)

                        # 批量保存到数据库
                        if dividend_records:
                            success_count = self.db_manager.insert_fund_dividend_data(dividend_records)
                            total_count += success_count

                            self.logger.info(f"基金 {ts_code} ({fund_name}): 获取{len(dividend_records)}条分红记录，成功保存{success_count}条")

                        # 更新进度条显示
                        progress_bar.set_postfix({
                            "基金": ts_code,
                            "请求数": request_count,
                            "本次": len(dividend_records),
                            "总计": total_count
                        })
                    else:
                        # 更新进度条显示（无分红记录的情况）
                        progress_bar.set_postfix({
                            "基金": ts_code,
                            "请求数": request_count,
                            "本次": 0,
                            "总计": total_count
                        })
                        self.logger.debug(f"基金 {ts_code} ({fund_name}): 指定日期范围内无分红记录")
                else:
                    # 更新进度条显示（无数据的情况）
                    progress_bar.set_postfix({
                        "基金": ts_code,
                        "请求数": request_count,
                        "本次": 0,
                        "总计": total_count
                    })
                    self.logger.debug(f"基金 {ts_code} ({fund_name}): 无分红数据")

            except Exception as e:
                self.logger.error(f"获取基金 {ts_code} ({fund_name}) 分红数据失败: {e}")
                # 如果是频率限制错误，也要计入请求次数
                if "每分钟最多访问" in str(e):
                    request_count += 1
                continue

        progress_bar.close()
        self.logger.info(f"基金分红数据获取完成，总共成功保存 {total_count} 条记录")
        return total_count

    def fetch_share_by_instrument_chunked(self, start_date: str, end_date: str) -> int:
        """
        按基金工具遍历获取规模数据（支持数据分块）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            int: 成功获取的数据条数
        """
        try:
            # 获取公募基金基本信息列表
            df_basic = self.pro.fund_basic(market='E', status='L')  # 场内基金，支持fund_share接口
            if df_basic.empty:
                self.logger.warning("未获取到基金基本信息")
                return 0

            # 应用白名单过滤
            original_count = len(df_basic)
            df_basic = df_basic[df_basic['management'].apply(
                lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False
            )]
            filtered_count = len(df_basic)

            self.logger.info(f"按工具获取基金规模 - 白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")

            if df_basic.empty:
                self.logger.warning("白名单过滤后无基金数据")
                return 0

            # 计算日期分割块
            trading_dates = self.get_trading_calendar(start_date, end_date)
            date_chunks = self.data_processor.calculate_chunks(trading_dates, max_records=2000)
            if not date_chunks:
                self.logger.error("无法计算日期分割块")
                return 0

            self.logger.info(f"基金规模数据分块策略: {len(date_chunks)}个时间块，每块最多2000条记录")

            success_count = 0
            all_data = []
            fund_count = len(df_basic)

            # 添加频率控制参数（fund_share接口限制每分钟400次）
            max_requests_per_minute = 300  # 设置为300，留出安全余量
            request_count = 0
            start_time = time.time()

            # 创建进度条
            progress_bar = tqdm(total=fund_count, desc="按基金获取规模数据（分块）", unit="个基金")

            for _, fund_info in df_basic.iterrows():
                ts_code = fund_info['ts_code']

                try:
                    # 调用API前检查频率
                    if request_count >= max_requests_per_minute:
                        elapsed_time = time.time() - start_time
                        if elapsed_time < 60:
                            sleep_time = 60 - elapsed_time + 5
                            self.logger.info(f"【频率控制】基金规模数据已请求 {request_count} 次，休息 {sleep_time:.1f} 秒")
                            time.sleep(sleep_time)
                        request_count = 0
                        start_time = time.time()

                    # 【分块获取】首先尝试按时间块获取数据
                    self.logger.debug(f"【分块】开始获取基金规模数据 {ts_code}")
                    df_list = []
                    chunk_requests = 0

                    for chunk_start, chunk_end in date_chunks:
                        # 频率控制检查（包括分块请求）
                        if request_count + chunk_requests >= max_requests_per_minute:
                            elapsed_time = time.time() - start_time
                            if elapsed_time < 60:
                                sleep_time = 60 - elapsed_time + 5
                                self.logger.info(f"【频率控制】分块过程中需要休息 {sleep_time:.1f} 秒")
                                time.sleep(sleep_time)
                            request_count = 0
                            start_time = time.time()
                            chunk_requests = 0

                        # 获取该基金在当前日期块的数据
                        chunk_df = self.pro.fund_share(
                            ts_code=ts_code,
                            start_date=chunk_start,
                            end_date=chunk_end
                        )
                        chunk_requests += 1
                        df_list.append(chunk_df)

                    request_count += chunk_requests

                    # 合并所有分块数据
                    if df_list:
                        df = self._safe_concat_dataframes(df_list)
                    else:
                        df = pd.DataFrame()

                    # 【回退机制】如果分块获取结果为空，尝试全周期获取
                    if df.empty:
                        self.logger.info(f"【回退】基金 {ts_code} 分块获取失败，尝试获取全周期数据")

                        # 频率控制检查（全周期请求）
                        if request_count >= max_requests_per_minute:
                            elapsed_time = time.time() - start_time
                            if elapsed_time < 60:
                                sleep_time = 60 - elapsed_time + 5
                                self.logger.info(f"【频率控制】回退过程中需要休息 {sleep_time:.1f} 秒")
                                time.sleep(sleep_time)
                            request_count = 0
                            start_time = time.time()

                        df = self.pro.fund_share(ts_code=ts_code)
                        request_count += 1

                        if df.empty:
                            self.logger.warning(f"【回退】基金 {ts_code} 全周期获取也失败，跳过")
                        else:
                            self.logger.info(f"【回退】基金 {ts_code} 全周期获取成功，数据量: {len(df)}")
                            # 按日期范围过滤数据
                            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
                    else:
                        self.logger.debug(f"【分块】基金 {ts_code} 分块获取成功，数据量: {len(df)}")

                    if not df.empty:
                        # 批量处理数据
                        for _, row in df.iterrows():
                            data = {
                                'data_type': 'fund_share',
                                'ts_code': row['ts_code'],
                                'trade_date': row['trade_date'],
                                'fd_share': row.get('fd_share')
                            }
                            data = self._clean_data(data)
                            all_data.append(data)

                    # 批量插入
                    if len(all_data) >= self.data_processor.batch_size:
                        batch_success = self.db_manager.batch_insert_fund_share_data(
                            all_data, batch_size=self.data_processor.batch_size
                        )
                        success_count += batch_success
                        all_data = []

                    time.sleep(0.2)  # 额外的保险延迟

                except Exception as e:
                    self.logger.error(f"获取基金规模失败 {ts_code}: {e}")

                finally:
                    progress_bar.update(1)
                    progress_bar.set_postfix({
                        "基金": ts_code,
                        "成功": success_count,
                        "请求数": request_count
                    })

            # 插入剩余数据
            if all_data:
                batch_success = self.db_manager.batch_insert_fund_share_data(
                    all_data, batch_size=self.data_processor.batch_size
                )
                success_count += batch_success

            progress_bar.close()
            self.logger.info(f"按基金遍历获取规模数据完成: {success_count}条（白名单内，支持分块）")
            return success_count

        except Exception as e:
            self.logger.error(f"按基金遍历获取规模数据失败: {e}")
            return 0

    def fetch_share_by_date(self, start_date: str, end_date: str) -> int:
        """
        按日期遍历获取基金规模数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            int: 成功获取的数据条数
        """
        trading_dates = self.get_trading_calendar(start_date, end_date)
        if not trading_dates:
            return 0

        total_count = 0
        date_progress = tqdm(trading_dates, desc="按日期获取基金规模", unit="天")

        for trade_date in date_progress:
            share_count = self._fetch_share_single_date(trade_date)
            total_count += share_count
            date_progress.set_postfix({"总计": total_count})
            time.sleep(0.2)

        date_progress.close()
        return total_count

    def _fetch_share_single_date(self, trade_date: str) -> int:
        """
        获取单个日期的基金规模数据

        Args:
            trade_date: 交易日期(YYYYMMDD)

        Returns:
            int: 成功获取的数据条数
        """
        try:
            df = self.pro.fund_share(trade_date=trade_date)

            if df.empty:
                self.logger.debug(f"未获取到 {trade_date} 的基金规模数据")
                return 0

            # 应用白名单过滤
            original_count = len(df)

            # 获取基金管理公司信息用于过滤
            filtered_data = []
            for _, row in df.iterrows():
                ts_code = row['ts_code']
                management = self._get_fund_management_from_db(ts_code)

                if management and self._is_whitelisted_fund_company(management):
                    data = {
                        'data_type': 'fund_share',
                        'ts_code': row['ts_code'],
                        'trade_date': row['trade_date'],
                        'fd_share': row.get('fd_share')
                    }
                    data = self._clean_data(data)
                    filtered_data.append(data)

            if filtered_data:
                success_count = self.db_manager.batch_insert_fund_share_data(
                    filtered_data, batch_size=self.data_processor.batch_size
                )
                self.logger.debug(f"{trade_date}: 获取{original_count}条 -> 白名单过滤{len(filtered_data)}条 -> 成功{success_count}条")
                return success_count
            else:
                self.logger.debug(f"{trade_date}: 白名单过滤后无数据")
                return 0

        except Exception as e:
            self.logger.error(f"获取{trade_date}基金规模数据失败: {e}")
            return 0

    def get_count(self) -> int:
        """
        获取基金数量（白名单内）

        Returns:
            int: 基金数量
        """
        try:
            df = self.pro.fund_basic(market='O', status='L')
            if df.empty:
                return 0

            # 应用白名单过滤
            df = df[df['management'].apply(
                lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False
            )]

            return len(df)

        except Exception as e:
            self.logger.error(f"获取基金数量失败: {e}")
            return 0
