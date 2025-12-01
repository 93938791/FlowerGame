"""
Minecraft 下载管理器
整合所有下载模块，提供统一的下载接口
"""
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from utils.logger import logger
from .mirror_utils import MirrorManager
from .http_downloader import HttpDownloader
from .version_manifest import VersionManifest
from .version_info import VersionInfo
from .client_downloader import ClientDownloader
from .library_downloader import LibraryDownloader
from .asset_downloader import AssetDownloader
from .loader_support import LoaderManager, LoaderType


class DownloadProgress:
    """下载进度"""
    
    def __init__(self):
        self.stage = "idle"  # idle, version_info, client_jar, libraries, assets, complete
        self.current = 0
        self.total = 0
        self.message = ""
        # 添加单独的库和资源进度跟踪
        self.libraries_progress = {"current": 0, "total": 0}
        self.assets_progress = {"current": 0, "total": 0}
    
    def update(self, stage: str, current: int, total: int, message: str = ""):
        self.stage = stage
        self.current = current
        self.total = total
        self.message = message


class MinecraftDownloadManager:
    """Minecraft 下载管理器"""
    
    def __init__(
        self,
        minecraft_dir: Optional[Path] = None,
        max_connections: int = None,  # None 表示自动计算
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ):
        """
        初始化下载管理器
        
        Args:
            minecraft_dir: Minecraft 目录，None 则使用默认路径
            max_connections: 最大并发连接数，None 则根据 CPU 自动计算
            progress_callback: 进度回调函数
        """
        # 设置 Minecraft 目录
        if minecraft_dir is None:
            from config import Config
            if not Config.is_configured():
                raise ValueError("未配置 FlowerGame 目录，请先启动程序进行配置")
            Config.init_dirs()
            self.minecraft_dir = Config.MINECRAFT_DIR
        else:
            self.minecraft_dir = Path(minecraft_dir)
        
        self.minecraft_dir.mkdir(parents=True, exist_ok=True)
        
        # 自动计算连接数
        if max_connections is None:
            import os
            cpu_count = os.cpu_count() or 4
            # 连接数 = CPU核心数 * 4，但不超过 100
            max_connections = min(cpu_count * 4, 100)
            logger.info(f"🔧 CPU 核心数: {cpu_count}, HTTP 连接数: {max_connections}")
        
        # 初始化组件
        self.mirror_manager = MirrorManager()
        self.downloader = HttpDownloader(
            max_connections=max_connections,
            mirror_manager=self.mirror_manager
        )
        
        self.version_manifest = VersionManifest(
            downloader=self.downloader,
            mirror_manager=self.mirror_manager
        )
        
        self.client_downloader = ClientDownloader(self.minecraft_dir, self.downloader)
        self.library_downloader = LibraryDownloader(self.minecraft_dir, self.downloader)
        self.asset_downloader = AssetDownloader(self.minecraft_dir, self.downloader)
        self.loader_manager = LoaderManager(self.downloader)
        
        # 进度回调
        self.progress_callback = progress_callback
        self.progress = DownloadProgress()
    
    def download_vanilla(
        self,
        version_id: str,
        custom_name: Optional[str] = None
    ) -> bool:
        """
        下载原版 Minecraft
        
        Args:
            version_id: 版本 ID（如 1.20.1）
            custom_name: 自定义版本名称
            
        Returns:
            是否下载成功
        """
        # 使用自定义名称或默认版本ID
        final_name = custom_name.strip() if custom_name else version_id
        
        logger.info(f"==================== 开始下载 Minecraft {version_id} ====================")
        logger.info(f"📂 下载目录: {self.minecraft_dir}")
        logger.info(f"✓ 目录是否存在: {self.minecraft_dir.exists()}")
        if custom_name:
            logger.info(f"📝 自定义名称: {final_name}")
        
        try:
            # 1. 加载版本清单
            self._update_progress("version_manifest", 0, 1, "正在加载版本清单...")
            if not self.version_manifest.load_manifest():
                logger.error("加载版本清单失败")
                return False
            self._update_progress("version_manifest", 1, 1, "版本清单加载完成")
            
            # 2. 获取版本信息
            self._update_progress("version_info", 0, 1, f"正在获取版本信息: {version_id}")
            version_data = self.version_manifest.get_version_info(version_id)
            if not version_data:
                logger.error(f"未找到版本: {version_id}")
                return False
            
            version_url = version_data.get("url")
            if not version_url:
                logger.error("版本信息不完整")
                return False
            
            # 获取版本 JSON（使用自定义名称）
            version_info = VersionInfo.from_url(
                final_name,  # 使用自定义名称
                version_url,
                self.minecraft_dir,
                self.downloader
            )
            
            if not version_info:
                return False
            
            # 保存版本 JSON
            version_info.save_version_json()
            self._update_progress("version_info", 1, 1, "版本信息获取完成")
            
            # 3. 下载客户端 JAR
            self._update_progress("client_jar", 0, 1, "正在下载客户端 JAR...")
            client_info = version_info.get_client_download_info()
            if not client_info:
                logger.error("获取客户端下载信息失败")
                return False
            
            def client_progress(downloaded, total):
                self._update_progress(
                    "client_jar",
                    downloaded,
                    total,
                    f"正在下载客户端 JAR: {downloaded / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB"
                )
            
            # 使用自定义名称下载客户端
            if not self.client_downloader.download_client(final_name, client_info, client_progress):
                logger.error("客户端 JAR 下载失败")
                return False
            
            self._update_progress("client_jar", 1, 1, "客户端 JAR 下载完成")
            
            # 4. 并行下载依赖库和资源文件
            libraries = version_info.get_libraries(filter_by_rules=True)
            asset_index_info = version_info.get_asset_index_info()
            
            # 使用线程池并行下载
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 提交依赖库下载任务
                lib_future = executor.submit(self._download_libraries, version_info, libraries)
                
                # 提交资源文件下载任务
                asset_future = None
                if asset_index_info:
                    asset_future = executor.submit(self._download_assets, asset_index_info)
                
                # 等待依赖库下载完成
                lib_success = lib_future.result()
                if lib_success:
                    logger.info("📦 依赖库下载完成")
                else:
                    logger.warning("部分依赖库下载失败")
                
                # 等待资源文件下载完成
                if asset_future:
                    asset_success = asset_future.result()
                    if asset_success:
                        logger.info("🎨 资源文件下载完成")
                    else:
                        logger.warning("部分资源文件下载失败")
            
            # 完成
            self._update_progress("complete", 1, 1, f"✓ {final_name} 下载完成！")
            logger.info(f"==================== {final_name} 下载完成 ====================")
            return True
        
        except Exception as e:
            logger.error(f"下载过程发生异常: {e}", exc_info=True)
            self._update_progress("error", 0, 0, f"下载失败: {e}")
            return False
    
    def download_with_loader(
        self,
        mc_version: str,
        loader_type: LoaderType,
        loader_version: str,
        custom_name: Optional[str] = None
    ) -> bool:
        """
        下载带加载器的版本
        
        Args:
            mc_version: Minecraft 版本
            loader_type: 加载器类型
            loader_version: 加载器版本
            custom_name: 自定义版本名称
            
        Returns:
            是否下载成功
        """
        logger.info(f"开始下载 {mc_version} + {loader_type.value} {loader_version}")
        
        try:
            # 1. 先下载原版
            if not self.download_vanilla(mc_version):
                return False
            
            # 2. 获取加载器配置
            self._update_progress("loader", 0, 1, f"正在获取 {loader_type.value} 配置...")
            
            if loader_type == LoaderType.FABRIC:
                profile = self.loader_manager.get_loader_profile(
                    loader_type,
                    mc_version,
                    loader_version
                )
                
                if not profile:
                    logger.error("获取 Fabric 配置失败")
                    return False
                
                # TODO: 合并 Fabric 配置并下载额外的库
                logger.info("Fabric 配置获取成功（需要实现配置合并）")
            
            elif loader_type == LoaderType.FORGE:
                # Forge 需要下载安装器
                installer_url = self.loader_manager.forge.get_installer_url(
                    mc_version,
                    loader_version
                )
                logger.info(f"Forge 安装器 URL: {installer_url}")
                logger.warning("Forge 安装需要手动运行安装器（自动安装功能待实现）")
            
            self._update_progress("loader", 1, 1, f"{loader_type.value} 处理完成")
            return True
        
        except Exception as e:
            logger.error(f"下载加载器版本失败: {e}", exc_info=True)
            return False
    
    def list_versions(self, version_type: Optional[str] = None) -> list:
        """
        列出所有可用版本
        
        Args:
            version_type: 版本类型过滤（release, snapshot）
            
        Returns:
            版本列表
        """
        if not self.version_manifest.load_manifest():
            return []
        
        return self.version_manifest.list_versions(version_type)
    
    def get_loader_versions(self, loader_type: LoaderType, mc_version: str) -> Optional[list]:
        """
        获取加载器版本列表
        
        Args:
            loader_type: 加载器类型
            mc_version: Minecraft 版本
            
        Returns:
            加载器版本列表
        """
        return self.loader_manager.get_loader_versions(loader_type, mc_version)
    
    def _download_libraries(self, version_info, libraries):
        """下载依赖库"""
        total_libs = len(libraries)
        self._update_progress("libraries", 0, total_libs, f"正在下载依赖库 (共 {total_libs} 个)...")
        
        def lib_progress(current, total):
            # 更新库的独立进度
            self.progress.libraries_progress["current"] = current
            self.progress.libraries_progress["total"] = total
            self._update_progress(
                "libraries",
                current,
                total,
                f"正在下载依赖库: {current}/{total}"
            )
        
        natives_dir = version_info.get_natives_dir()
        success = self.library_downloader.download_libraries(libraries, natives_dir, lib_progress)
        
        if success:
            self._update_progress("libraries", total_libs, total_libs, "依赖库下载完成")
        else:
            logger.warning("部分依赖库下载失败")
        
        return success
    
    def _download_assets(self, asset_index_info):
        """下载资源文件"""
        self._update_progress("assets", 0, 1, "正在下载资源文件...")
        
        def asset_progress(stage, current, total):
            # 更新资源的独立进度
            self.progress.assets_progress["current"] = current
            self.progress.assets_progress["total"] = total
            if stage == "index":
                self._update_progress("assets", current, total, "正在下载资源索引...")
            else:
                self._update_progress(
                    "assets",
                    current,
                    total,
                    f"正在下载资源文件: {current}/{total}"
                )
        
        success = self.asset_downloader.download_assets(asset_index_info, asset_progress)
        
        if success:
            self._update_progress("assets", 1, 1, "资源文件下载完成")
        else:
            logger.warning("部分资源文件下载失败")
        
        return success
    
    def _update_progress(self, stage: str, current: int, total: int, message: str = ""):
        """更新进度"""
        self.progress.update(stage, current, total, message)
        
        if self.progress_callback:
            try:
                self.progress_callback(self.progress)
            except Exception as e:
                logger.error(f"进度回调异常: {e}")
        
        # 同时输出日志
        if total > 0:
            percentage = (current / total) * 100
            logger.info(f"[{stage}] {percentage:.1f}% - {message}")
        else:
            logger.info(f"[{stage}] {message}")
    
    def close(self):
        """关闭下载器"""
        self.downloader.close()
    
    def list_installed_versions(self) -> list:
        """
        列出本地已安装的 Minecraft 版本
        
        Returns:
            已安装版本列表，每个版本包含 id 和类型信息
        """
        installed_versions = []
        
        # 检查 versions 目录
        versions_dir = self.minecraft_dir / "versions"
        if not versions_dir.exists():
            return installed_versions
        
        # 遍历版本目录
        for version_dir in versions_dir.iterdir():
            if version_dir.is_dir():
                version_id = version_dir.name
                
                # 检查是否存在版本 JSON 文件
                version_json = version_dir / f"{version_id}.json"
                version_jar = version_dir / f"{version_id}.jar"
                
                if version_json.exists() and version_jar.exists():
                    # 读取版本信息
                    try:
                        with open(version_json, "r", encoding="utf-8") as f:
                            version_data = json.load(f)
                        
                        # 获取版本类型，如果没有则尝试从 id 推断
                        version_type = version_data.get("type")
                        if not version_type or version_type == "unknown":
                            # 尝试从版本名推断类型
                            if "snapshot" in version_id.lower() or "w" in version_id.lower():
                                version_type = "snapshot"
                            elif "pre" in version_id.lower() or "rc" in version_id.lower():
                                version_type = "snapshot"
                            else:
                                # 默认为 release
                                version_type = "release"
                        
                        version_info = {
                            "id": version_id,
                            "type": version_type,
                            "installed": True,
                            "jar_exists": version_jar.exists(),
                            "json_exists": version_json.exists()
                        }
                        
                        installed_versions.append(version_info)
                    except Exception as e:
                        logger.warning(f"读取版本 {version_id} 信息失败: {e}")
                        # 即使读取失败，也添加基本版本信息
                        # 尝试从版本名推断类型
                        version_type = "release"
                        if "snapshot" in version_id.lower() or "w" in version_id.lower():
                            version_type = "snapshot"
                        elif "pre" in version_id.lower() or "rc" in version_id.lower():
                            version_type = "snapshot"
                        
                        installed_versions.append({
                            "id": version_id,
                            "type": version_type,
                            "installed": True,
                            "jar_exists": version_jar.exists(),
                            "json_exists": version_json.exists()
                        })
        
        return installed_versions
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
