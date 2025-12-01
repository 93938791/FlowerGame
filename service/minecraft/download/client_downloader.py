"""
Minecraft 客户端 JAR 下载器
"""
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from utils.logger import logger
from .http_downloader import HttpDownloader


class ClientDownloader:
    """客户端 JAR 下载器"""
    
    def __init__(self, minecraft_dir: Path, downloader: HttpDownloader):
        """
        初始化客户端下载器
        
        Args:
            minecraft_dir: Minecraft 根目录
            downloader: HTTP 下载器
        """
        self.minecraft_dir = minecraft_dir
        self.downloader = downloader
    
    def download_client(
        self,
        version_id: str,
        client_info: Dict[str, Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        下载客户端 JAR
        
        Args:
            version_id: 版本 ID
            client_info: 客户端下载信息（从版本 JSON 获取）
            progress_callback: 进度回调 (downloaded_bytes, total_bytes)
            
        Returns:
            是否下载成功
        """
        url = client_info.get("url")
        sha1 = client_info.get("sha1")
        size = client_info.get("size", 0)
        
        if not url:
            logger.error("客户端下载信息不完整")
            return False
        
        # 保存路径
        version_dir = self.minecraft_dir / "versions" / version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        jar_path = version_dir / f"{version_id}.jar"
        
        logger.info(f"开始下载客户端 JAR: {version_id} ({size / 1024 / 1024:.2f} MB)")
        
        # 下载文件
        success = self.downloader.download_file(
            url=url,
            save_path=jar_path,
            sha1=sha1,
            use_mirror=True,
            progress_callback=progress_callback
        )
        
        if success:
            logger.info(f"✓ 客户端 JAR 下载成功: {jar_path}")
        else:
            logger.error(f"✗ 客户端 JAR 下载失败")
        
        return success
