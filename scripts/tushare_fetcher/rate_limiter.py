"""
API频率控制器

管理Tushare API调用频率，避免超出限制
"""

import time
import logging
from typing import Optional


class RateLimiter:
    """API频率限制控制器"""

    def __init__(self, max_requests_per_minute: int = 400, logger: Optional[logging.Logger] = None):
        """
        初始化频率限制器

        Args:
            max_requests_per_minute: 每分钟最大请求数
            logger: 日志记录器
        """
        self.max_requests = max_requests_per_minute
        self.request_count = 0
        self.start_time = time.time()
        self.logger = logger or logging.getLogger(__name__)

    def check_and_wait(self):
        """
        检查请求频率，必要时等待

        如果超出频率限制，自动休眠到下一个时间窗口
        """
        if self.request_count >= self.max_requests:
            elapsed_time = time.time() - self.start_time
            if elapsed_time < 60:
                sleep_time = 60 - elapsed_time + 5  # 多等5秒作为缓冲
                self.logger.info(f"【频率控制】已请求 {self.request_count} 次，休息 {sleep_time:.1f} 秒")
                time.sleep(sleep_time)

            # 重置计数器
            self.reset()

    def increment(self):
        """增加请求计数"""
        self.request_count += 1

    def reset(self):
        """重置计数器和时间"""
        self.request_count = 0
        self.start_time = time.time()

    def get_count(self) -> int:
        """获取当前请求计数"""
        return self.request_count
