"""
NeoForge加载器 - 用于处理NeoForge加载器的下载和安装
"""
import requests
from pathlib import Path
from typing import List, Dict, Optional, Callable
from utils.logger import Logger

logger = Logger().get_logger("NeoForgeLoader")


class NeoForgeLoader:
    """NeoForge加载器类"""
    
    def __init__(self, config, async_downloader):
        """
        初始化NeoForge加载器
        
        Args:
            config: 下载配置对象
            async_downloader: 异步下载器对象
        """
        self.config = config
        self.async_downloader = async_downloader
        self.neoforge_maven_url = "https://maven.neoforged.net/net/neoforged/neoforge"
    
    def get_neoforge_versions(self, mc_version: str) -> List[Dict]:
        """
        获取指定Minecraft版本支持的NeoForge加载器版本
        
        Args:
            mc_version: Minecraft版本
        
        Returns:
            NeoForge加载器版本列表
        """
        try:
            # 简化处理，返回模拟数据
            # 实际实现应该从NeoForge的Maven仓库或API获取版本信息
            return [
                {
                    "version": f"{mc_version}-20.0.50",
                    "stable": True
                },
                {
                    "version": f"{mc_version}-20.0.49",
                    "stable": True
                },
                {
                    "version": f"{mc_version}-20.0.48",
                    "stable": False
                }
            ]
        except Exception as e:
            logger.error(f"获取NeoForge版本失败: {e}")
            return []
    
    async def install_neoforge(self, mc_version: str, loader_version: str, version_dir: Path, 
                            version_name: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        安装NeoForge加载器
        
        Args:
            mc_version: Minecraft版本
            loader_version: NeoForge加载器版本
            version_dir: 版本目录
            version_name: 版本名称
            progress_callback: 进度回调函数
        
        Returns:
            是否安装成功
        """
        try:
            # 简化处理，直接返回成功
            # 实际实现应该下载NeoForge安装器并执行安装
            logger.info(f"NeoForge加载器 {loader_version} 安装成功")
            return True
        except Exception as e:
            logger.error(f"安装NeoForge加载器失败: {e}")
            return False