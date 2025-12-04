"""
Minecraft 下载管理器
整合所有下载模块，提供统一的下载接口
"""
import json
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from utils.logger import logger
from .mirror_utils import MirrorManager
from .http_downloader import HttpDownloader
from .version_manifest import VersionManifest
from .version_info import VersionInfo, RuleEvaluator
from .client_downloader import ClientDownloader
from .library_downloader import LibraryDownloader
from .asset_downloader import AssetDownloader
from .loader_support import LoaderManager, LoaderType
from .forge_installer import ForgeInstaller


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
            
            # 获取版本 JSON（区分目录名和文件名）
            # 目录名：使用 custom_name 或 version_id
            # 文件名：始终使用 version_id
            version_info = VersionInfo.from_url(
                version_id,  # 文件名使用原始版本号
                version_url,
                self.minecraft_dir,
                self.downloader,
                custom_dir_name=final_name  # 目录名使用自定义名称
            )
            
            if not version_info:
                return False
            
            # 保存版本 JSON
            version_info.save_version_json()
            self._update_progress("version_info", 1, 1, "版本信息获取完成")
            
            # 3. 下载客户端 JAR（使用 version_info 的路径，确保文件名正确）
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
            
            # 直接下载到 version_info 指定的路径（目录名是自定义的，文件名是版本号）
            url = client_info.get("url")
            sha1 = client_info.get("sha1")
            jar_path = version_info.get_client_jar_path()  # 使用 version_info 的路径方法
            
            logger.info(f"下载客户端 JAR 到: {jar_path}")
            
            success = self.downloader.download_file(
                url=url,
                save_path=jar_path,
                sha1=sha1,
                use_mirror=True,
                progress_callback=client_progress
            )
            
            if not success:
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
        custom_name: Optional[str] = None,
        fabric_api_version: Optional[str] = None
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
        if custom_name:
            logger.info(f"📝 自定义名称: {custom_name}")
        
        try:
            # 1. 先下载原版（使用自定义名称）
            if not self.download_vanilla(mc_version, custom_name):
                return False
            
            # 2. 获取加载器配置
            self._update_progress("loader_info", 0, 1, f"正在获取 {loader_type.value} 配置...")
            
            if loader_type == LoaderType.FABRIC:
                profile = self.loader_manager.fabric.get_profile_json(
                    mc_version,
                    loader_version
                )
                
                if not profile:
                    logger.error("获取 Fabric 配置失败")
                    return False
                
                self._update_progress("loader_info", 1, 1, "Fabric 配置获取成功")
                logger.info("Fabric 配置获取成功")
                
                # 3. 下载 Fabric 依赖库
                fabric_libraries = profile.get("libraries", [])
                if fabric_libraries:
                    total_libs = len(fabric_libraries)
                    self._update_progress("loader_libraries", 0, total_libs, f"正在下载 Fabric 依赖库 (共 {total_libs} 个)...")
                    
                    def fabric_lib_progress(current, total):
                        self._update_progress(
                            "loader_libraries",
                            current,
                            total,
                            f"正在下载 Fabric 依赖库: {current}/{total}"
                        )
                    
                    logger.info(f"Fabric 依赖库数量: {len(fabric_libraries)}")
                    
                    # Fabric的库下载到全局libraries目录（不是版本专属目录）
                    # 所有版本共享libraries
                    success = self.library_downloader.download_libraries(
                        fabric_libraries,
                        None,  # Fabric的库不需要natives解压
                        fabric_lib_progress
                    )
                    
                    if success:
                        self._update_progress("loader_libraries", total_libs, total_libs, "Fabric 依赖库下载完成")
                        logger.info("📦 Fabric 依赖库下载完成")
                    else:
                        logger.warning("部分 Fabric 依赖库下载失败")
                
                # 4. 如果选择了 Fabric API，下载到版本专属的 mods 目录
                # 根据版本隔离要求，每个版本有独立的 mods 目录
                if fabric_api_version:
                    self._update_progress("fabric_api", 0, 1, "正在下载 Fabric API...")
                    
                    # 注意：这里需要先计算version_dir_name（在步骤5中定义）
                    # 为了避免重复计算，我们这里直接使用custom_name
                    version_dir_for_mods = custom_name if custom_name else f"fabric-loader-{loader_version}-{mc_version}"
                    # 版本隔离：mods 目录在版本专属目录下
                    version_mods_dir = self.minecraft_dir / "versions" / version_dir_for_mods / "mods"
                    version_mods_dir.mkdir(parents=True, exist_ok=True)
                    
                    logger.info(f"📂 版本专属 mods 目录: {version_mods_dir}")
                    
                    # 从 Modrinth 获取 Fabric API 下载链接
                    try:
                        from utils.httpx import get_session
                        client = get_session()
                        
                        # Fabric API 的 Modrinth ID
                        fabric_api_id = "P7dR8mSH"
                        url = f"https://api.modrinth.com/v2/project/{fabric_api_id}/version"
                        
                        # 增加超时时间，并添加重试机制
                        retry_count = 3
                        versions_data = None
                        
                        for attempt in range(retry_count):
                            try:
                                response = client.get(url, timeout=15.0)
                                if response.status_code == 200:
                                    versions_data = response.json()
                                    break
                                else:
                                    logger.warning(f"Modrinth API 请求失败: {response.status_code} (重试 {attempt+1}/{retry_count})")
                                    import time
                                    time.sleep(1)
                            except Exception as e:
                                logger.warning(f"Modrinth API 请求异常: {e} (重试 {attempt+1}/{retry_count})")
                                import time
                                time.sleep(1)
                        
                        if versions_data:
                            # 查找匹配的版本
                            target_version = None
                            for version in versions_data:
                                if version.get("version_number") == fabric_api_version:
                                    target_version = version
                                    break
                            
                            if target_version and target_version.get("files"):
                                # 获取主文件
                                primary_file = None
                                for file in target_version["files"]:
                                    if file.get("primary", False):
                                        primary_file = file
                                        break
                                
                                if not primary_file and target_version["files"]:
                                    primary_file = target_version["files"][0]
                                
                                if primary_file:
                                    download_url = primary_file.get("url")
                                    filename = primary_file.get("filename")
                                    
                                    if download_url and filename:
                                        # 下载 Fabric API jar 到版本专属 mods 目录
                                        fabric_api_path = version_mods_dir / filename
                                        
                                        logger.info(f"下载 Fabric API: {filename}")
                                        
                                        # 下载文件重试机制
                                        download_success = False
                                        for attempt in range(retry_count):
                                            try:
                                                file_response = client.get(download_url, timeout=30.0)
                                                if file_response.status_code == 200:
                                                    with open(fabric_api_path, "wb") as f:
                                                        f.write(file_response.content)
                                                    download_success = True
                                                    break
                                                else:
                                                    logger.warning(f"Fabric API 下载失败: {file_response.status_code} (重试 {attempt+1}/{retry_count})")
                                            except Exception as e:
                                                logger.warning(f"Fabric API 下载异常: {e} (重试 {attempt+1}/{retry_count})")
                                        
                                        if download_success:
                                            logger.info(f"✅ Fabric API 已下载到: {fabric_api_path}")
                                            self._update_progress("fabric_api", 1, 1, "Fabric API 下载完成")
                                        else:
                                            logger.error("Fabric API 下载最终失败")
                                    else:
                                        logger.error("Fabric API 文件信息不完整")
                                else:
                                    logger.error("Fabric API 没有有效的下载文件")
                            else:
                                logger.error(f"未找到 Fabric API 版本: {fabric_api_version}")
                        else:
                            logger.error("无法获取 Fabric API 版本列表")
                    except Exception as e:
                        logger.error(f"下载 Fabric API 失败: {e}")
                
                # 5. 创建 Fabric 版本 JSON
                # 有自定义名称：完全合并（像 PCL 那样）
                # 无自定义名称：使用 inheritsFrom 继承
                
                # 5. 创建 Fabric 版本 JSON（完全合并模式，与 Forge 一致）
                import shutil
                
                # 确定最终版本名称
                final_name = custom_name.strip() if custom_name else f"fabric-loader-{loader_version}-{mc_version}"
                
                logger.info(f"🔧 使用完全合并模式安装 Fabric")
                
                version_dir = self.minecraft_dir / "versions" / final_name
                version_dir.mkdir(parents=True, exist_ok=True)
                
                # 读取原版MC的JSON
                mc_json_path = version_dir / f"{mc_version}.json"
                if not mc_json_path.exists():
                    error_msg = f"MC JSON不存在: {mc_json_path}"
                    logger.error(error_msg)
                    self._update_progress("error", 0, 0, error_msg)
                    return False
                
                try:
                    with open(mc_json_path, "r", encoding="utf-8") as f:
                        mc_data = json.load(f)
                    
                    # 以MC原版为基础，合并Fabric配置
                    merged_data = mc_data.copy()
                    merged_data["id"] = final_name
                    merged_data["type"] = "fabric"
                    merged_data["mainClass"] = profile.get("mainClass")
                    
                    # 删除 inheritsFrom（完全合并模式）
                    if "inheritsFrom" in merged_data:
                        del merged_data["inheritsFrom"]
                    
                    # 合并arguments
                    if "arguments" not in merged_data:
                        merged_data["arguments"] = {}
                    if "arguments" in profile:
                        for arg_type in ["game", "jvm"]:
                            if arg_type in profile["arguments"]:
                                if arg_type not in merged_data["arguments"]:
                                    merged_data["arguments"][arg_type] = []
                                merged_data["arguments"][arg_type].extend(profile["arguments"][arg_type])
                    
                    # 合并libraries（去重，优先使用Fabric的高版本库）
                    if "libraries" not in merged_data:
                        merged_data["libraries"] = []
                    
                    # 构建MC库的名称集合（用于去重）
                    mc_lib_names = {}
                    for lib in merged_data["libraries"]:
                        lib_name = lib.get("name", "")
                        if lib_name:
                            parts = lib_name.split(":")
                            if len(parts) >= 2:
                                base_name = f"{parts[0]}:{parts[1]}"
                                mc_lib_names[base_name] = lib
                    
                    # 添加Fabric库，如果有冲突则覆盖
                    for fabric_lib in fabric_libraries:
                        lib_name = fabric_lib.get("name", "")
                        if lib_name:
                            parts = lib_name.split(":")
                            if len(parts) >= 2:
                                base_name = f"{parts[0]}:{parts[1]}"
                                if base_name in mc_lib_names:
                                    old_lib = mc_lib_names[base_name]
                                    merged_data["libraries"].remove(old_lib)
                                    logger.info(f"⚠️ 库冲突，使用Fabric版本: {lib_name}")
                        merged_data["libraries"].append(fabric_lib)
                    
                    # 保存合并后JSON（使用版本名作为文件名）
                    final_json_path = version_dir / f"{final_name}.json"
                    with open(final_json_path, "w", encoding="utf-8") as f:
                        json.dump(merged_data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"✅ Fabric 版本已创建: {final_json_path.name}")
                    logger.info(f"🎮 mainClass: {merged_data.get('mainClass')}")
                    logger.info(f"📦 Libraries: {len(merged_data.get('libraries', []))} 个")
                    
                    # 处理文件重命名（与 Forge 一致）
                    # 重命名 JAR
                    old_jar = version_dir / f"{mc_version}.jar"
                    final_jar = version_dir / f"{final_name}.jar"
                    if old_jar.exists() and not final_jar.exists():
                        old_jar.rename(final_jar)
                        logger.info(f"✅ 已重命名 JAR: {mc_version}.jar → {final_name}.jar")
                    
                    # 删除原版 JSON（避免混淆）
                    if mc_json_path.exists() and mc_json_path != final_json_path:
                        mc_json_path.unlink()
                        logger.info(f"🗑️ 已删除原版 JSON: {mc_version}.json")
                    
                except Exception as e:
                    error_msg = f"合并 Fabric 配置失败: {e}"
                    logger.error(error_msg)
                    import traceback
                    logger.error(traceback.format_exc())
                    self._update_progress("error", 0, 0, error_msg)
                    return False
                
                logger.info("✅ Fabric 安装完成")
            
            elif loader_type == LoaderType.FORGE:
                # Forge 自动安装（使用新的 ForgeInstaller）
                logger.info(f"🔨 开始Forge自动安装: {loader_version}")
                
                # 1. 获取Forge配置
                self._update_progress("loader_info", 0, 1, "正在获取 Forge 配置...")
                forge_data = self.loader_manager.get_loader_profile(loader_type, mc_version, loader_version)
                if not forge_data:
                    error_msg = "获取Forge配置失败"
                    logger.error(error_msg)
                    self._update_progress("error", 0, 0, error_msg)
                    return False
                
                version_json = forge_data.get("version")
                installer_type = forge_data.get("installer_type")
                
                if not version_json:
                    error_msg = "Forge配置缺失version字段"
                    logger.error(error_msg)
                    self._update_progress("error", 0, 0, error_msg)
                    return False
                
                logger.info(f"📝 Forge安装器类型: {installer_type}")
                logger.info(f"🆔 Forge版本: {version_json.get('id')}")
                self._update_progress("loader_info", 1, 1, "Forge 配置获取成功")
                
                # 2. 使用 ForgeInstaller 执行安装
                def forge_progress_callback(stage: str, current: int, total: int):
                    stage_names = {
                        "forge_libraries": "下载 Forge 依赖库",
                        "extract_data": "提取安装数据",
                        "processors": "执行 Forge 处理器",
                        "generate_json": "生成版本配置"
                    }
                    stage_name = stage_names.get(stage, stage)
                    self._update_progress(
                        stage,  # 直接使用原始 stage 名称
                        current,
                        total,
                        f"{stage_name}: {current}/{total}"
                    )
                
                forge_installer = ForgeInstaller(
                    minecraft_dir=self.minecraft_dir,
                    downloader=self.downloader,
                    progress_callback=forge_progress_callback
                )
                
                # 查找 Java 路径
                java_path = self._find_java_path()
                
                success = forge_installer.install_forge(
                    mc_version=mc_version,
                    forge_version=loader_version,
                    forge_data=forge_data,
                    custom_name=custom_name,
                    java_path=java_path
                )
                
                if not success:
                    error_msg = "Forge 安装失败"
                    logger.error(error_msg)
                    self._update_progress("error", 0, 0, error_msg)
                    return False
                
                logger.info("✅ Forge 安装完成")
            
            elif loader_type == LoaderType.NEOFORGE:
                # NeoForge 安装（与 Forge 1.13+ 类似）
                logger.info(f"🔧 开始 NeoForge 自动安装: {loader_version}")
                
                # 1. 获取 NeoForge 配置
                self._update_progress("loader_info", 0, 1, "正在获取 NeoForge 配置...")
                neoforge_data = self.loader_manager.get_loader_profile(loader_type, mc_version, loader_version)
                if not neoforge_data:
                    error_msg = "获取 NeoForge 配置失败"
                    logger.error(error_msg)
                    self._update_progress("error", 0, 0, error_msg)
                    return False
                
                version_json = neoforge_data.get("version")
                
                if not version_json:
                    error_msg = "NeoForge 配置缺失 version 字段"
                    logger.error(error_msg)
                    self._update_progress("error", 0, 0, error_msg)
                    return False
                
                logger.info(f"🆔 NeoForge 版本: {version_json.get('id')}")
                self._update_progress("loader_info", 1, 1, "NeoForge 配置获取成功")
                
                # 2. 使用 ForgeInstaller 执行安装（NeoForge 模式）
                def neoforge_progress_callback(stage: str, current: int, total: int):
                    stage_names = {
                        "forge_libraries": "下载 NeoForge 依赖库",
                        "extract_data": "提取安装数据",
                        "processors": "执行 NeoForge 处理器",
                        "generate_json": "生成版本配置"
                    }
                    stage_name = stage_names.get(stage, stage)
                    self._update_progress(
                        stage,
                        current,
                        total,
                        f"{stage_name}: {current}/{total}"
                    )
                
                neoforge_installer = ForgeInstaller(
                    minecraft_dir=self.minecraft_dir,
                    downloader=self.downloader,
                    progress_callback=neoforge_progress_callback
                )
                
                # 查找 Java 路径
                java_path = self._find_java_path()
                
                success = neoforge_installer.install_neoforge(
                    mc_version=mc_version,
                    neoforge_version=loader_version,
                    neoforge_data=neoforge_data,
                    custom_name=custom_name,
                    java_path=java_path
                )
                
                if not success:
                    error_msg = "NeoForge 安装失败"
                    logger.error(error_msg)
                    self._update_progress("error", 0, 0, error_msg)
                    return False
                
                logger.info("✅ NeoForge 安装完成")
            
            self._update_progress("complete", 1, 1, f"{loader_type.value} 安装完成")
            return True
        
        except Exception as e:
            logger.error(f"下载加载器版本失败: {e}", exc_info=True)
            self._update_progress("error", 0, 0, f"下载失败: {e}")
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
                # 检查是否是异步回调
                import inspect
                import asyncio
                if inspect.iscoroutinefunction(self.progress_callback):
                    # 如果在事件循环中，使用 create_task
                    try:
                        loop = asyncio.get_running_loop()
                        if loop.is_running():
                            loop.create_task(self.progress_callback(self.progress))
                    except RuntimeError:
                        # 如果没有事件循环，创建一个新的（不太可能在下载器中发生，除非是在独立脚本）
                        pass
                else:
                    # 如果不是协程函数，直接调用
                    # 但如果外部期望是异步环境（例如在异步任务中调用同步回调），这可能会阻塞
                    # 如果回调本身需要进行异步操作（如 manager.broadcast），它应该被定义为 async
                    
                    # 这里尝试检查是否需要将同步回调放入线程池，或者直接调用
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
    
    def _detect_loader_type(self, version_data: dict, version_id: str) -> str:
        """
        检测版本的加载器类型
        
        Args:
            version_data: 版本 JSON 数据
            version_id: 版本 ID
            
        Returns:
            加载器类型: fabric, forge, neoforge, optifine, release, snapshot
        """
        # 1. 检查 mainClass 字段
        main_class = version_data.get("mainClass", "").lower()
        
        if "fabric" in main_class or "net.fabricmc" in main_class:
            return "fabric"
        if "neoforge" in main_class or "net.neoforged" in main_class:
            return "neoforge"
        if "forge" in main_class or "net.minecraftforge" in main_class:
            return "forge"
        if "optifine" in main_class:
            return "optifine"
        
        # 2. 检查 libraries 字段
        libraries = version_data.get("libraries", [])
        for lib in libraries:
            lib_name = lib.get("name", "").lower()
            if "net.fabricmc" in lib_name or "fabric-loader" in lib_name:
                return "fabric"
            if "net.neoforged" in lib_name or "neoforge" in lib_name:
                return "neoforge"
            if "net.minecraftforge" in lib_name or "forge" in lib_name:
                # 需要再次检查不是 neoforge
                if "neoforge" not in lib_name:
                    return "forge"
            if "optifine" in lib_name:
                return "optifine"
        
        # 3. 检查版本 ID
        version_id_lower = version_id.lower()
        if "fabric" in version_id_lower:
            return "fabric"
        if "neoforge" in version_id_lower:
            return "neoforge"
        if "forge" in version_id_lower:
            return "forge"
        if "optifine" in version_id_lower:
            return "optifine"
        
        # 4. 检查 inheritsFrom 字段（有些版本会有这个）
        inherits_from = version_data.get("inheritsFrom", "")
        if inherits_from:
            # 如果有继承，说明可能是加载器版本，再检查 arguments 或 minecraftArguments
            arguments = version_data.get("arguments", {})
            game_args = arguments.get("game", []) if isinstance(arguments, dict) else []
            jvm_args = arguments.get("jvm", []) if isinstance(arguments, dict) else []
            
            all_args = str(game_args) + str(jvm_args)
            if "fabric" in all_args.lower():
                return "fabric"
            if "neoforge" in all_args.lower():
                return "neoforge"
            if "forge" in all_args.lower():
                return "forge"
        
        # 5. 默认返回官方类型
        official_type = version_data.get("type", "release")
        if official_type in ["snapshot", "old_beta", "old_alpha"]:
            return official_type
        
        return "release"
    
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
                
                # 查找目录中的JSON和JAR文件
                json_files = list(version_dir.glob("*.json"))
                jar_files = list(version_dir.glob("*.jar"))
                
                # 必须同时存在JSON和JAR才算有效版本
                if json_files and jar_files:
                    version_json = json_files[0]
                    version_jar = jar_files[0]
                    # 读取版本信息
                    try:
                        with open(version_json, "r", encoding="utf-8") as f:
                            version_data = json.load(f)
                        
                        # 确保 version_data 是字典
                        if not isinstance(version_data, dict):
                             # 如果是列表（可能是PCL等启动器的列表缓存），尝试找到真正的版本对象
                            if isinstance(version_data, list):
                                logger.warning(f"版本 {version_id} JSON 格式异常（列表），尝试修复")
                                # 简单的策略：如果列表里有字典且包含 id 字段，且 id 匹配，则使用它
                                found = False
                                for item in version_data:
                                    if isinstance(item, dict) and item.get("id") == version_id:
                                        version_data = item
                                        found = True
                                        break
                                if not found:
                                    # 如果没找到匹配的，但列表第一个是字典，尝试使用
                                    if version_data and isinstance(version_data[0], dict):
                                        version_data = version_data[0]
                                    else:
                                        raise ValueError("Version JSON is a list but contains no valid version object")
                            else:
                                raise ValueError(f"Version JSON format error: expected dict, got {type(version_data)}")

                        # 检测加载器类型
                        loader_type = self._detect_loader_type(version_data, version_id)
                        
                        version_info = {
                            "id": version_id,
                            "type": loader_type,
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
                        version_id_lower = version_id.lower()
                        if "fabric" in version_id_lower:
                            version_type = "fabric"
                        elif "neoforge" in version_id_lower:
                            version_type = "neoforge"
                        elif "forge" in version_id_lower:
                            version_type = "forge"
                        elif "optifine" in version_id_lower:
                            version_type = "optifine"
                        elif "snapshot" in version_id_lower or "w" in version_id_lower:
                            version_type = "snapshot"
                        elif "pre" in version_id_lower or "rc" in version_id_lower:
                            version_type = "snapshot"
                        
                        installed_versions.append({
                            "id": version_id,
                            "type": version_type,
                            "installed": True,
                            "jar_exists": version_jar.exists(),
                            "json_exists": version_json.exists()
                        })
        
        return installed_versions
    
    def _find_java_path(self) -> str:
        """
        查找 Java 可执行文件路径
        
        Returns:
            Java 可执行文件路径
        """
        import subprocess
        import platform
        
        # 首先检查系统 PATH 中的 java
        try:
            result = subprocess.run(["java", "-version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return "java"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Windows 系统尝试常见路径
        if platform.system() == "Windows":
            common_paths = [
                "C:\\Program Files\\Java\\jdk-17\\bin\\java.exe",
                "C:\\Program Files\\Java\\jre-17\\bin\\java.exe",
                "C:\\Program Files\\Eclipse Adoptium\\jdk-17\\bin\\java.exe",
                "C:\\Program Files\\Eclipse Adoptium\\jre-17\\bin\\java.exe",
                "C:\\Program Files (x86)\\Java\\jdk-17\\bin\\java.exe",
                "C:\\Program Files (x86)\\Java\\jre-17\\bin\\java.exe",
                "C:\\Program Files\\Java\\jdk-21\\bin\\java.exe",
                "C:\\Program Files\\Eclipse Adoptium\\jdk-21\\bin\\java.exe",
            ]
            
            for path in common_paths:
                if Path(path).exists():
                    return path
        
        # 默认返回 java
        return "java"
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
