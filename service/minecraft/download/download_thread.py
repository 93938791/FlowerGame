"""
下载线程类 - 用于处理单个文件的下载
"""
import threading
import requests
import os
import hashlib
from pathlib import Path
from typing import Optional, Callable
from utils.logger import Logger

logger = Logger().get_logger("DownloadThread")


class DownloadThread(threading.Thread):
    """下载线程类"""
    
    def __init__(self, url: str, file_path: Path, use_mirror: bool, expected_sha1: Optional[str] = None, 
                mirror_converter: Optional[Callable] = None):
        """
        初始化下载线程
        
        Args:
            url: 下载URL
            file_path: 文件路径
            use_mirror: 是否使用镜像
            expected_sha1: 期望的SHA1值
            mirror_converter: 镜像URL转换函数
        """
        super().__init__()
        self.url = url
        self.file_path = file_path
        self.use_mirror = use_mirror
        self.expected_sha1 = expected_sha1
        self.mirror_converter = mirror_converter
        self._stop_flag = False
        self.success = False
        self.error_message = ""
        # 使用自定义事件系统，因为Qt的信号槽在非Qt线程中可能有问题
        self._finished_callbacks = []
    
    def finished(self):
        """模拟Qt的信号连接机制"""
        class Signal:
            def connect(self, callback):
                self._callback = callback
            
            def emit(self, *args):
                if hasattr(self, '_callback'):
                    self._callback(*args)
        
        signal = Signal()
        self._finished_callbacks.append(signal)
        return signal
    
    def run(self):
        """线程运行方法"""
        try:
            # 确保目录存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 转换为镜像URL
            if self.use_mirror and self.mirror_converter:
                try:
                    mirrored_url = self.mirror_converter(self.url)
                    if mirrored_url != self.url:
                        logger.info(f"使用镜像URL: {mirrored_url}")
                        self.url = mirrored_url
                except Exception as e:
                    logger.warning(f"转换镜像URL失败: {e}")
            
            # 下载文件
            logger.info(f"开始下载: {self.url} -> {self.file_path}")
            
            # 使用requests下载文件
            with requests.get(self.url, stream=True, timeout=30) as response:
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                # 写入文件
                with open(self.file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        if self._stop_flag:
                            logger.info("下载已取消")
                            self.success = False
                            self.error_message = "下载已取消"
                            return
                        
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
            
            # 校验SHA1
            if self.expected_sha1:
                logger.info(f"开始SHA1校验: {self.expected_sha1}")
                sha1 = hashlib.sha1()
                with open(self.file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        sha1.update(chunk)
                actual_sha1 = sha1.hexdigest()
                
                if actual_sha1.lower() != self.expected_sha1.lower():
                    logger.error(f"SHA1校验失败: 期望 {self.expected_sha1}, 实际 {actual_sha1}")
                    self.success = False
                    self.error_message = f"SHA1校验失败: 期望 {self.expected_sha1}, 实际 {actual_sha1}"
                    # 删除下载的文件
                    self.file_path.unlink()
                    return
            
            logger.info(f"下载成功: {self.file_path}")
            self.success = True
            self.error_message = ""
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self.success = False
            self.error_message = str(e)
            # 删除可能不完整的文件
            if self.file_path.exists():
                self.file_path.unlink()
        finally:
            # 触发所有回调
            for callback in self._finished_callbacks:
                callback.emit(self.success, self.error_message)
    
    def stop(self):
        """停止下载"""
        self._stop_flag = True
    
    def wait(self, timeout=None):
        """等待线程完成"""
        self.join(timeout)
    
    @property
    def is_running(self):
        """检查线程是否正在运行"""
        return self.is_alive()