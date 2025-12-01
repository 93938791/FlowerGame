"""
Minecraft 加载器支持
支持 Forge、Fabric、NeoForge、OptiFine
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from utils.logger import logger
from .http_downloader import HttpDownloader


class LoaderType(Enum):
    """加载器类型"""
    FORGE = "forge"
    FABRIC = "fabric"
    NEOFORGE = "neoforge"
    OPTIFINE = "optifine"


class FabricLoader:
    """Fabric 加载器支持"""
    
    BASE_URL = "https://meta.fabricmc.net/v2"
    
    def __init__(self, downloader: HttpDownloader):
        self.downloader = downloader
    
    def get_loader_versions(self, mc_version: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定 MC 版本的 Fabric Loader 版本列表
        
        Args:
            mc_version: Minecraft 版本
            
        Returns:
            Loader 版本列表
        """
        url = f"{self.BASE_URL}/versions/loader/{mc_version}"
        
        try:
            data = self.downloader.get_json(url, use_mirror=False)
            if data:
                logger.info(f"找到 {len(data)} 个 Fabric Loader 版本")
                return data
        except Exception as e:
            logger.error(f"获取 Fabric Loader 版本失败: {e}")
        
        return None
    
    def get_profile_json(
        self,
        mc_version: str,
        loader_version: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取 Fabric 启动配置
        
        Args:
            mc_version: Minecraft 版本
            loader_version: Loader 版本
            
        Returns:
            启动配置 JSON
        """
        url = f"{self.BASE_URL}/versions/loader/{mc_version}/{loader_version}/profile/json"
        
        try:
            data = self.downloader.get_json(url, use_mirror=False)
            if data:
                logger.info(f"获取 Fabric 配置成功: {mc_version} + {loader_version}")
                return data
        except Exception as e:
            logger.error(f"获取 Fabric 配置失败: {e}")
        
        return None


class ForgeLoader:
    """Forge 加载器支持"""
    
    BASE_URL = "https://files.minecraftforge.net/net/minecraftforge/forge"
    MAVEN_URL = "https://maven.minecraftforge.net"
    BMCL_FORGE_URL = "https://bmclapi2.bangbang93.com/forge/minecraft"
    
    def __init__(self, downloader: HttpDownloader):
        self.downloader = downloader
    
    def get_version_list(self, mc_version: str) -> Optional[List[str]]:
        """
        获取指定 MC 版本的 Forge 版本列表
        
        Args:
            mc_version: Minecraft 版本
            
        Returns:
            Forge 版本列表
        """
        # 使用 BMCLAPI 镜像
        url = f"{self.BMCL_FORGE_URL}/{mc_version}"
        
        try:
            data = self.downloader.get_json(url, use_mirror=False)
            if data and isinstance(data, list):
                versions = [item.get("version") for item in data if "version" in item]
                logger.info(f"找到 {len(versions)} 个 Forge 版本")
                return versions
        except Exception as e:
            logger.error(f"获取 Forge 版本列表失败: {e}")
        
        return None
    
    def get_installer_url(self, mc_version: str, forge_version: str) -> str:
        """
        获取 Forge 安装器 URL
        
        Args:
            mc_version: Minecraft 版本
            forge_version: Forge 版本
            
        Returns:
            安装器下载 URL
        """
        full_version = f"{mc_version}-{forge_version}"
        # 使用 BMCLAPI 镜像
        return f"https://bmclapi2.bangbang93.com/forge/download/{full_version}/installer"


class NeoForgeLoader:
    """NeoForge 加载器支持"""
    
    MAVEN_URL = "https://maven.neoforged.net/releases"
    
    def __init__(self, downloader: HttpDownloader):
        self.downloader = downloader
    
    def get_version_list(self, mc_version: str) -> Optional[List[str]]:
        """
        获取 NeoForge 版本列表
        
        Args:
            mc_version: Minecraft 版本
            
        Returns:
            NeoForge 版本列表
        """
        # NeoForge 主要支持 1.20.1+
        logger.info(f"获取 NeoForge 版本列表: {mc_version}")
        # TODO: 实现 NeoForge API 调用
        return []


class OptiFineLoader:
    """OptiFine 支持"""
    
    BMCL_OPTIFINE_URL = "https://bmclapi2.bangbang93.com/optifine"
    
    def __init__(self, downloader: HttpDownloader):
        self.downloader = downloader
    
    def get_version_list(self, mc_version: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取 OptiFine 版本列表
        
        Args:
            mc_version: Minecraft 版本
            
        Returns:
            OptiFine 版本列表
        """
        url = f"{self.BMCL_OPTIFINE_URL}/{mc_version}"
        
        try:
            data = self.downloader.get_json(url, use_mirror=False)
            if data and isinstance(data, list):
                logger.info(f"找到 {len(data)} 个 OptiFine 版本")
                return data
        except Exception as e:
            logger.error(f"获取 OptiFine 版本列表失败: {e}")
        
        return None


class LoaderManager:
    """加载器管理器"""
    
    def __init__(self, downloader: HttpDownloader):
        self.downloader = downloader
        self.fabric = FabricLoader(downloader)
        self.forge = ForgeLoader(downloader)
        self.neoforge = NeoForgeLoader(downloader)
        self.optifine = OptiFineLoader(downloader)
    
    def get_loader_versions(
        self,
        loader_type: LoaderType,
        mc_version: str
    ) -> Optional[List]:
        """
        获取加载器版本列表
        
        Args:
            loader_type: 加载器类型
            mc_version: Minecraft 版本
            
        Returns:
            版本列表
        """
        if loader_type == LoaderType.FABRIC:
            return self.fabric.get_loader_versions(mc_version)
        elif loader_type == LoaderType.FORGE:
            return self.forge.get_version_list(mc_version)
        elif loader_type == LoaderType.NEOFORGE:
            return self.neoforge.get_version_list(mc_version)
        elif loader_type == LoaderType.OPTIFINE:
            return self.optifine.get_version_list(mc_version)
        
        return None
    
    def get_loader_profile(
        self,
        loader_type: LoaderType,
        mc_version: str,
        loader_version: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取加载器启动配置
        
        Args:
            loader_type: 加载器类型
            mc_version: Minecraft 版本
            loader_version: 加载器版本
            
        Returns:
            启动配置
        """
        if loader_type == LoaderType.FABRIC:
            return self.fabric.get_profile_json(mc_version, loader_version)
        
        # Forge/NeoForge 需要通过安装器安装
        logger.warning(f"{loader_type.value} 需要通过安装器安装")
        return None
