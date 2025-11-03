"""
MySQL数据库管理类
支持股票、基金、ETF数据的增删查改操作
"""

import logging
import pymysql
import pandas as pd
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, date
import json
from contextlib import contextmanager


class MySQLManager:
    """
    MySQL数据库操作管理类
    
    支持股票、基金、ETF数据的增删查改操作，提供连接池管理、事务支持和异常处理
    """
    
    def __init__(
        self, 
        host: str = "localhost",
        user: str = "root", 
        password: str = "qlib_data",
        database: str = "qlib_data",
        port: int = 3306,
        charset: str = "utf8mb4"
    ):
        """
        初始化MySQL连接管理器
        
        Args:
            host: 数据库主机地址
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
            port: 数据库端口
            charset: 字符编码
        """
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.charset = charset
        self.logger = logging.getLogger(__name__)
        
        # 初始化连接配置
        self.connection_config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
            'port': port,
            'charset': charset,
            'autocommit': False,
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        # 初始化数据库和表
        self._init_database()
    
    def _get_connection(self) -> pymysql.Connection:
        """
        获取数据库连接
        
        Returns:
            pymysql.Connection: 数据库连接对象
            
        Raises:
            Exception: 连接数据库失败时抛出异常
        """
        try:
            connection = pymysql.connect(**self.connection_config)
            return connection
        except Exception as e:
            self.logger.error(f"连接数据库失败: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        上下文管理器，自动管理数据库连接的生命周期
        
        Yields:
            pymysql.Connection: 数据库连接对象
        """
        connection = None
        try:
            connection = self._get_connection()
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            self.logger.error(f"数据库操作异常: {e}")
            raise
        finally:
            if connection:
                connection.close()
    
    def _init_database(self):
        """
        初始化数据库和表结构
        
        创建必要的数据表，包括股票、基金、ETF数据表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 创建股票数据表
                self._create_stock_table(cursor)
                
                # 创建基金数据表
                self._create_fund_table(cursor)
                
                # 创建ETF数据表
                self._create_etf_table(cursor)
                
                # 创建通用市场数据表（用于存储价格、成交量等时序数据）
                self._create_market_data_table(cursor)
                
                # 创建统一基本信息表（ETF、指数、基金）
                self._create_instrument_basic_table(cursor)
                
                # 创建统一行情数据表（ETF、指数、基金）
                self._create_instrument_daily_table(cursor)
                
                # 创建基金分红数据表
                self._create_fund_dividend_table(cursor)
                
                # 创建基金规模数据表
                self._create_fund_share_table(cursor)
                
                conn.commit()
                self.logger.info("数据库表结构初始化完成")
                
        except Exception as e:
            self.logger.error(f"初始化数据库失败: {e}")
            raise
    
    def _create_stock_table(self, cursor):
        """创建股票基本信息表"""
        sql = """
        CREATE TABLE IF NOT EXISTS stock_info (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(20) NOT NULL COMMENT '股票代码',
            name VARCHAR(100) NOT NULL COMMENT '股票名称',
            market VARCHAR(20) DEFAULT NULL COMMENT '交易市场(SH/SZ)',
            industry VARCHAR(50) DEFAULT NULL COMMENT '所属行业',
            status VARCHAR(20) DEFAULT 'active' COMMENT '状态(active/delisted)',
            list_date DATE DEFAULT NULL COMMENT '上市日期',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_code (code),
            INDEX idx_market (market),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基本信息表'
        """
        cursor.execute(sql)
    
    def _create_fund_table(self, cursor):
        """创建基金基本信息表"""
        sql = """
        CREATE TABLE IF NOT EXISTS fund_info (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(20) NOT NULL COMMENT '基金代码',
            name VARCHAR(100) NOT NULL COMMENT '基金名称',
            fund_type VARCHAR(50) DEFAULT NULL COMMENT '基金类型',
            manager VARCHAR(100) DEFAULT NULL COMMENT '基金管理人',
            status VARCHAR(20) DEFAULT 'active' COMMENT '状态(active/inactive)',
            establish_date DATE DEFAULT NULL COMMENT '成立日期',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_code (code),
            INDEX idx_fund_type (fund_type),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金基本信息表'
        """
        cursor.execute(sql)
    
    def _create_etf_table(self, cursor):
        """创建ETF基本信息表"""
        sql = """
        CREATE TABLE IF NOT EXISTS etf_info (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(20) NOT NULL COMMENT 'ETF代码',
            name VARCHAR(100) NOT NULL COMMENT 'ETF名称',
            tracking_index VARCHAR(100) DEFAULT NULL COMMENT '跟踪指数',
            manager VARCHAR(100) DEFAULT NULL COMMENT '基金管理人',
            status VARCHAR(20) DEFAULT 'active' COMMENT '状态(active/inactive)',
            list_date DATE DEFAULT NULL COMMENT '上市日期',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_code (code),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ETF基本信息表'
        """
        cursor.execute(sql)
    
    def _create_market_data_table(self, cursor):
        """创建市场数据表（存储价格、成交量等时序数据）"""
        sql = """
        CREATE TABLE IF NOT EXISTS market_data (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            instrument_code VARCHAR(20) NOT NULL COMMENT '证券代码',
            instrument_type VARCHAR(20) NOT NULL COMMENT '证券类型(stock/fund/etf)',
            trade_date DATE NOT NULL COMMENT '交易日期',
            open_price DECIMAL(12,4) DEFAULT NULL COMMENT '开盘价',
            high_price DECIMAL(12,4) DEFAULT NULL COMMENT '最高价',
            low_price DECIMAL(12,4) DEFAULT NULL COMMENT '最低价',
            close_price DECIMAL(12,4) DEFAULT NULL COMMENT '收盘价',
            volume BIGINT DEFAULT NULL COMMENT '成交量',
            amount DECIMAL(15,2) DEFAULT NULL COMMENT '成交金额',
            pct_change DECIMAL(8,4) DEFAULT NULL COMMENT '涨跌幅',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_instrument_date (instrument_code, trade_date),
            INDEX idx_instrument_type (instrument_type),
            INDEX idx_trade_date (trade_date),
            INDEX idx_instrument_code (instrument_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='市场数据表'
        """
        cursor.execute(sql)
    
    def add_stock_info(self, code: str, name: str, market: str = None, 
                      industry: str = None, list_date: date = None) -> bool:
        """
        添加股票基本信息
        
        Args:
            code: 股票代码
            name: 股票名称
            market: 交易市场
            industry: 所属行业
            list_date: 上市日期
            
        Returns:
            bool: 添加成功返回True，否则返回False
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = """
                INSERT INTO stock_info (code, name, market, industry, list_date)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (code, name, market, industry, list_date))
                conn.commit()
                # self.logger.info(f"成功添加股票信息: {code} - {name}")
                return True
        except Exception as e:
            self.logger.error(f"添加股票信息失败 {code}: {e}")
            return False
    
    def add_fund_info(self, code: str, name: str, fund_type: str = None,
                     manager: str = None, establish_date: date = None) -> bool:
        """
        添加基金基本信息
        
        Args:
            code: 基金代码
            name: 基金名称
            fund_type: 基金类型
            manager: 基金管理人
            establish_date: 成立日期
            
        Returns:
            bool: 添加成功返回True，否则返回False
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = """
                INSERT INTO fund_info (code, name, fund_type, manager, establish_date)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (code, name, fund_type, manager, establish_date))
                conn.commit()
                # self.logger.info(f"成功添加基金信息: {code} - {name}")
                return True
        except Exception as e:
            self.logger.error(f"添加基金信息失败 {code}: {e}")
            return False
    
    def add_etf_info(self, code: str, name: str, tracking_index: str = None,
                    manager: str = None, list_date: date = None) -> bool:
        """
        添加ETF基本信息
        
        Args:
            code: ETF代码
            name: ETF名称
            tracking_index: 跟踪指数
            manager: 基金管理人
            list_date: 上市日期
            
        Returns:
            bool: 添加成功返回True，否则返回False
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = """
                INSERT INTO etf_info (code, name, tracking_index, manager, list_date)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (code, name, tracking_index, manager, list_date))
                conn.commit()
                # self.logger.info(f"成功添加ETF信息: {code} - {name}")
                return True
        except Exception as e:
            self.logger.error(f"添加ETF信息失败 {code}: {e}")
            return False
    
    def add_market_data(self, instrument_code: str, instrument_type: str,
                       trade_date: date, open_price: float = None,
                       high_price: float = None, low_price: float = None,
                       close_price: float = None, volume: int = None,
                       amount: float = None, pct_change: float = None) -> bool:
        """
        添加市场数据
        
        Args:
            instrument_code: 证券代码
            instrument_type: 证券类型(stock/fund/etf)
            trade_date: 交易日期
            open_price: 开盘价
            high_price: 最高价
            low_price: 最低价
            close_price: 收盘价
            volume: 成交量
            amount: 成交金额
            pct_change: 涨跌幅
            
        Returns:
            bool: 添加成功返回True，否则返回False
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = """
                INSERT INTO market_data (instrument_code, instrument_type, trade_date,
                                       open_price, high_price, low_price, close_price,
                                       volume, amount, pct_change)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    open_price = VALUES(open_price),
                    high_price = VALUES(high_price),
                    low_price = VALUES(low_price),
                    close_price = VALUES(close_price),
                    volume = VALUES(volume),
                    amount = VALUES(amount),
                    pct_change = VALUES(pct_change),
                    updated_at = CURRENT_TIMESTAMP
                """
                cursor.execute(sql, (instrument_code, instrument_type, trade_date,
                                   open_price, high_price, low_price, close_price,
                                   volume, amount, pct_change))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"添加市场数据失败 {instrument_code} {trade_date}: {e}")
            return False
    
    def get_stock_info(self, code: str = None, market: str = None) -> List[Dict]:
        """
        查询股票基本信息
        
        Args:
            code: 股票代码，为空时查询所有
            market: 交易市场过滤
            
        Returns:
            List[Dict]: 股票信息列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM stock_info WHERE 1=1"
                params = []
                
                if code:
                    sql += " AND code = %s"
                    params.append(code)
                    
                if market:
                    sql += " AND market = %s"
                    params.append(market)
                
                sql += " ORDER BY code"
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"查询股票信息失败: {e}")
            return []
    
    def get_fund_info(self, code: str = None, fund_type: str = None) -> List[Dict]:
        """
        查询基金基本信息
        
        Args:
            code: 基金代码，为空时查询所有
            fund_type: 基金类型过滤
            
        Returns:
            List[Dict]: 基金信息列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM fund_info WHERE 1=1"
                params = []
                
                if code:
                    sql += " AND code = %s"
                    params.append(code)
                    
                if fund_type:
                    sql += " AND fund_type = %s"
                    params.append(fund_type)
                
                sql += " ORDER BY code"
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"查询基金信息失败: {e}")
            return []
    
    def get_etf_info(self, code: str = None) -> List[Dict]:
        """
        查询ETF基本信息
        
        Args:
            code: ETF代码，为空时查询所有
            
        Returns:
            List[Dict]: ETF信息列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM etf_info WHERE 1=1"
                params = []
                
                if code:
                    sql += " AND code = %s"
                    params.append(code)
                
                sql += " ORDER BY code"
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"查询ETF信息失败: {e}")
            return []
    
    def get_market_data(self, instrument_code: str, instrument_type: str = None,
                       start_date: date = None, end_date: date = None) -> List[Dict]:
        """
        查询市场数据
        
        Args:
            instrument_code: 证券代码
            instrument_type: 证券类型过滤
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[Dict]: 市场数据列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM market_data WHERE instrument_code = %s"
                params = [instrument_code]
                
                if instrument_type:
                    sql += " AND instrument_type = %s"
                    params.append(instrument_type)
                    
                if start_date:
                    sql += " AND trade_date >= %s"
                    params.append(start_date)
                    
                if end_date:
                    sql += " AND trade_date <= %s"
                    params.append(end_date)
                
                sql += " ORDER BY trade_date"
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"查询市场数据失败: {e}")
            return []
    
    def update_stock_info(self, code: str, **kwargs) -> bool:
        """
        更新股票基本信息
        
        Args:
            code: 股票代码
            **kwargs: 要更新的字段和值
            
        Returns:
            bool: 更新成功返回True，否则返回False
        """
        if not kwargs:
            return False
            
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建更新SQL
                fields = []
                values = []
                for field, value in kwargs.items():
                    if field in ['name', 'market', 'industry', 'status', 'list_date']:
                        fields.append(f"{field} = %s")
                        values.append(value)
                
                if not fields:
                    return False
                
                sql = f"UPDATE stock_info SET {', '.join(fields)} WHERE code = %s"
                values.append(code)
                
                cursor.execute(sql, values)
                conn.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(f"成功更新股票信息: {code}")
                    return True
                else:
                    self.logger.warning(f"未找到股票代码: {code}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"更新股票信息失败 {code}: {e}")
            return False
    
    def delete_stock_info(self, code: str) -> bool:
        """
        删除股票基本信息
        
        Args:
            code: 股票代码
            
        Returns:
            bool: 删除成功返回True，否则返回False
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = "DELETE FROM stock_info WHERE code = %s"
                cursor.execute(sql, (code,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(f"成功删除股票信息: {code}")
                    return True
                else:
                    self.logger.warning(f"未找到股票代码: {code}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"删除股票信息失败 {code}: {e}")
            return False
    
    def batch_insert_market_data(self, data_list: List[Dict]) -> int:
        """
        批量插入市场数据
        
        Args:
            data_list: 市场数据列表，每个元素为包含市场数据字段的字典
            
        Returns:
            int: 成功插入的数据条数
        """
        if not data_list:
            return 0
            
        success_count = 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = """
                INSERT INTO market_data (instrument_code, instrument_type, trade_date,
                                       open_price, high_price, low_price, close_price,
                                       volume, amount, pct_change)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    open_price = VALUES(open_price),
                    high_price = VALUES(high_price),
                    low_price = VALUES(low_price),
                    close_price = VALUES(close_price),
                    volume = VALUES(volume),
                    amount = VALUES(amount),
                    pct_change = VALUES(pct_change),
                    updated_at = CURRENT_TIMESTAMP
                """
                
                for data in data_list:
                    try:
                        cursor.execute(sql, (
                            data.get('instrument_code'),
                            data.get('instrument_type'),
                            data.get('trade_date'),
                            data.get('open_price'),
                            data.get('high_price'),
                            data.get('low_price'),
                            data.get('close_price'),
                            data.get('volume'),
                            data.get('amount'),
                            data.get('pct_change')
                        ))
                        success_count += 1
                    except Exception as e:
                        self.logger.error(f"插入单条数据失败: {e}")
                        
                conn.commit()
                self.logger.info(f"批量插入市场数据完成，成功{success_count}条")
                
        except Exception as e:
            self.logger.error(f"批量插入市场数据失败: {e}")
            
        return success_count
    
    def execute_query(self, sql: str, params: tuple = None) -> List[Dict]:
        """
        执行自定义查询SQL
        
        Args:
            sql: SQL查询语句
            params: SQL参数
            
        Returns:
            List[Dict]: 查询结果
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params or ())
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"执行查询失败: {e}")
            return []
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        获取表信息统计
        
        Args:
            table_name: 表名
            
        Returns:
            Dict[str, Any]: 表信息统计
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取表记录数
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                count_result = cursor.fetchone()
                
                # 获取表结构信息
                cursor.execute(f"DESCRIBE {table_name}")
                structure = cursor.fetchall()
                
                return {
                    'table_name': table_name,
                    'record_count': count_result['count'],
                    'structure': structure,
                    'updated_at': datetime.now().isoformat()
                }
        except Exception as e:
            self.logger.error(f"获取表信息失败 {table_name}: {e}")
            return {}
    
    def _create_instrument_basic_table(self, cursor):
        """创建统一基本信息表（ETF、指数、基金）"""
        sql = """
        CREATE TABLE IF NOT EXISTS instrument_basic (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
            symbol VARCHAR(20) DEFAULT NULL COMMENT '交易代码',
            name VARCHAR(100) NOT NULL COMMENT '名称/简称',
            fullname VARCHAR(200) DEFAULT NULL COMMENT '全称',
            data_type ENUM('etf', 'index', 'fund') NOT NULL COMMENT '数据类型',
            market VARCHAR(20) DEFAULT NULL COMMENT '市场(SH/SZ/CSI/SSE/SZSE等)',
            
            -- ETF特有字段
            tracking_index VARCHAR(100) DEFAULT NULL COMMENT 'ETF跟踪指数',
            
            -- 指数特有字段
            publisher VARCHAR(50) DEFAULT NULL COMMENT '指数发布方',
            index_type VARCHAR(50) DEFAULT NULL COMMENT '指数风格',
            category VARCHAR(50) DEFAULT NULL COMMENT '指数类别',
            base_date VARCHAR(10) DEFAULT NULL COMMENT '基期',
            base_point DECIMAL(10,2) DEFAULT NULL COMMENT '基点',
            weight_rule VARCHAR(100) DEFAULT NULL COMMENT '加权方式',
            
            -- 基金特有字段
            management VARCHAR(100) DEFAULT NULL COMMENT '管理人',
            custodian VARCHAR(100) DEFAULT NULL COMMENT '托管人',
            fund_type VARCHAR(50) DEFAULT NULL COMMENT '基金类型',
            invest_type VARCHAR(50) DEFAULT NULL COMMENT '投资风格',
            benchmark VARCHAR(200) DEFAULT NULL COMMENT '业绩基准',
            m_fee DECIMAL(6,4) DEFAULT NULL COMMENT '管理费',
            c_fee DECIMAL(6,4) DEFAULT NULL COMMENT '托管费',
            min_amount DECIMAL(10,2) DEFAULT NULL COMMENT '起点金额(万元)',
            
            -- 通用字段
            list_date VARCHAR(10) DEFAULT NULL COMMENT '上市日期',
            found_date VARCHAR(10) DEFAULT NULL COMMENT '成立日期',
            due_date VARCHAR(10) DEFAULT NULL COMMENT '到期日期',
            delist_date VARCHAR(10) DEFAULT NULL COMMENT '退市日期',
            status VARCHAR(10) DEFAULT 'L' COMMENT '状态(L上市/D摘牌/I发行)',
            description TEXT DEFAULT NULL COMMENT '描述',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_code_type (ts_code, data_type),
            INDEX idx_data_type (data_type),
            INDEX idx_market (market),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一基本信息表'
        """
        cursor.execute(sql)
    
    def _create_instrument_daily_table(self, cursor):
        """创建统一行情数据表（ETF、指数、基金）"""
        sql = """
        CREATE TABLE IF NOT EXISTS instrument_daily (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            ts_code VARCHAR(20) NOT NULL COMMENT 'TS代码',
            data_type ENUM('etf', 'index', 'fund') NOT NULL COMMENT '数据类型',
            trade_date VARCHAR(8) NOT NULL COMMENT '交易日期(YYYYMMDD)',
            
            -- 价格数据 (ETF和指数都有)
            open_price DECIMAL(12,4) DEFAULT NULL COMMENT '开盘价/开盘点位',
            high_price DECIMAL(12,4) DEFAULT NULL COMMENT '最高价/最高点位',
            low_price DECIMAL(12,4) DEFAULT NULL COMMENT '最低价/最低点位',
            close_price DECIMAL(12,4) DEFAULT NULL COMMENT '收盘价/收盘点位',
            pre_close DECIMAL(12,4) DEFAULT NULL COMMENT '昨收盘价/昨收盘点位',
            change_amount DECIMAL(12,4) DEFAULT NULL COMMENT '涨跌额/涨跌点',
            pct_change DECIMAL(8,4) DEFAULT NULL COMMENT '涨跌幅(%)',
            
            -- 成交数据
            volume BIGINT DEFAULT NULL COMMENT '成交量(手)',
            amount DECIMAL(15,2) DEFAULT NULL COMMENT '成交额(千元)',
            
            -- 基金特有字段
            unit_nav DECIMAL(10,4) DEFAULT NULL COMMENT '单位净值',
            accum_nav DECIMAL(10,4) DEFAULT NULL COMMENT '累计净值',
            adj_nav DECIMAL(10,4) DEFAULT NULL COMMENT '复权单位净值',
            accum_div DECIMAL(10,4) DEFAULT NULL COMMENT '累计分红',
            net_asset DECIMAL(15,2) DEFAULT NULL COMMENT '资产净值',
            total_netasset DECIMAL(15,2) DEFAULT NULL COMMENT '合计资产净值',
            ann_date VARCHAR(8) DEFAULT NULL COMMENT '公告日期',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_code_date_type (ts_code, trade_date, data_type),
            INDEX idx_data_type (data_type),
            INDEX idx_trade_date (trade_date),
            INDEX idx_ts_code (ts_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一行情数据表'
        """
        cursor.execute(sql)
    
    def _create_fund_dividend_table(self, cursor):
        """创建基金分红数据表"""
        sql = """
        CREATE TABLE IF NOT EXISTS fund_dividend (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ts_code VARCHAR(20) NOT NULL COMMENT '基金代码',
            ann_date VARCHAR(8) DEFAULT NULL COMMENT '公告日期',
            imp_anndate VARCHAR(8) DEFAULT NULL COMMENT '分红实施公告日',
            base_date VARCHAR(8) DEFAULT NULL COMMENT '分配收益基准日',
            div_proc VARCHAR(20) DEFAULT NULL COMMENT '方案进度',
            record_date VARCHAR(8) DEFAULT NULL COMMENT '权益登记日',
            ex_date VARCHAR(8) DEFAULT NULL COMMENT '除息日',
            pay_date VARCHAR(8) DEFAULT NULL COMMENT '派息日',
            earpay_date VARCHAR(8) DEFAULT NULL COMMENT '收益支付日',
            net_ex_date VARCHAR(8) DEFAULT NULL COMMENT '净值除权日',
            div_cash DECIMAL(10,6) DEFAULT NULL COMMENT '每份派息(元)',
            base_unit DECIMAL(15,4) DEFAULT NULL COMMENT '基准基金份额(万份)',
            ear_distr DECIMAL(15,2) DEFAULT NULL COMMENT '可分配收益(元)',
            ear_amount DECIMAL(15,2) DEFAULT NULL COMMENT '收益分配金额(元)',
            account_date VARCHAR(8) DEFAULT NULL COMMENT '红利再投资到账日',
            base_year VARCHAR(4) DEFAULT NULL COMMENT '份额基准年度',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_fund_dividend (ts_code, ex_date),
            INDEX idx_ts_code (ts_code),
            INDEX idx_ex_date (ex_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金分红数据表'
        """
        cursor.execute(sql)
    
    def _create_fund_share_table(self, cursor):
        """创建基金规模数据表"""
        sql = """
        CREATE TABLE IF NOT EXISTS fund_share (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ts_code VARCHAR(20) NOT NULL COMMENT '基金代码',
            trade_date VARCHAR(8) NOT NULL COMMENT '交易日期',
            fd_share DECIMAL(15,4) DEFAULT NULL COMMENT '基金份额(万)',
            data_type VARCHAR(20) DEFAULT 'fund_share' COMMENT '数据类型',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_fund_share (ts_code, trade_date),
            INDEX idx_ts_code (ts_code),
            INDEX idx_trade_date (trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金规模数据表'
        """
        cursor.execute(sql)
    
    def add_instrument_basic(self, data_type: str, ts_code: str, name: str, **kwargs) -> bool:
        """
        添加统一基本信息
        
        Args:
            data_type: 数据类型 ('etf', 'index', 'fund')
            ts_code: TS代码
            name: 名称
            **kwargs: 其他字段
            
        Returns:
            bool: 添加成功返回True，否则返回False
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建字段和值
                fields = ['data_type', 'ts_code', 'name']
                values = [data_type, ts_code, name]
                placeholders = ['%s', '%s', '%s']
                
                # 添加其他字段
                allowed_fields = [
                    'symbol', 'fullname', 'market', 'tracking_index', 'publisher',
                    'index_type', 'category', 'base_date', 'base_point', 'weight_rule',
                    'management', 'custodian', 'fund_type', 'invest_type', 'benchmark',
                    'm_fee', 'c_fee', 'min_amount', 'list_date', 'found_date',
                    'due_date', 'delist_date', 'status', 'description'
                ]
                
                for field, value in kwargs.items():
                    if field in allowed_fields and value is not None:
                        fields.append(field)
                        values.append(value)
                        placeholders.append('%s')
                
                sql = f"""
                INSERT INTO instrument_basic ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                ON DUPLICATE KEY UPDATE
                """
                
                # 构建更新语句
                update_fields = []
                for i, field in enumerate(fields[1:], 1):  # 跳过data_type
                    if field != 'ts_code':  # 不更新主键
                        update_fields.append(f"{field} = VALUES({field})")
                
                if update_fields:
                    sql += ', '.join(update_fields) + ", updated_at = CURRENT_TIMESTAMP"
                else:
                    sql += "updated_at = CURRENT_TIMESTAMP"
                
                cursor.execute(sql, values)
                conn.commit()
                # self.logger.info(f"成功添加{data_type}基本信息: {ts_code} - {name}")
                return True
        except Exception as e:
            self.logger.error(f"添加{data_type}基本信息失败 {ts_code}: {e}")
            return False
    
    def add_instrument_daily(self, data_type: str, ts_code: str, trade_date: str, **kwargs) -> bool:
        """
        添加统一行情数据
        
        Args:
            data_type: 数据类型 ('etf', 'index', 'fund')
            ts_code: TS代码
            trade_date: 交易日期(YYYYMMDD格式)
            **kwargs: 其他字段
            
        Returns:
            bool: 添加成功返回True，否则返回False
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建字段和值
                fields = ['data_type', 'ts_code', 'trade_date']
                values = [data_type, ts_code, trade_date]
                placeholders = ['%s', '%s', '%s']
                
                # 添加其他字段
                allowed_fields = [
                    'open_price', 'high_price', 'low_price', 'close_price', 'pre_close',
                    'change_amount', 'pct_change', 'volume', 'amount', 'unit_nav',
                    'accum_nav', 'adj_nav', 'accum_div', 'net_asset', 'total_netasset', 'ann_date'
                ]
                
                for field, value in kwargs.items():
                    if field in allowed_fields and value is not None:
                        fields.append(field)
                        values.append(value)
                        placeholders.append('%s')
                
                sql = f"""
                INSERT INTO instrument_daily ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                ON DUPLICATE KEY UPDATE
                """
                
                # 构建更新语句
                update_fields = []
                for field in fields[3:]:  # 跳过主键字段
                    update_fields.append(f"{field} = VALUES({field})")
                
                if update_fields:
                    sql += ', '.join(update_fields) + ", updated_at = CURRENT_TIMESTAMP"
                else:
                    sql += "updated_at = CURRENT_TIMESTAMP"
                
                cursor.execute(sql, values)
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"添加{data_type}行情数据失败 {ts_code} {trade_date}: {e}")
            return False
    
    def get_instrument_basic(self, data_type: str = None, ts_code: str = None, market: str = None) -> List[Dict]:
        """
        查询统一基本信息
        
        Args:
            data_type: 数据类型过滤
            ts_code: TS代码过滤
            market: 市场过滤
            
        Returns:
            List[Dict]: 基本信息列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM instrument_basic WHERE 1=1"
                params = []
                
                if data_type:
                    sql += " AND data_type = %s"
                    params.append(data_type)
                    
                    # 对于指数类型，只保留SSE和SZSE市场的数据（上海和深圳交易所）
                    if data_type == 'index':
                        sql += " AND market IN ('SSE', 'SZSE')"
                    
                if ts_code:
                    sql += " AND ts_code = %s"
                    params.append(ts_code)
                    
                if market:
                    sql += " AND market = %s"
                    params.append(market)
                
                sql += " ORDER BY data_type, ts_code"
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"查询基本信息失败: {e}")
            return []
    
    def get_instrument_basic_with_date_filter(self, data_type: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        查询符合日期范围要求的工具基本信息
        
        Args:
            data_type: 数据类型
            start_date: 要求的开始日期(YYYYMMDD)，None表示不限制
            end_date: 要求的结束日期(YYYYMMDD)，None表示不限制
            
        Returns:
            List[Dict]: 符合条件的基本信息列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if start_date and end_date:
                    # 对于指数类型，只保留SSE和SZSE市场的数据（上海和深圳交易所）
                    market_filter = " AND ib.market IN ('SSE', 'SZSE')" if data_type == 'index' else ""
                    
                    # 使用日期过滤：工具最早日期 <= start_date AND 工具最晚日期 >= end_date
                    sql = f"""
                    SELECT ib.* 
                    FROM instrument_basic ib
                    WHERE ib.data_type = %s{market_filter}
                    AND ib.ts_code IN (
                        SELECT ts_code FROM instrument_daily
                        WHERE data_type = %s
                        GROUP BY ts_code
                        HAVING MIN(trade_date) <= %s AND MAX(trade_date) >= %s
                    )
                    ORDER BY ib.ts_code
                    """
                    params = [data_type, data_type, start_date, end_date]
                else:
                    # 没有日期要求，返回所有该类型的基本信息
                    # 对于指数类型，只保留SSE和SZSE市场的数据（上海和深圳交易所）
                    if data_type == 'index':
                        sql = "SELECT * FROM instrument_basic WHERE data_type = %s AND market IN ('SSE', 'SZSE') ORDER BY ts_code"
                    else:
                        sql = "SELECT * FROM instrument_basic WHERE data_type = %s ORDER BY ts_code"
                    params = [data_type]
                
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                if start_date and end_date:
                    self.logger.info(f"日期过滤查询{data_type}基本信息：找到{len(results)}个符合条件的工具")
                else:
                    self.logger.info(f"查询{data_type}基本信息：找到{len(results)}个工具")
                    
                return results
                
        except Exception as e:
            self.logger.error(f"查询基本信息失败: {e}")
            return []
    
    def get_instrument_daily(self, data_type: str, ts_code: str = None,
                           start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        查询统一行情数据
        
        Args:
            data_type: 数据类型
            ts_code: TS代码
            start_date: 开始日期(YYYYMMDD格式)
            end_date: 结束日期(YYYYMMDD格式)
            
        Returns:
            List[Dict]: 行情数据列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM instrument_daily WHERE data_type = %s"
                params = [data_type]
                
                if ts_code:
                    sql += " AND ts_code = %s"
                    params.append(ts_code)
                    
                if start_date:
                    sql += " AND trade_date >= %s"
                    params.append(start_date)
                    
                if end_date:
                    sql += " AND trade_date <= %s"
                    params.append(end_date)
                
                sql += " ORDER BY ts_code, trade_date"
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"查询行情数据失败: {e}")
            return []
    
    def get_instrument_daily_dataframe(self, data_type: str, ts_code: str = None,
                                     start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        查询统一行情数据并返回DataFrame（避免编码问题）
        
        Args:
            data_type: 数据类型
            ts_code: TS代码
            start_date: 开始日期(YYYYMMDD格式)
            end_date: 结束日期(YYYYMMDD格式)
            
        Returns:
            pd.DataFrame: 行情数据DataFrame
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM instrument_daily WHERE data_type = %s"
                params = [data_type]
                
                if ts_code:
                    sql += " AND ts_code = %s"
                    params.append(ts_code)
                    
                if start_date:
                    sql += " AND trade_date >= %s"
                    params.append(start_date)
                    
                if end_date:
                    sql += " AND trade_date <= %s"
                    params.append(end_date)
                
                sql += " ORDER BY ts_code, trade_date"
                cursor.execute(sql, params)
                
                # 获取列名
                columns = [desc[0] for desc in cursor.description]
                
                # 获取数据
                rows = cursor.fetchall()
                
                # 创建DataFrame
                if rows:
                    df = pd.DataFrame(rows, columns=columns)
                    return df
                else:
                    return pd.DataFrame()
                    
        except Exception as e:
            self.logger.error(f"查询统一行情数据DataFrame失败: {e}")
            return pd.DataFrame()
    
    def get_qualified_instruments_summary(self, data_type: str, start_date: str = None, end_date: str = None, limit: int = None) -> List[Dict]:
        """
        轻量级预筛选：基于daily表直接筛选符合日期范围要求的工具
        仅返回工具代码和统计信息，不加载实际数据
        
        Args:
            data_type: 数据类型
            start_date: 要求的开始日期(YYYYMMDD)，None表示不限制
            end_date: 要求的结束日期(YYYYMMDD)，None表示不限制
            limit: 限制返回数量
            
        Returns:
            List[Dict]: [{'ts_code': 'xxx', 'first_date': 'yyyymmdd', 'last_date': 'yyyymmdd', 'data_count': n}]
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 对于指数类型，只保留SSE和SZSE市场的数据（上海和深圳交易所）
                if data_type == 'index':
                    sql = """
                    SELECT 
                        id.ts_code,
                        MIN(id.trade_date) as first_date,
                        MAX(id.trade_date) as last_date,
                        COUNT(*) as data_count
                    FROM instrument_daily id
                    JOIN instrument_basic ib ON id.ts_code = ib.ts_code AND id.data_type = ib.data_type
                    WHERE id.data_type = %s AND ib.market IN ('SSE', 'SZSE')
                    """
                else:
                    sql = """
                    SELECT 
                        ts_code,
                        MIN(trade_date) as first_date,
                        MAX(trade_date) as last_date,
                        COUNT(*) as data_count
                    FROM instrument_daily 
                    WHERE data_type = %s
                    """
                params = [data_type]
                
                # 如果有日期范围要求，添加过滤条件
                if start_date and end_date:
                    if data_type == 'index':
                        sql += """
                        AND id.ts_code IN (
                            SELECT ts_code FROM instrument_daily
                            WHERE data_type = %s
                            GROUP BY ts_code
                            HAVING MIN(trade_date) <= %s AND MAX(trade_date) >= %s
                        )
                        """
                        params.extend([data_type, start_date, end_date])
                    else:
                        sql += """
                        AND ts_code IN (
                            SELECT ts_code FROM instrument_daily
                            WHERE data_type = %s
                            GROUP BY ts_code
                            HAVING MIN(trade_date) <= %s AND MAX(trade_date) >= %s
                        )
                        """
                        params.extend([data_type, start_date, end_date])
                
                if data_type == 'index':
                    sql += " GROUP BY id.ts_code ORDER BY id.ts_code"
                else:
                    sql += " GROUP BY ts_code ORDER BY ts_code"
                
                if limit:
                    sql += f" LIMIT {limit}"
                
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                self.logger.info(f"预筛选{data_type}数据：找到{len(results)}个符合条件的工具")
                return results
                
        except Exception as e:
            self.logger.error(f"预筛选工具失败: {e}")
            return []
    
    def get_instruments_basic_batch(self, ts_codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取基本信息
        
        Args:
            ts_codes: 工具代码列表
            
        Returns:
            Dict[str, Dict]: {ts_code: basic_info_dict}
        """
        try:
            if not ts_codes:
                return {}
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 构建IN查询
                placeholders = ','.join(['%s'] * len(ts_codes))
                sql = f"""
                SELECT * FROM instrument_basic 
                WHERE ts_code IN ({placeholders})
                ORDER BY ts_code
                """
                
                cursor.execute(sql, ts_codes)
                results = cursor.fetchall()
                
                # 转换为字典格式
                basic_info_dict = {}
                for row in results:
                    basic_info_dict[row['ts_code']] = row
                
                self.logger.info(f"批量获取基本信息：{len(results)}/{len(ts_codes)}个工具")
                return basic_info_dict
                
        except Exception as e:
            self.logger.error(f"批量获取基本信息失败: {e}")
            return {}
    
    def get_instruments_daily_batch_safe(self, data_type: str, ts_codes: List[str], start_date: str = None, end_date: str = None, batch_size: int = 50):
        """
        内存安全的分批获取日线数据
        
        Args:
            data_type: 数据类型
            ts_codes: 工具代码列表
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)
            batch_size: 每批处理的工具数量
            
        Yields:
            Dict[str, List[Dict]]: 每批次的数据 {ts_code: daily_data_list}
        """
        try:
            if not ts_codes:
                return
            
            for i in range(0, len(ts_codes), batch_size):
                batch_codes = ts_codes[i:i+batch_size]
                self.logger.info(f"获取第{i//batch_size + 1}批数据：{len(batch_codes)}个工具 (索引{i}-{i+len(batch_codes)-1})")
                
                batch_data = self._get_batch_daily_data(data_type, batch_codes, start_date, end_date)
                yield batch_data
                
        except Exception as e:
            self.logger.error(f"分批获取日线数据失败: {e}")
            return
    
    def _get_batch_daily_data(self, data_type: str, ts_codes: List[str], start_date: str = None, end_date: str = None) -> Dict[str, List[Dict]]:
        """
        获取单个批次的日线数据
        
        Returns:
            Dict[str, List[Dict]]: {ts_code: daily_data_list}
        """
        try:
            if not ts_codes:
                return {}
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 构建IN查询
                placeholders = ','.join(['%s'] * len(ts_codes))
                sql = f"SELECT * FROM instrument_daily WHERE data_type = %s AND ts_code IN ({placeholders})"
                params = [data_type] + ts_codes
                
                if start_date:
                    sql += " AND trade_date >= %s"
                    params.append(start_date)
                    
                if end_date:
                    sql += " AND trade_date <= %s"
                    params.append(end_date)
                
                sql += " ORDER BY ts_code, trade_date"
                
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                # 按ts_code分组
                batch_data = {}
                for row in results:
                    ts_code = row['ts_code']
                    if ts_code not in batch_data:
                        batch_data[ts_code] = []
                    batch_data[ts_code].append(row)
                
                total_records = sum(len(data) for data in batch_data.values())
                self.logger.info(f"批次数据：{len(batch_data)}个工具，{total_records}条记录")
                
                return batch_data
                
        except Exception as e:
            self.logger.error(f"获取批次日线数据失败: {e}")
            return {}

    def get_instrument_date_range(self, data_type: str, ts_code: str) -> Dict[str, str]:
        """
        获取工具的日期范围信息
        
        Args:
            data_type: 数据类型
            ts_code: 工具代码
            
        Returns:
            Dict[str, str]: 包含min_date和max_date的字典
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = """
                    SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date 
                    FROM instrument_daily 
                    WHERE data_type = %s AND ts_code = %s
                """
                cursor.execute(sql, [data_type, ts_code])
                result = cursor.fetchone()
                
                if result:
                    return {
                        'min_date': result['min_date'],
                        'max_date': result['max_date']
                    }
                else:
                    return {}
                    
        except Exception as e:
            self.logger.error(f"查询{ts_code}日期范围失败: {e}")
            return {}
    
    def clear_instrument_data_by_date_range(self, data_type: str = None, start_date: str = None, end_date: str = None) -> Dict[str, int]:
        """
        按日期范围清理instrument数据
        
        Args:
            data_type: 数据类型过滤 ('etf', 'index', 'fund')，为空时清理所有类型
            start_date: 开始日期(YYYYMMDD格式)
            end_date: 结束日期(YYYYMMDD格式)
            
        Returns:
            Dict[str, int]: 清理的记录数量
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                results = {'basic_deleted': 0, 'daily_deleted': 0}
                
                # 清理基本信息（如果没有指定日期范围，才清理基本信息）
                if not start_date and not end_date:
                    sql = "DELETE FROM instrument_basic WHERE 1=1"
                    params = []
                    
                    if data_type:
                        sql += " AND data_type = %s"
                        params.append(data_type)
                    
                    cursor.execute(sql, params)
                    results['basic_deleted'] = cursor.rowcount
                    self.logger.info(f"清理基本信息表: {results['basic_deleted']}条")
                
                # 清理日线数据
                sql = "DELETE FROM instrument_daily WHERE 1=1"
                params = []
                
                if data_type:
                    sql += " AND data_type = %s"
                    params.append(data_type)
                    
                if start_date:
                    sql += " AND trade_date >= %s"
                    params.append(start_date)
                    
                if end_date:
                    sql += " AND trade_date <= %s"
                    params.append(end_date)
                
                cursor.execute(sql, params)
                results['daily_deleted'] = cursor.rowcount
                self.logger.info(f"清理日线数据表: {results['daily_deleted']}条")
                
                conn.commit()
                total_deleted = results['basic_deleted'] + results['daily_deleted']
                self.logger.info(f"总共清理数据: {total_deleted}条")
                
                return results
                
        except Exception as e:
            self.logger.error(f"清理数据失败: {e}")
            return {'basic_deleted': 0, 'daily_deleted': 0}
    
    def clear_all_instrument_data(self, data_type: str = None) -> Dict[str, int]:
        """
        清空所有instrument数据
        
        Args:
            data_type: 数据类型过滤 ('etf', 'index', 'fund')，为空时清理所有类型
            
        Returns:
            Dict[str, int]: 清理的记录数量
        """
        return self.clear_instrument_data_by_date_range(data_type=data_type)
    
    def get_data_statistics(self, data_type: str = None) -> Dict[str, Any]:
        """
        获取数据统计信息
        
        Args:
            data_type: 数据类型过滤 ('etf', 'index', 'fund')，为空时统计所有类型
            
        Returns:
            Dict[str, Any]: 数据统计信息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                stats = {}
                
                # 统计基本信息
                sql = "SELECT data_type, COUNT(*) as count FROM instrument_basic WHERE 1=1"
                params = []
                
                if data_type:
                    sql += " AND data_type = %s"
                    params.append(data_type)
                    
                sql += " GROUP BY data_type"
                cursor.execute(sql, params)
                basic_stats = cursor.fetchall()
                stats['basic_info'] = {row['data_type']: row['count'] for row in basic_stats}
                
                # 统计日线数据
                sql = """
                SELECT data_type, 
                       COUNT(*) as total_records,
                       COUNT(DISTINCT ts_code) as unique_codes,
                       MIN(trade_date) as earliest_date,
                       MAX(trade_date) as latest_date
                FROM instrument_daily WHERE 1=1
                """
                params = []
                
                if data_type:
                    sql += " AND data_type = %s"
                    params.append(data_type)
                    
                sql += " GROUP BY data_type"
                cursor.execute(sql, params)
                daily_stats = cursor.fetchall()
                
                stats['daily_data'] = {}
                for row in daily_stats:
                    stats['daily_data'][row['data_type']] = {
                        'total_records': row['total_records'],
                        'unique_codes': row['unique_codes'],
                        'date_range': f"{row['earliest_date']} - {row['latest_date']}"
                    }
                
                # 总计统计
                total_basic = sum(stats['basic_info'].values())
                total_daily = sum([v['total_records'] for v in stats['daily_data'].values()])
                stats['summary'] = {
                    'total_basic_records': total_basic,
                    'total_daily_records': total_daily,
                    'total_records': total_basic + total_daily
                }
                
                return stats
                
        except Exception as e:
            self.logger.error(f"获取数据统计失败: {e}")
            return {}
    
    def validate_data_completeness(self, data_type: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        验证数据完整性
        
        Args:
            data_type: 数据类型 ('etf', 'index', 'fund')
            start_date: 开始日期(YYYYMMDD格式)
            end_date: 结束日期(YYYYMMDD格式)
            
        Returns:
            Dict[str, Any]: 数据完整性报告
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取该类型的基本信息数量
                cursor.execute(
                    "SELECT COUNT(*) as count FROM instrument_basic WHERE data_type = %s",
                    (data_type,)
                )
                basic_count = cursor.fetchone()['count']
                
                # 获取日期范围内的数据情况
                cursor.execute("""
                    SELECT COUNT(*) as total_records,
                           COUNT(DISTINCT ts_code) as unique_codes,
                           COUNT(DISTINCT trade_date) as unique_dates
                    FROM instrument_daily 
                    WHERE data_type = %s AND trade_date >= %s AND trade_date <= %s
                """, (data_type, start_date, end_date))
                
                daily_stats = cursor.fetchone()
                
                # 获取交易日历用于计算预期记录数
                trading_dates = self._get_trading_dates_from_db(start_date, end_date)
                expected_records = basic_count * len(trading_dates) if trading_dates else 0
                
                completeness_rate = (daily_stats['total_records'] / expected_records * 100) if expected_records > 0 else 0
                
                report = {
                    'data_type': data_type,
                    'date_range': f"{start_date} - {end_date}",
                    'basic_info_count': basic_count,
                    'daily_stats': daily_stats,
                    'trading_dates_count': len(trading_dates),
                    'expected_records': expected_records,
                    'completeness_rate': round(completeness_rate, 2),
                    'status': 'good' if completeness_rate >= 90 else 'warning' if completeness_rate >= 70 else 'poor'
                }
                
                return report
                
        except Exception as e:
            self.logger.error(f"验证数据完整性失败: {e}")
            return {}
    
    def _get_trading_dates_from_db(self, start_date: str, end_date: str) -> List[str]:
        """
        从数据库获取交易日期（简化版本，实际应该有单独的交易日历表）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[str]: 交易日期列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT trade_date 
                    FROM instrument_daily 
                    WHERE trade_date >= %s AND trade_date <= %s 
                    ORDER BY trade_date
                """, (start_date, end_date))
                
                result = cursor.fetchall()
                return [row['trade_date'] for row in result]
                
        except Exception as e:
            self.logger.warning(f"获取交易日期失败: {e}")
            return []
    
    def batch_insert_instrument_daily(self, data_list: List[Dict], batch_size: int = 1000) -> int:
        """
        批量插入instrument_daily表数据
        
        Args:
            data_list: 包含所有字段的数据列表，每个字典应包含:
                     - data_type: 数据类型 ('etf', 'index', 'fund')
                     - ts_code: 证券代码
                     - trade_date: 交易日期
                     - 其他价格、成交量等字段
            batch_size: 批处理大小，默认1000条
            
        Returns:
            int: 成功插入的数据条数
        """
        if not data_list:
            return 0
            
        total_success = 0
        
        try:
            # 按批次处理数据
            for i in range(0, len(data_list), batch_size):
                batch_data = data_list[i:i + batch_size]
                batch_success = self._insert_batch_data(batch_data)
                total_success += batch_success
                
                self.logger.info(f"批次 {i//batch_size + 1}: 成功插入 {batch_success}/{len(batch_data)} 条")
            
            self.logger.info(f"批量插入完成，总计成功 {total_success}/{len(data_list)} 条")
            return total_success
            
        except Exception as e:
            self.logger.error(f"批量插入instrument_daily数据失败: {e}")
            return total_success
    
    def _insert_batch_data(self, batch_data: List[Dict]) -> int:
        """
        插入一批数据
        
        Args:
            batch_data: 批量数据
            
        Returns:
            int: 成功插入的数据条数
        """
        success_count = 0
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 准备批量插入SQL
                sql = """
                INSERT INTO instrument_daily (
                    data_type, ts_code, trade_date, open_price, high_price, low_price,
                    close_price, pre_close, change_amount, pct_change, volume, amount,
                    unit_nav, accum_nav, adj_nav, accum_div, net_asset, total_netasset,
                    ann_date, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON DUPLICATE KEY UPDATE
                    open_price = VALUES(open_price),
                    high_price = VALUES(high_price),
                    low_price = VALUES(low_price),
                    close_price = VALUES(close_price),
                    pre_close = VALUES(pre_close),
                    change_amount = VALUES(change_amount),
                    pct_change = VALUES(pct_change),
                    volume = VALUES(volume),
                    amount = VALUES(amount),
                    unit_nav = VALUES(unit_nav),
                    accum_nav = VALUES(accum_nav),
                    adj_nav = VALUES(adj_nav),
                    accum_div = VALUES(accum_div),
                    net_asset = VALUES(net_asset),
                    total_netasset = VALUES(total_netasset),
                    ann_date = VALUES(ann_date),
                    updated_at = CURRENT_TIMESTAMP
                """
                
                # 准备批量数据
                batch_values = []
                for data in batch_data:
                    values = (
                        data.get('data_type'),
                        data.get('ts_code'),
                        data.get('trade_date'),
                        data.get('open_price'),
                        data.get('high_price'),
                        data.get('low_price'),
                        data.get('close_price'),
                        data.get('pre_close'),
                        data.get('change_amount'),
                        data.get('pct_change'),
                        data.get('volume'),
                        data.get('amount'),
                        data.get('unit_nav'),
                        data.get('accum_nav'),
                        data.get('adj_nav'),
                        data.get('accum_div'),
                        data.get('net_asset'),
                        data.get('total_netasset'),
                        data.get('ann_date')
                    )
                    batch_values.append(values)
                
                # 执行批量插入
                cursor.executemany(sql, batch_values)
                conn.commit()
                
                # 获取实际插入的行数
                success_count = cursor.rowcount if cursor.rowcount > 0 else 0
                self.logger.debug(f"批量插入: 提交{len(batch_values)}条，实际插入/更新{success_count}条")
                
        except Exception as e:
            self.logger.error(f"插入批量数据失败: {e}")
            # 异常情况下success_count保持0
            success_count = 0
            
        return success_count

    # ==================== 基金分红数据相关方法 ====================
    
    def insert_fund_dividend_data(self, dividend_data: List[Dict]) -> int:
        """
        批量插入基金分红数据
        
        Args:
            dividend_data: 分红数据列表
            
        Returns:
            int: 成功插入的记录数
        """
        if not dividend_data:
            return 0
            
        success_count = 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                INSERT INTO fund_dividend (
                    ts_code, ann_date, imp_anndate, base_date, div_proc, 
                    record_date, ex_date, pay_date, earpay_date, net_ex_date, 
                    div_cash, base_unit, ear_distr, ear_amount, account_date, base_year
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    ann_date = VALUES(ann_date),
                    imp_anndate = VALUES(imp_anndate),
                    base_date = VALUES(base_date),
                    div_proc = VALUES(div_proc),
                    record_date = VALUES(record_date),
                    pay_date = VALUES(pay_date),
                    earpay_date = VALUES(earpay_date),
                    net_ex_date = VALUES(net_ex_date),
                    div_cash = VALUES(div_cash),
                    base_unit = VALUES(base_unit),
                    ear_distr = VALUES(ear_distr),
                    ear_amount = VALUES(ear_amount),
                    account_date = VALUES(account_date),
                    base_year = VALUES(base_year),
                    updated_at = CURRENT_TIMESTAMP
                """
                
                # 准备批量数据
                batch_values = []
                for data in dividend_data:
                    # 处理NaN值，转换为None
                    def handle_nan(value):
                        if pd.isna(value) or value != value:  # 检查NaN
                            return None
                        return value
                    
                    values = (
                        handle_nan(data.get('ts_code')),
                        handle_nan(data.get('ann_date')),
                        handle_nan(data.get('imp_anndate')),
                        handle_nan(data.get('base_date')),
                        handle_nan(data.get('div_proc')),
                        handle_nan(data.get('record_date')),
                        handle_nan(data.get('ex_date')),
                        handle_nan(data.get('pay_date')),
                        handle_nan(data.get('earpay_date')),
                        handle_nan(data.get('net_ex_date')),
                        handle_nan(data.get('div_cash')),
                        handle_nan(data.get('base_unit')),
                        handle_nan(data.get('ear_distr')),
                        handle_nan(data.get('ear_amount')),
                        handle_nan(data.get('account_date')),
                        handle_nan(data.get('base_year'))
                    )
                    batch_values.append(values)
                
                # 执行批量插入
                cursor.executemany(sql, batch_values)
                conn.commit()
                
                success_count = cursor.rowcount if cursor.rowcount > 0 else 0
                self.logger.debug(f"基金分红数据批量插入: 提交{len(batch_values)}条，实际插入/更新{success_count}条")
                
        except Exception as e:
            self.logger.error(f"插入基金分红数据失败: {e}")
            success_count = 0
            
        return success_count
    
    def get_fund_dividend_by_code(self, ts_code: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        根据基金代码获取分红数据
        
        Args:
            ts_code: 基金代码
            start_date: 开始日期(YYYYMMDD格式)
            end_date: 结束日期(YYYYMMDD格式)
            
        Returns:
            List[Dict]: 分红数据列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建SQL查询
                sql = "SELECT * FROM fund_dividend WHERE ts_code = %s"
                params = [ts_code]
                
                if start_date:
                    sql += " AND ex_date >= %s"
                    params.append(start_date)
                    
                if end_date:
                    sql += " AND ex_date <= %s"
                    params.append(end_date)
                
                sql += " ORDER BY ex_date"
                
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                self.logger.debug(f"查询到{ts_code}的{len(results)}条分红记录")
                return results if results else []
                
        except Exception as e:
            self.logger.error(f"查询基金分红数据失败 {ts_code}: {e}")
            return []
    
    def get_fund_dividend_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """
        根据日期范围获取分红数据
        
        Args:
            start_date: 开始日期(YYYYMMDD格式)
            end_date: 结束日期(YYYYMMDD格式)
            
        Returns:
            List[Dict]: 分红数据列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                SELECT * FROM fund_dividend 
                WHERE ex_date >= %s AND ex_date <= %s 
                ORDER BY ex_date, ts_code
                """
                
                cursor.execute(sql, [start_date, end_date])
                results = cursor.fetchall()
                
                self.logger.debug(f"查询到日期范围{start_date}-{end_date}的{len(results)}条分红记录")
                return results if results else []
                
        except Exception as e:
            self.logger.error(f"查询日期范围分红数据失败 {start_date}-{end_date}: {e}")
            return []
    
    def get_fund_dividend_statistics(self) -> Dict[str, int]:
        """
        获取基金分红数据统计信息
        
        Returns:
            Dict[str, int]: 统计信息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT ts_code) as unique_funds,
                    MIN(ex_date) as earliest_date,
                    MAX(ex_date) as latest_date
                FROM fund_dividend
                """
                
                cursor.execute(sql)
                result = cursor.fetchone()
                
                return result if result else {}
                
        except Exception as e:
            self.logger.error(f"查询基金分红统计信息失败: {e}")
            return {}

    # ==================== 基金规模数据相关方法 ====================
    
    def batch_insert_fund_share_data(self, share_data: List[Dict], batch_size: int = 1000) -> int:
        """
        批量插入基金规模数据
        
        Args:
            share_data: 基金规模数据列表
            batch_size: 批量大小
            
        Returns:
            int: 成功插入的记录数
        """
        if not share_data:
            return 0
            
        success_count = 0
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                INSERT INTO fund_share (
                    ts_code, trade_date, fd_share, data_type
                ) VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    fd_share = VALUES(fd_share),
                    data_type = VALUES(data_type),
                    updated_at = CURRENT_TIMESTAMP
                """
                
                # 准备批量数据
                batch_values = []
                for data in share_data:
                    values = (
                        data.get('ts_code'),
                        data.get('trade_date'),
                        data.get('fd_share'),
                        data.get('data_type', 'fund_share')
                    )
                    batch_values.append(values)
                
                # 执行批量插入
                cursor.executemany(sql, batch_values)
                conn.commit()
                
                success_count = cursor.rowcount if cursor.rowcount > 0 else 0
                self.logger.debug(f"基金规模数据批量插入: 提交{len(batch_values)}条，实际插入/更新{success_count}条")
                
        except Exception as e:
            self.logger.error(f"插入基金规模数据失败: {e}")
            success_count = 0
            
        return success_count
    
    def get_fund_share_by_code(self, ts_code: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        根据基金代码获取规模数据
        
        Args:
            ts_code: 基金代码
            start_date: 开始日期(YYYYMMDD格式)
            end_date: 结束日期(YYYYMMDD格式)
            
        Returns:
            List[Dict]: 基金规模数据列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建SQL查询
                sql = "SELECT * FROM fund_share WHERE ts_code = %s"
                params = [ts_code]
                
                if start_date:
                    sql += " AND trade_date >= %s"
                    params.append(start_date)
                    
                if end_date:
                    sql += " AND trade_date <= %s"
                    params.append(end_date)
                
                sql += " ORDER BY trade_date"
                
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                self.logger.debug(f"查询到{ts_code}的{len(results)}条规模记录")
                return results if results else []
                
        except Exception as e:
            self.logger.error(f"查询基金规模数据失败 {ts_code}: {e}")
            return []
    
    def get_fund_share_by_date(self, trade_date: str) -> List[Dict]:
        """
        根据交易日期获取所有基金的规模数据
        
        Args:
            trade_date: 交易日期(YYYYMMDD格式)
            
        Returns:
            List[Dict]: 基金规模数据列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                SELECT * FROM fund_share 
                WHERE trade_date = %s 
                ORDER BY ts_code
                """
                
                cursor.execute(sql, [trade_date])
                results = cursor.fetchall()
                
                self.logger.debug(f"查询到{trade_date}的{len(results)}条基金规模记录")
                return results if results else []
                
        except Exception as e:
            self.logger.error(f"查询基金规模数据失败 {trade_date}: {e}")
            return []