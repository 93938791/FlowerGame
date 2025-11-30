"""
HTTP/2异步下载器 - 支持多线程下载和断点续传
"""
import asyncio
import aiohttp
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Callable
from utils.logger import Logger

logger = Logger().get_logger("AsyncHTTP2Downloader")


class AsyncHTTP2Downloader:
    """HTTP/2异步下载器"""
    
    def __init__(self, config):
        """
        初始化异步下载器
        
        Args:
            config: 下载配置对象
        """
        self.config = config
        self.session = None
    
    async def _create_session(self):
        """创建aiohttp会话"""
        if not self.session or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.config.DOWNLOAD_THREADS,
                enable_cleanup_closed=True
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.config.TIMEOUT)
            )
        return self.session
    
    async def _close_session(self):
        """关闭aiohttp会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _download_chunk(self, url: str, start: int, end: int, file_path: Path, chunk_index: int, 
                            progress_callback: Optional[Callable] = None, task_id: str = None):
        """
        下载文件的一个块
        
        Args:
            url: 下载URL
            start: 块开始位置
            end: 块结束位置
            file_path: 文件路径
            chunk_index: 块索引
            progress_callback: 进度回调函数
            task_id: 任务ID
        """
        headers = {"Range": f"bytes={start}-{end}"}
        session = await self._create_session()
        
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                
                # 计算块大小
                chunk_size = end - start + 1
                downloaded = 0
                
                # 写入文件
                with open(file_path, "r+b") as f:
                    f.seek(start)
                    async for chunk in response.content.iter_chunked(self.config.CHUNK_SIZE):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 调用进度回调
                        if progress_callback:
                            await asyncio.to_thread(progress_callback, downloaded, chunk_size, f"块 {chunk_index+1} 下载中", task_id)
        except Exception as e:
            logger.error(f"下载块 {chunk_index+1} 失败: {e}")
            raise
    
    async def _download_file(self, url: str, file_path: Path, expected_sha1: Optional[str] = None, 
                           progress_callback: Optional[Callable] = None, task_id: str = None):
        """
        下载单个文件
        
        Args:
            url: 下载URL
            file_path: 文件路径
            expected_sha1: 期望的SHA1值（用于校验）
            progress_callback: 进度回调函数
            task_id: 任务ID
        """
        session = await self._create_session()
        
        try:
            # 获取文件大小
            async with session.head(url) as response:
                response.raise_for_status()
                file_size = int(response.headers.get("content-length", 0))
            
            # 创建文件并设置大小
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                f.truncate(file_size)
            
            # 计算分块
            chunk_size = max(1, file_size // self.config.DOWNLOAD_THREADS)
            chunks = []
            for i in range(self.config.DOWNLOAD_THREADS):
                start = i * chunk_size
                end = min((i + 1) * chunk_size - 1, file_size - 1)
                if start < file_size:
                    chunks.append((start, end, i))
            
            # 下载所有块
            tasks = []
            for start, end, i in chunks:
                task = asyncio.create_task(
                    self._download_chunk(url, start, end, file_path, i, progress_callback, task_id)
                )
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            # 校验SHA1
            if expected_sha1:
                sha1 = hashlib.sha1()
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha1.update(chunk)
                actual_sha1 = sha1.hexdigest()
                
                if actual_sha1.lower() != expected_sha1.lower():
                    logger.error(f"SHA1校验失败: 期望 {expected_sha1}, 实际 {actual_sha1}")
                    file_path.unlink()
                    raise ValueError(f"SHA1校验失败: 期望 {expected_sha1}, 实际 {actual_sha1}")
            
            return True
        except Exception as e:
            logger.error(f"下载文件 {file_path.name} 失败: {e}")
            if file_path.exists():
                file_path.unlink()
            return False
    
    async def _batch_download_async(self, tasks: List[Dict], progress_callback: Optional[Callable] = None):
        """
        异步批量下载文件
        
        Args:
            tasks: 下载任务列表，每个任务包含url、file_path和optional expected_sha1
            progress_callback: 进度回调函数
        
        Returns:
            Tuple[int, int]: (成功数量, 失败数量)
        """
        success_count = 0
        failed_count = 0
        
        try:
            # 并行下载所有文件
            download_tasks = []
            for i, task in enumerate(tasks):
                url = task["url"]
                file_path = Path(task["file_path"])
                expected_sha1 = task.get("expected_sha1")
                
                # 创建下载任务
                download_task = asyncio.create_task(
                    self._download_file(url, file_path, expected_sha1, progress_callback, f"task_{i}")
                )
                download_tasks.append(download_task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
            
            # 统计结果
            for result in results:
                if result is True:
                    success_count += 1
                else:
                    failed_count += 1
        except Exception as e:
            logger.error(f"批量下载失败: {e}")
            failed_count += len(tasks) - success_count
        finally:
            await self._close_session()
        
        return success_count, failed_count
    
    def batch_download(self, tasks: List[Dict], progress_callback: Optional[Callable] = None):
        """
        批量下载文件（同步接口）
        
        Args:
            tasks: 下载任务列表，每个任务包含url、file_path和optional expected_sha1
            progress_callback: 进度回调函数
        
        Returns:
            Tuple[int, int]: (成功数量, 失败数量)
        """
        try:
            # 运行异步下载
            return asyncio.run(self._batch_download_async(tasks, progress_callback))
        except Exception as e:
            logger.error(f"批量下载失败: {e}")
            return 0, len(tasks)