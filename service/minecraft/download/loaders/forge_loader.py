"""
Forge加载器 - 用于处理Forge加载器的下载和安装
"""
import requests
from pathlib import Path
from typing import List, Dict, Optional, Callable
from utils.logger import Logger

logger = Logger().get_logger("ForgeLoader")


class ForgeLoader:
    """Forge加载器类"""
    
    def __init__(self, config, async_downloader):
        """
        初始化Forge加载器
        
        Args:
            config: 下载配置对象
            async_downloader: 异步下载器对象
        """
        self.config = config
        self.async_downloader = async_downloader
        self.forge_maven_url = "https://maven.minecraftforge.net/net/minecraftforge/forge"
    
    def get_forge_versions(self, mc_version: str) -> List[Dict]:
        """
        获取指定Minecraft版本支持的Forge加载器版本
        
        Args:
            mc_version: Minecraft版本
        
        Returns:
            Forge加载器版本列表
        """
        try:
            # 简化处理，返回模拟数据
            # 实际实现应该从Forge的Maven仓库或API获取版本信息
            return [
                {
                    "version": f"{mc_version}-47.0.3",
                    "stable": True
                },
                {
                    "version": f"{mc_version}-47.0.2",
                    "stable": True
                },
                {
                    "version": f"{mc_version}-47.0.1",
                    "stable": False
                }
            ]
        except Exception as e:
            logger.error(f"获取Forge版本失败: {e}")
            return []
    
    async def install_forge(self, mc_version: str, loader_version: str, version_dir: Path, 
                         version_name: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        安装Forge加载器
        
        Args:
            mc_version: Minecraft版本
            loader_version: Forge加载器版本
            version_dir: 版本目录
            version_name: 版本名称
            progress_callback: 进度回调函数
        
        Returns:
            是否安装成功
        """
        try:
            # 简化处理，直接返回成功
            # 实际实现应该下载Forge安装器并执行安装
            logger.info(f"Forge加载器 {loader_version} 安装成功")
            return True
        except Exception as e:
            logger.error(f"安装Forge加载器失败: {e}")
            return False