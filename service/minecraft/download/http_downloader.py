"""
基于 httpx[http2] 的高效下载器
使用连接池复用，支持断点续传和重试机制
"""
import httpx
import hashlib
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor, Future
from utils.logger import logger
from .mirror_utils import MirrorManager, MirrorSource


class DownloadTask:
    """下载任务"""
    
    def __init__(
        self,
        url: str,
        save_path: Path,
        sha1: Optional[str] = None,
        description: Optional[str] = None
    ):
        self.url = url
        self.save_path = save_path
        self.sha1 = sha1
        self.description = description or url
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.status = "pending"  # pending, downloading, completed, failed
        self.error: Optional[str] = None


class HttpDownloader:
    """HTTP/2 下载器（基于 httpx）"""
    
    def __init__(
        self,
        max_connections: int = 50,
        timeout: int = 30,
        max_retries: int = 3,
        mirror_manager: Optional[MirrorManager] = None
    ):
        """
        初始化下载器
        
        Args:
            max_connections: 最大并发连接数
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            mirror_manager: 镜像管理器
        """
        self.max_connections = max_connections
        self.timeout = timeout
        self.max_retries = max_retries
        self.mirror_manager = mirror_manager or MirrorManager()
        
        # 创建 httpx 客户端（启用 HTTP/2 和连接池）
        self.client = httpx.Client(
            http2=True,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=20
            ),
            follow_redirects=True
        )
        
        # 线程池用于并发下载
        self.executor = ThreadPoolExecutor(max_workers=max_connections)
        
        # 下载统计
        self.total_downloaded = 0
        self.total_failed = 0
        self.total_skipped = 0  # 跳过的文件数
    
    def download_file(
        self,
        url: str,
        save_path: Path,
        sha1: Optional[str] = None,
        use_mirror: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        下载单个文件（同步方法）
        
        Args:
            url: 下载地址
            save_path: 保存路径
            sha1: SHA1 校验值
            use_mirror: 是否使用镜像加速
            progress_callback: 进度回调 (downloaded_bytes, total_bytes)
            
        Returns:
            是否下载成功
        """
        # logger.info(f"📥 开始下载: {save_path.name}")
        
        # 确保父目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)
        # logger.debug(f"✓ 目录已创建: {save_path.parent}")
        
        # 如果文件已存在且校验通过，跳过下载
        if save_path.exists() and sha1:
            if self._verify_sha1(save_path, sha1):
                # logger.debug(f"文件已存在且校验通过，跳过下载: {save_path.name}")
                self.total_skipped += 1
                return True
            else:
                logger.warning(f"文件校验失败，重新下载: {save_path.name}")
                save_path.unlink()
        
        # 获取下载 URL（使用镜像）
        download_url = self.mirror_manager.convert_url(url) if use_mirror else url
        # logger.info(f"🔗 下载地址: {download_url}")
        
        # 重试机制
        for attempt in range(self.max_retries):
            try:
                # 发送请求
                with self.client.stream("GET", download_url) as response:
                    # 检查 429 错误，切换到官方源
                    if response.status_code == 429:
                        logger.warning(f"遇到 429 限流，切换到官方源重试: {save_path.name}")
                        download_url = url  # 使用原始 URL（官方源）
                        continue
                    
                    response.raise_for_status()
                    
                    # 获取文件大小
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded_size = 0
                    
                    # 分块下载并写入
                    with open(save_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 调用进度回调
                            if progress_callback:
                                progress_callback(downloaded_size, total_size)
                
                # 校验 SHA1
                if sha1 and not self._verify_sha1(save_path, sha1):
                    logger.error(f"文件 SHA1 校验失败: {save_path.name}")
                    save_path.unlink()
                    
                    if attempt < self.max_retries - 1:
                        logger.info(f"第 {attempt + 1} 次重试下载...")
                        continue
                    return False
                
                self.total_downloaded += 1
                return True
            
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP 错误 {e.response.status_code}: {save_path.name}")
                if attempt < self.max_retries - 1:
                    logger.info(f"第 {attempt + 1} 次重试下载...")
                    continue
            
            except Exception as e:
                logger.error(f"下载失败: {save_path.name}, 错误: {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"第 {attempt + 1} 次重试下载...")
                    continue
        
        # 所有重试都失败
        self.total_failed += 1
        if save_path.exists():
            save_path.unlink()
        return False
    
    def download_batch(
        self,
        tasks: list[DownloadTask],
        progress_callback: Optional[Callable[[DownloadTask], None]] = None
    ) -> Dict[str, Any]:
        """
        批量下载文件（并发）
        
        Args:
            tasks: 下载任务列表
            progress_callback: 任务完成回调
            
        Returns:
            下载统计信息
        """
        futures: Dict[Future, DownloadTask] = {}
        
        # 提交所有任务到线程池
        for task in tasks:
            future = self.executor.submit(
                self._download_task_wrapper,
                task
            )
            futures[future] = task
        
        # 等待所有任务完成
        completed = 0
        failed = 0
        
        for future in futures:
            task = futures[future]
            try:
                success = future.result()
                if success:
                    task.status = "completed"
                    completed += 1
                else:
                    task.status = "failed"
                    failed += 1
                
                # 调用回调
                if progress_callback:
                    progress_callback(task)
            
            except Exception as e:
                logger.error(f"任务执行异常: {task.description}, 错误: {e}")
                task.status = "failed"
                task.error = str(e)
                failed += 1
        
        return {
            "total": len(tasks),
            "completed": completed,
            "failed": failed,
            "success_rate": completed / len(tasks) if tasks else 0
        }
    
    def _download_task_wrapper(self, task: DownloadTask) -> bool:
        """下载任务包装器"""
        task.status = "downloading"
        
        def task_progress(downloaded, total):
            task.downloaded_bytes = downloaded
            task.total_bytes = total
        
        success = self.download_file(
            task.url,
            task.save_path,
            task.sha1,
            progress_callback=task_progress
        )
        
        return success
    
    def _verify_sha1(self, file_path: Path, expected_sha1: str) -> bool:
        """验证文件 SHA1"""
        try:
            sha1 = hashlib.sha1()
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha1.update(chunk)
            return sha1.hexdigest().lower() == expected_sha1.lower()
        except Exception as e:
            logger.error(f"SHA1 校验异常: {e}")
            return False
    
    def get_json(self, url: str, use_mirror: bool = True) -> Optional[dict]:
        """
        获取 JSON 数据
        
        Args:
            url: 请求地址
            use_mirror: 是否使用镜像
            
        Returns:
            JSON 数据，失败返回 None
        """
        download_url = self.mirror_manager.convert_url(url) if use_mirror else url
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.get(download_url)
                
                # 429 错误切换官方源
                if response.status_code == 429:
                    logger.warning("遇到 429 限流，切换到官方源")
                    download_url = url
                    continue
                
                response.raise_for_status()
                return response.json()
            
            except Exception as e:
                logger.error(f"获取 JSON 失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    continue
        
        return None
    
    def close(self):
        """关闭下载器，释放资源"""
        self.client.close()
        self.executor.shutdown(wait=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
