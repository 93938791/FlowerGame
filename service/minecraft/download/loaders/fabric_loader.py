"""
Fabric加载器 - 用于处理Fabric加载器的下载和安装
"""
import requests
import json
from pathlib import Path
from typing import List, Dict, Optional, Callable
from utils.logger import Logger

logger = Logger().get_logger("FabricLoader")


class FabricLoader:
    """Fabric加载器类"""
    
    def __init__(self, config, async_downloader):
        """
        初始化Fabric加载器
        
        Args:
            config: 下载配置对象
            async_downloader: 异步下载器对象
        """
        self.config = config
        self.async_downloader = async_downloader
        self.fabric_meta_url = "https://meta.fabricmc.net/v2"
    
    def get_fabric_versions(self, mc_version: str) -> List[Dict]:
        """
        获取指定Minecraft版本支持的Fabric加载器版本
        
        Args:
            mc_version: Minecraft版本
        
        Returns:
            Fabric加载器版本列表
        """
        try:
            # 获取所有Fabric加载器版本
            versions_url = f"{self.fabric_meta_url}/versions/loader"
            response = requests.get(versions_url, timeout=10)
            response.raise_for_status()
            
            all_versions = response.json()
            
            # 过滤出支持指定Minecraft版本的加载器版本
            supported_versions = []
            for version in all_versions:
                version_info = {
                    "version": version["version"],
                    "stable": version["stable"],
                    "mc_versions": [mc["version"] for mc in version["game_versions"]]
                }
                if mc_version in version_info["mc_versions"]:
                    supported_versions.append(version_info)
            
            return supported_versions
        except Exception as e:
            logger.error(f"获取Fabric版本失败: {e}")
            return []
    
    def get_fabric_api_versions(self, mc_version: str) -> List[Dict]:
        """
        获取指定Minecraft版本支持的Fabric API版本
        
        Args:
            mc_version: Minecraft版本
        
        Returns:
            Fabric API版本列表
        """
        try:
            # 获取所有Fabric API版本
            api_versions_url = f"{self.fabric_meta_url}/versions/modloader/fabric"
            response = requests.get(api_versions_url, timeout=10)
            response.raise_for_status()
            
            all_versions = response.json()
            
            # 简化处理，返回所有版本
            return [{
                "version": version["version"],
                "stable": version["stable"]
            } for version in all_versions]
        except Exception as e:
            logger.error(f"获取Fabric API版本失败: {e}")
            return []
    
    async def install_fabric(self, mc_version: str, loader_version: str, version_dir: Path, 
                          version_name: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        安装Fabric加载器
        
        Args:
            mc_version: Minecraft版本
            loader_version: Fabric加载器版本
            version_dir: 版本目录
            version_name: 版本名称
            progress_callback: 进度回调函数
        
        Returns:
            是否安装成功
        """
        try:
            # 获取Fabric安装器元数据
            installer_url = f"{self.fabric_meta_url}/versions/loader/{mc_version}/{loader_version}/profile/json"
            response = requests.get(installer_url, timeout=10)
            response.raise_for_status()
            
            profile_data = response.json()
            
            # 保存版本JSON文件
            version_json_path = version_dir / f"{version_name}.json"
            with open(version_json_path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Fabric加载器 {loader_version} 安装成功")
            return True
        except Exception as e:
            logger.error(f"安装Fabric加载器失败: {e}")
            return False