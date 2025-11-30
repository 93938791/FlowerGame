"""
HTTP客户端工具 - 支持HTTP/2高效请求，根据电脑性能自动调整线程数
"""
import httpx
import os
import platform
import threading
from typing import Optional, Dict, Any, List
from utils.logger import Logger

logger = Logger().get_logger("HTTPX")

class HTTPXClient:
    """HTTP客户端类，支持HTTP/2和自动线程调整"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(HTTPXClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化HTTP客户端"""
        if hasattr(self, "initialized") and self.initialized:
            return
        
        # 根据系统和CPU核心数自动调整线程数
        self.cpu_count = os.cpu_count() or 4
        
        # 根据系统类型调整默认配置
        if platform.system() == "Windows":
            # Windows系统默认限制连接数
            self.default_max_connections = min(self.cpu_count * 8, 64)
        else:
            # Linux/macOS系统可以使用更多连接
            self.default_max_connections = min(self.cpu_count * 16, 128)
        
        # 配置HTTP/2客户端
        self.client_config = {
            "http2": True,
            "timeout": httpx.Timeout(
                connect=10.0,  # 连接超时10秒
                read=30.0,     # 读取超时30秒
                write=10.0,    # 写入超时10秒
                pool=5.0       # 连接池超时5秒
            ),
            "follow_redirects": True,
            "limits": httpx.Limits(
                max_connections=self.default_max_connections,
                max_keepalive_connections=min(self.default_max_connections, 32),
                keepalive_expiry=30.0
            )
        }
        
        # 创建主客户端实例
        self.client = httpx.AsyncClient(**self.client_config)
        
        # 创建同步客户端实例（用于同步代码）
        self.sync_client = httpx.Client(**self.client_config)
        
        # 请求计数器
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        
        logger.info(f"[HTTPX] 客户端初始化完成 | HTTP/2: 启用 | 最大连接数: {self.default_max_connections} | CPU核心数: {self.cpu_count}")
        
        self.initialized = True
    
    def get_sync_client(self) -> httpx.Client:
        """获取同步客户端实例"""
        return self.sync_client
    
    def get_async_client(self) -> httpx.AsyncClient:
        """获取异步客户端实例"""
        return self.client
    
    async def aget(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        """异步GET请求"""
        self.request_count += 1
        try:
            response = await self.client.get(url, params=params, headers=headers, **kwargs)
            response.raise_for_status()
            self.success_count += 1
            return response
        except Exception as e:
            self.error_count += 1
            logger.error(f"[HTTPX] GET请求失败: {url} - {str(e)}")
            raise
    
    async def apost(self, url: str, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        """异步POST请求"""
        self.request_count += 1
        try:
            response = await self.client.post(url, json=json, data=data, headers=headers, **kwargs)
            response.raise_for_status()
            self.success_count += 1
            return response
        except Exception as e:
            self.error_count += 1
            logger.error(f"[HTTPX] POST请求失败: {url} - {str(e)}")
            raise
    
    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        """同步GET请求"""
        self.request_count += 1
        try:
            response = self.sync_client.get(url, params=params, headers=headers, **kwargs)
            response.raise_for_status()
            self.success_count += 1
            return response
        except Exception as e:
            self.error_count += 1
            logger.error(f"[HTTPX] GET请求失败: {url} - {str(e)}")
            raise
    
    def post(self, url: str, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        """同步POST请求"""
        self.request_count += 1
        try:
            response = self.sync_client.post(url, json=json, data=data, headers=headers, **kwargs)
            response.raise_for_status()
            self.success_count += 1
            return response
        except Exception as e:
            self.error_count += 1
            logger.error(f"[HTTPX] POST请求失败: {url} - {str(e)}")
            raise
    
    def get_stats(self) -> Dict[str, int]:
        """获取请求统计信息"""
        return {
            "request_count": self.request_count,
            "success_count": self.success_count,
            "error_count": self.error_count
        }
    
    async def close(self):
        """关闭异步客户端"""
        if hasattr(self, "client"):
            await self.client.aclose()
    
    def close_sync(self):
        """关闭同步客户端"""
        if hasattr(self, "sync_client"):
            self.sync_client.close()
    
    def reset_stats(self):
        """重置请求统计信息"""
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0

# 创建全局HTTP客户端实例
http_client = HTTPXClient()

# 提供便捷的请求函数
def get(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
    """便捷的同步GET请求函数"""
    return http_client.get(url, params=params, headers=headers, **kwargs)

def post(url: str, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
    """便捷的同步POST请求函数"""
    return http_client.post(url, json=json, data=data, headers=headers, **kwargs)

async def aget(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
    """便捷的异步GET请求函数"""
    return await http_client.aget(url, params=params, headers=headers, **kwargs)

async def apost(url: str, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
    """便捷的异步POST请求函数"""
    return await http_client.apost(url, json=json, data=data, headers=headers, **kwargs)

# 提供请求会话管理
def get_session() -> httpx.Client:
    """获取HTTP会话"""
    return http_client.get_sync_client()

async def get_async_session() -> httpx.AsyncClient:
    """获取异步HTTP会话"""
    return http_client.get_async_client()

# 提供请求重试装饰器
def retry_request(max_retries: int = 3, retry_delay: float = 1.0):
    """
    请求重试装饰器
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
    """
    import functools
    import time
    
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"[HTTPX] 请求失败，重试 {attempt+1}/{max_retries} - {str(e)}")
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # 指数退避
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"[HTTPX] 请求失败，重试 {attempt+1}/{max_retries} - {str(e)}")
                    time.sleep(retry_delay * (2 ** attempt))  # 指数退避
        
        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# 添加异步支持
import asyncio
