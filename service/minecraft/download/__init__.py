"""
Minecraft 下载模块

提供高效的 Minecraft 版本下载功能：
- 基于 httpx[http2] 的高速下载
- 连接池复用，避免重复建立连接
- 自动镜像加速（BMCLAPI、MCBBS）
- 支持原版和加载器版本（Forge、Fabric、NeoForge、OptiFine）
- 完整的进度回调和错误处理

使用示例：
    from service.minecraft.download import MinecraftDownloadManager, LoaderType
    
    # 下载原版
    manager = MinecraftDownloadManager()
    manager.download_vanilla("1.20.1")
    
    # 下载 Fabric 版本
    manager.download_with_loader("1.20.1", LoaderType.FABRIC, "0.15.11")
    
    # 列出所有版本
    versions = manager.list_versions("release")
"""

from .download_manager import MinecraftDownloadManager, DownloadProgress
from .loader_support import LoaderType, LoaderManager
from .mirror_utils import MirrorManager, MirrorSource
from .version_manifest import VersionManifest
from .version_info import VersionInfo, RuleEvaluator
from .http_downloader import HttpDownloader, DownloadTask

__all__ = [
    # 主要接口
    "MinecraftDownloadManager",
    "DownloadProgress",
    
    # 加载器支持
    "LoaderType",
    "LoaderManager",
    
    # 镜像管理
    "MirrorManager",
    "MirrorSource",
    
    # 版本管理
    "VersionManifest",
    "VersionInfo",
    "RuleEvaluator",
    
    # 下载器
    "HttpDownloader",
    "DownloadTask",
]
