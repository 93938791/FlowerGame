"""
下载服务 - 处理游戏版本、加载器、模组等资源的下载
"""

# 从独立的业务文件中导出DownloadService类
from .download_service import DownloadService

# 导出所有相关类，方便外部使用
from .download_config import DownloadConfig
from .async_http2_downloader import AsyncHTTP2Downloader
from .download_thread import DownloadThread
from .mirror_utils import MirrorUtils
from .modrinth_client import ModrinthClient

# 导出加载器类
from .loaders.fabric_loader import FabricLoader
from .loaders.forge_loader import ForgeLoader
from .loaders.neoforge_loader import NeoForgeLoader
from .loaders.optifine_loader import OptiFineLoader

# 定义包的公共API
__all__ = [
    "DownloadService",
    "DownloadConfig",
    "AsyncHTTP2Downloader",
    "DownloadThread",
    "MirrorUtils",
    "ModrinthClient",
    "FabricLoader",
    "ForgeLoader",
    "NeoForgeLoader",
    "OptiFineLoader"
]