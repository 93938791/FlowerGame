"""
下载配置类 - 管理下载服务的配置参数
"""
from pathlib import Path
from typing import Dict, Any

class DownloadConfig:
    """下载配置类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化下载配置
        
        Args:
            config: 配置字典
        """
        # 从配置字典中获取必要的配置项，设置默认值
        self.minecraft_dir = Path(config.get("minecraft_dir", Path.home() / ".minecraft"))
        self.use_mirror = config.get("use_mirror", True)
        self.BMCLAPI_DOMAIN = config.get("BMCLAPI_DOMAIN", "bmclapi2.bangbang93.com")
        self.VERSION_MANIFEST_URL = config.get("VERSION_MANIFEST_URL", "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
        self.CACHE_TIMEOUT = config.get("CACHE_TIMEOUT", 300)  # 缓存超时时间（秒）
        self.DOWNLOAD_THREADS = config.get("DOWNLOAD_THREADS", 10)  # 下载线程数
        self.CHUNK_SIZE = config.get("CHUNK_SIZE", 1024 * 1024)  # 下载块大小
        self.TIMEOUT = config.get("TIMEOUT", 30)  # 下载超时时间（秒）
        self.RETRY_COUNT = config.get("RETRY_COUNT", 3)  # 重试次数
        self.BACKOFF_FACTOR = config.get("BACKOFF_FACTOR", 0.5)  # 重试退避因子
        
        # 确保必要的目录存在
        self.minecraft_dir.mkdir(parents=True, exist_ok=True)
        (self.minecraft_dir / "libraries").mkdir(parents=True, exist_ok=True)
        (self.minecraft_dir / "assets").mkdir(parents=True, exist_ok=True)
        (self.minecraft_dir / "versions").mkdir(parents=True, exist_ok=True)