"""
Minecraft 加载器支持
支持 Forge、Fabric、NeoForge、OptiFine
"""
import json
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
            # 使用镜像加速
            data = self.downloader.get_json(url, use_mirror=True)
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
            # 使用镜像加速
            data = self.downloader.get_json(url, use_mirror=True)
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
    BMCL_MAVEN = "https://bmclapi2.bangbang93.com/maven"  # BMCL Maven镜像
    
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
        # 使用 BMCL Maven 镜像（标准Maven格式）
        return f"{self.BMCL_MAVEN}/net/minecraftforge/forge/{full_version}/forge-{full_version}-installer.jar"
    
    def get_profile_json(self, mc_version: str, forge_version: str) -> Optional[Dict[str, Any]]:
        """
        获取 Forge 启动配置（通过解析安装器）
        参考HMCL的实现：
        - 旧型安装器（1.12.2-）：有install和versionInfo字段
        - 新型安装器（1.13+）：有spec字段和processors
        
        Args:
            mc_version: Minecraft 版本
            forge_version: Forge 版本
            
        Returns:
            Forge 启动配置JSON
        """
        import zipfile
        import tempfile
        from pathlib import Path
        
        full_version = f"{mc_version}-{forge_version}"
        logger.info(f"🔧 获取 Forge {full_version} 配置...")
        
        try:
            # 1. 下载安装器到临时目录
            installer_url = self.get_installer_url(mc_version, forge_version)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                installer_path = Path(temp_dir) / "forge-installer.jar"
                
                logger.info(f"📥 下载 Forge 安装器: {installer_url}")
                success = self.downloader.download_file(
                    url=installer_url,
                    save_path=installer_path,
                    use_mirror=False
                )
                
                if not success:
                    logger.error("Forge 安装器下载失败")
                    return None
                
                # 2. 解压安装器，读取配置文件
                logger.info("📦 解析 Forge 安装器...")
                with zipfile.ZipFile(installer_path, 'r') as jar:
                    # 读取install_profile.json
                    if 'install_profile.json' not in jar.namelist():
                        logger.error("安装器中未找到 install_profile.json")
                        return None
                    
                    install_profile_text = jar.read('install_profile.json').decode('utf-8')
                    install_profile = json.loads(install_profile_text)
                    
                    # 判断安装器类型
                    if 'spec' in install_profile:
                        # 新型安装器（Forge 1.13+）
                        logger.info("🆕 检测到新型 Forge 安装器 (1.13+)")
                        
                        # 读取version.json
                        if 'version.json' not in jar.namelist():
                            logger.error("新型安装器中未找到 version.json")
                            return None
                        
                        version_json = json.loads(jar.read('version.json').decode('utf-8'))
                        logger.info(f"✅ 成功解析 Forge 配置: {version_json.get('id')}")
                        
                        return {
                            "version": version_json,
                            "install_profile": install_profile,
                            "installer_type": "new"  # 新型安装器
                        }
                    
                    elif 'install' in install_profile and 'versionInfo' in install_profile:
                        # 旧型安装器（Forge 1.12.2及以下）
                        logger.info("📜 检测到旧型 Forge 安装器 (1.12.2-)")
                        
                        # 旧型安装器直接使用versionInfo作为version.json
                        version_json = install_profile['versionInfo']
                        logger.info(f"✅ 成功解析 Forge 配置: {version_json.get('id')}")
                        
                        return {
                            "version": version_json,
                            "install_profile": install_profile,
                            "installer_type": "legacy"  # 旧型安装器
                        }
                    
                    else:
                        logger.error("无法识别的 Forge 安装器格式")
                        return None
        
        except Exception as e:
            logger.error(f"获取 Forge 配置失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return None


class NeoForgeLoader:
    """NeoForge 加载器支持"""
    
    MAVEN_URL = "https://maven.neoforged.net/releases"
    # NeoForge 版本 API
    VERSION_API = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge"
    # BMCLAPI 镜像
    BMCL_MAVEN = "https://bmclapi2.bangbang93.com/maven"
    
    def __init__(self, downloader: HttpDownloader):
        self.downloader = downloader
    
    def get_version_list(self, mc_version: str) -> Optional[List[str]]:
        """
        获取指定 MC 版本的 NeoForge 版本列表
        
        NeoForge 版本命名规则：
        - 1.20.1: 47.1.x (基于 Forge)
        - 1.20.2+: 20.2.x, 20.3.x, 20.4.x... (新命名)
        - 1.21.x: 21.0.x, 21.1.x...
        
        Args:
            mc_version: Minecraft 版本
            
        Returns:
            NeoForge 版本列表
        """
        logger.info(f"获取 NeoForge 版本列表: {mc_version}")
        
        try:
            # 获取所有 NeoForge 版本
            data = self.downloader.get_json(self.VERSION_API, use_mirror=False)
            if not data or "versions" not in data:
                logger.error("NeoForge API 返回数据无效")
                return None
            
            all_versions = data.get("versions", [])
            
            # 根据 MC 版本过滤
            # NeoForge 版本格式：
            # - 1.20.1: 47.1.x
            # - 1.20.2: 20.2.x
            # - 1.20.4: 20.4.x
            # - 1.21: 21.0.x
            # - 1.21.1: 21.1.x
            
            filtered_versions = []
            
            # 解析 MC 版本
            mc_parts = mc_version.split(".")
            if len(mc_parts) < 2:
                return None
            
            mc_major = int(mc_parts[0])  # 1
            mc_minor = int(mc_parts[1])  # 20, 21
            mc_patch = int(mc_parts[2]) if len(mc_parts) > 2 else 0  # 1, 2, 4...
            
            for version in all_versions:
                # NeoForge 版本格式: major.minor.patch 或 major.minor.patch-beta
                nf_parts = version.replace("-beta", "").split(".")
                if len(nf_parts) < 2:
                    continue
                
                try:
                    nf_major = int(nf_parts[0])
                    nf_minor = int(nf_parts[1])
                    
                    # 特殊处理 1.20.1 (使用 Forge 47.x 系列)
                    if mc_version == "1.20.1" and nf_major == 47:
                        filtered_versions.append(version)
                    # 1.20.2+ 使用新命名 (20.x)
                    elif mc_minor == 20 and mc_patch >= 2:
                        if nf_major == 20 and nf_minor == mc_patch:
                            filtered_versions.append(version)
                    # 1.21.x 使用 21.x
                    elif mc_minor == 21:
                        if nf_major == 21 and nf_minor == mc_patch:
                            filtered_versions.append(version)
                except ValueError:
                    continue
            
            # 按版本号排序（最新在前）
            filtered_versions.sort(reverse=True, key=lambda v: [int(x) for x in v.replace("-beta", "").split(".")[:3]])
            
            logger.info(f"找到 {len(filtered_versions)} 个 NeoForge 版本")
            return filtered_versions
            
        except Exception as e:
            logger.error(f"获取 NeoForge 版本列表失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_installer_url(self, neoforge_version: str, use_mirror: bool = True) -> str:
        """
        获取 NeoForge 安装器 URL
        
        Args:
            neoforge_version: NeoForge 版本
            use_mirror: 是否使用镜像
            
        Returns:
            安装器下载 URL
        """
        if use_mirror:
            return f"{self.BMCL_MAVEN}/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}-installer.jar"
        return f"{self.MAVEN_URL}/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}-installer.jar"
    
    def get_profile_json(self, mc_version: str, neoforge_version: str) -> Optional[Dict[str, Any]]:
        """
        获取 NeoForge 启动配置（通过解析安装器）
        与 Forge 类似，NeoForge 也使用安装器格式
        
        Args:
            mc_version: Minecraft 版本
            neoforge_version: NeoForge 版本
            
        Returns:
            NeoForge 启动配置JSON
        """
        import zipfile
        import tempfile
        from pathlib import Path
        
        logger.info(f"🔧 获取 NeoForge {neoforge_version} 配置...")
        
        try:
            # 1. 下载安装器到临时目录
            installer_url = self.get_installer_url(neoforge_version, use_mirror=True)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                installer_path = Path(temp_dir) / "neoforge-installer.jar"
                
                logger.info(f"📥 下载 NeoForge 安装器: {installer_url}")
                success = self.downloader.download_file(
                    url=installer_url,
                    save_path=installer_path,
                    use_mirror=False
                )
                
                if not success:
                    # 尝试官方源
                    installer_url = self.get_installer_url(neoforge_version, use_mirror=False)
                    logger.info(f"📥 尝试官方源: {installer_url}")
                    success = self.downloader.download_file(
                        url=installer_url,
                        save_path=installer_path,
                        use_mirror=False
                    )
                    
                    if not success:
                        logger.error("NeoForge 安装器下载失败")
                        return None
                
                # 2. 解压安装器，读取配置文件
                logger.info("📦 解析 NeoForge 安装器...")
                with zipfile.ZipFile(installer_path, 'r') as jar:
                    # 读取 install_profile.json
                    if 'install_profile.json' not in jar.namelist():
                        logger.error("安装器中未找到 install_profile.json")
                        return None
                    
                    install_profile_text = jar.read('install_profile.json').decode('utf-8')
                    install_profile = json.loads(install_profile_text)
                    
                    # NeoForge 使用新型安装器格式（与 Forge 1.13+ 相同）
                    if 'version.json' not in jar.namelist():
                        logger.error("安装器中未找到 version.json")
                        return None
                    
                    version_json = json.loads(jar.read('version.json').decode('utf-8'))
                    logger.info(f"✅ 成功解析 NeoForge 配置: {version_json.get('id')}")
                    
                    return {
                        "version": version_json,
                        "install_profile": install_profile,
                        "installer_type": "neoforge"
                    }
        
        except Exception as e:
            logger.error(f"获取 NeoForge 配置失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return None


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
        elif loader_type == LoaderType.FORGE:
            return self.forge.get_profile_json(mc_version, loader_version)
        elif loader_type == LoaderType.NEOFORGE:
            return self.neoforge.get_profile_json(mc_version, loader_version)
        
        logger.warning(f"{loader_type.value} 暂不支持")
        return None
