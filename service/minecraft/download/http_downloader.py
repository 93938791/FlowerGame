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


def verify_file_integrity(file_path: Path, sha1: Optional[str] = None, size: Optional[int] = None) -> bool:
    """
    校验文件完整性（独立函数）
    
    Args:
        file_path: 文件路径
        sha1: 期望的 SHA1 值
        size: 期望的文件大小
        
    Returns:
        校验是否通过
    """
    if not file_path.exists():
        return False
        
    if size is not None and size > 0:
        if file_path.stat().st_size != size:
            return False
            
    if sha1:
        try:
            hasher = hashlib.sha1()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest().lower() == sha1.lower()
        except Exception as e:
            logger.warning(f"校验文件异常: {e}")
            return False
            
    return True


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
    

    def verify_file(self, file_path: Path, sha1: Optional[str] = None, size: Optional[int] = None) -> bool:
        """校验文件完整性（代理到全局函数）"""
        return verify_file_integrity(file_path, sha1, size)

    def download_file(
        self,
        url: str,
        save_path: Path,
        sha1: Optional[str] = None,
        size: Optional[int] = None,
        use_mirror: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        下载单个文件，支持自动重试和镜像切换
        
        Args:
            url: 下载 URL
            save_path: 保存路径
            sha1: 文件 SHA1 校验码
            size: 文件大小（可选，用于进度显示）
            use_mirror: 是否使用镜像加速
            progress_callback: 进度回调
            
        Returns:
            是否下载成功
        """
        if not url:
            logger.error("下载 URL 为空")
            return False
            
        # 1. 检查文件是否已存在且完整
        # 使用全局函数进行校验，避免 self.verify_file 可能的属性丢失问题
        if verify_file_integrity(save_path, sha1, size):
            if progress_callback and size:
                progress_callback(size, size)
            return True
            
        # 2. 准备下载
        save_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = save_path.with_suffix(save_path.suffix + ".part")
        
        # 3. 获取下载 URL（镜像）
        download_url = url
        if use_mirror and self.mirror_manager:
            download_url = self.mirror_manager.get_download_url(url)
        logger.info(f"下载源: {self.mirror_manager.current_source.name if self.mirror_manager else 'unknown'}, URL: {download_url}")
            
        # 4. 执行下载（带重试）
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                import time
                # 线性退避
                if retry_count > 0:
                    wait_time = 2 * retry_count
                    time.sleep(wait_time)
                
                # 使用流式下载
                with self.client.stream("GET", download_url, follow_redirects=True, timeout=60.0) as response:
                    if response.status_code != 200:
                        # 如果是 404 或其他错误，尝试切换镜像源
                        if self.mirror_manager and use_mirror:
                            logger.warning(f"下载失败 {response.status_code}，尝试切换镜像源...")
                            if self.mirror_manager.switch_to_fallback():
                                download_url = self.mirror_manager.get_download_url(url)
                                logger.info(f"已切换到: {self.mirror_manager.current_source.name}, URL: {download_url}")
                                continue
                        
                        raise Exception(f"HTTP {response.status_code}")
                    
                    total_size = int(response.headers.get("content-length", 0)) or size or 0
                    downloaded_size = 0
                    
                    with open(temp_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                if progress_callback:
                                    progress_callback(downloaded_size, total_size)
                
                # 5. 下载完成，校验文件
                if verify_file_integrity(temp_path, sha1, size):
                    if save_path.exists():
                        save_path.unlink()
                    temp_path.rename(save_path)
                    return True
                else:
                    logger.warning(f"文件校验失败: {save_path.name} (重试 {retry_count+1}/{max_retries})")
                    retry_count += 1
                    
            except Exception as e:
                logger.warning(f"下载异常: {e} (重试 {retry_count+1}/{max_retries}) - {download_url}")
                retry_count += 1
                
                # 如果多次失败，尝试切换镜像源
                if retry_count >= 2 and self.mirror_manager and use_mirror:
                    if self.mirror_manager.switch_to_fallback():
                        download_url = self.mirror_manager.get_download_url(url)
                        logger.info(f"多次失败，切换到镜像源: {self.mirror_manager.current_source.name}, URL: {download_url}")
        
        # 清理临时文件
        if temp_path.exists():
            temp_path.unlink()
            
        logger.error(f"文件下载最终失败: {save_path.name}")
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
        download_url = self.mirror_manager.get_download_url(url) if use_mirror else url
        
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
