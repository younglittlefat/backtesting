"""
基础过滤器类

所有过滤器的抽象基类，定义了过滤器的通用接口。
"""

from abc import ABC, abstractmethod


class BaseFilter(ABC):
    """
    信号过滤器基类

    所有过滤器必须实现 filter_signal 方法
    """

    def __init__(self, enabled=True, **kwargs):
        """
        初始化过滤器

        Args:
            enabled: 是否启用该过滤器
            **kwargs: 过滤器特定的参数
        """
        self.enabled = enabled
        self.params = kwargs

    @abstractmethod
    def filter_signal(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号

        Args:
            strategy: 策略实例，可以访问策略的数据和指标
            signal_type: 信号类型 ('buy' 或 'sell')
            **kwargs: 额外的上下文信息

        Returns:
            bool: True表示信号通过过滤，False表示信号被过滤掉
        """
        pass

    def __call__(self, strategy, signal_type, **kwargs):
        """
        使过滤器可调用

        如果过滤器未启用，直接返回True（通过）
        """
        if not self.enabled:
            return True
        return self.filter_signal(strategy, signal_type, **kwargs)
