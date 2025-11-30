"""
线程池管理模块
根据电脑性能动态调整线程数，处理线程安全问题，确保线程正确关闭
"""
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from utils.logger import Logger

logger = Logger().get_logger("ThreadPool")


class ThreadPoolManager:
    """线程池管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式，确保全局只有一个线程池实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ThreadPoolManager, cls).__new__(cls)
                cls._instance._init()
        return cls._instance
    
    def _init(self):
        """初始化线程池"""
        # 根据CPU核心数和系统类型确定线程池大小
        self._cpu_count = os.cpu_count() or 4
        
        # 根据不同任务类型创建不同的线程池
        self._thread_pools = {
            "io": ThreadPoolExecutor(
                max_workers=self._cpu_count * 2,  # IO密集型任务使用更多线程
                thread_name_prefix="IOThreadPool"
            ),
            "cpu": ThreadPoolExecutor(
                max_workers=self._cpu_count,  # CPU密集型任务使用CPU核心数线程
                thread_name_prefix="CPUThreadPool"
            ),
            "download": ThreadPoolExecutor(
                max_workers=min(10, self._cpu_count * 3),  # 下载任务使用适中的线程数
                thread_name_prefix="DownloadThreadPool"
            )
        }
        
        logger.info(f"线程池初始化完成: CPU核心数={self._cpu_count}")
        logger.info(f"IO线程池大小: {self._cpu_count * 2}")
        logger.info(f"CPU线程池大小: {self._cpu_count}")
        logger.info(f"下载线程池大小: {min(10, self._cpu_count * 3)}")
        
        # 注册退出处理
        import atexit
        atexit.register(self.shutdown)
    
    def get_thread_pool(self, pool_type="io"):
        """
        获取指定类型的线程池
        
        Args:
            pool_type: 线程池类型 (io, cpu, download)
            
        Returns:
            ThreadPoolExecutor实例
        """
        if pool_type not in self._thread_pools:
            logger.warning(f"未知的线程池类型: {pool_type}，使用默认IO线程池")
            pool_type = "io"
        return self._thread_pools[pool_type]
    
    def submit(self, pool_type="io", func=None, *args, **kwargs):
        """
        提交任务到指定类型的线程池
        
        Args:
            pool_type: 线程池类型
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
        
        Returns:
            Future对象
        """
        if func is None:
            # 如果func为None，说明调用方式是submit(func, pool_type=...)，交换参数
            func = pool_type
            pool_type = "io"
        
        thread_pool = self.get_thread_pool(pool_type)
        return thread_pool.submit(func, *args, **kwargs)
    
    def map(self, func, iterable, pool_type="io", **kwargs):
        """
        映射任务到指定类型的线程池
        
        Args:
            func: 要执行的函数
            iterable: 可迭代的参数列表
            pool_type: 线程池类型
            **kwargs: 其他参数
            
        Returns:
            结果迭代器
        """
        thread_pool = self.get_thread_pool(pool_type)
        return thread_pool.map(func, iterable, **kwargs)
    
    def shutdown(self, wait=True):
        """
        关闭所有线程池
        
        Args:
            wait: 是否等待所有任务完成
        """
        logger.info("开始关闭线程池...")
        for pool_type, pool in self._thread_pools.items():
            try:
                pool.shutdown(wait=wait)
                logger.info(f"{pool_type}线程池已关闭")
            except Exception as e:
                logger.error(f"关闭{pool_type}线程池失败: {e}")
        logger.info("所有线程池已关闭")
    
    def get_current_thread_info(self):
        """
        获取当前线程信息
        
        Returns:
            线程信息字典
        """
        current_thread = threading.current_thread()
        return {
            "name": current_thread.name,
            "ident": current_thread.ident,
            "daemon": current_thread.daemon,
            "is_alive": current_thread.is_alive()
        }


# 全局线程池管理器实例
thread_pool_manager = ThreadPoolManager()
