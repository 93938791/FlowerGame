"""
Forge/NeoForge 安装器处理器
支持：
- Forge 新型 (1.13+) 和旧型 (1.12.2-) 安装
- NeoForge (1.20.1+) 安装
参考 HMCL/PCL2 实现
"""
import json
import zipfile
import subprocess
import tempfile
import shutil
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from utils.logger import logger
from .http_downloader import HttpDownloader, DownloadTask


class ForgeInstaller:
    """Forge/NeoForge 安装器"""
    
    BMCL_MAVEN = "https://bmclapi2.bangbang93.com/maven"
    FORGE_MAVEN = "https://maven.minecraftforge.net"
    NEOFORGE_MAVEN = "https://maven.neoforged.net/releases"
    
    def __init__(
        self, 
        minecraft_dir: Path, 
        downloader: HttpDownloader,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ):
        """
        初始化 Forge 安装器
        
        Args:
            minecraft_dir: Minecraft 根目录
            downloader: HTTP 下载器
            progress_callback: 进度回调 (stage, current, total)
        """
        self.minecraft_dir = Path(minecraft_dir)
        self.downloader = downloader
        self.progress_callback = progress_callback
        self.libraries_dir = self.minecraft_dir / "libraries"
        self.libraries_dir.mkdir(parents=True, exist_ok=True)
    
    def install_forge(
        self,
        mc_version: str,
        forge_version: str,
        forge_data: Dict[str, Any],
        custom_name: Optional[str] = None,
        java_path: str = "java"
    ) -> bool:
        """
        安装 Forge
        
        Args:
            mc_version: Minecraft 版本
            forge_version: Forge 版本
            forge_data: Forge 配置数据 (从 ForgeLoader.get_profile_json 获取)
            custom_name: 自定义版本名称
            java_path: Java 可执行文件路径
            
        Returns:
            是否安装成功
        """
        installer_type = forge_data.get("installer_type")
        version_json = forge_data.get("version")
        install_profile = forge_data.get("install_profile")
        
        if not version_json or not install_profile:
            logger.error("Forge 配置数据不完整")
            return False
        
        logger.info(f"🔨 开始安装 Forge {mc_version}-{forge_version}")
        logger.info(f"📝 安装器类型: {installer_type}")
        
        if installer_type == "new":
            # 新型安装器 (1.13+)
            return self._install_new_forge(
                mc_version, forge_version, version_json, 
                install_profile, custom_name, java_path
            )
        else:
            # 旧型安装器 (1.12.2-)
            return self._install_legacy_forge(
                mc_version, forge_version, version_json,
                install_profile, custom_name
            )
    
    def install_neoforge(
        self,
        mc_version: str,
        neoforge_version: str,
        neoforge_data: Dict[str, Any],
        custom_name: Optional[str] = None,
        java_path: str = "java"
    ) -> bool:
        """
        安装 NeoForge
        NeoForge 的安装流程与 Forge 1.13+ 相同
        
        Args:
            mc_version: Minecraft 版本
            neoforge_version: NeoForge 版本
            neoforge_data: NeoForge 配置数据 (从 NeoForgeLoader.get_profile_json 获取)
            custom_name: 自定义版本名称
            java_path: Java 可执行文件路径
            
        Returns:
            是否安装成功
        """
        version_json = neoforge_data.get("version")
        install_profile = neoforge_data.get("install_profile")
        
        if not version_json or not install_profile:
            logger.error("NeoForge 配置数据不完整")
            return False
        
        logger.info(f"🔧 开始安装 NeoForge {neoforge_version}")
        
        # NeoForge 使用与 Forge 1.13+ 相同的安装流程
        return self._install_new_forge(
            mc_version, neoforge_version, version_json,
            install_profile, custom_name, java_path,
            loader_type="neoforge"  # 标识为 NeoForge
        )
    
    def _install_new_forge(
        self,
        mc_version: str,
        forge_version: str,
        version_json: Dict,
        install_profile: Dict,
        custom_name: Optional[str],
        java_path: str,
        loader_type: str = "forge"  # "forge" 或 "neoforge"
    ) -> bool:
        """
        安装新型 Forge/NeoForge (1.13+)
        需要执行 processors
        
        Args:
            loader_type: 加载器类型，"forge" 或 "neoforge"
        """
        loader_name = "NeoForge" if loader_type == "neoforge" else "Forge"
        logger.info(f"🆕 执行新型 {loader_name} 安装流程...")
        
        try:
            # 1. 首先提取安装器中的文件（包含预打包的库）
            self._update_progress("extract_data", 0, 1)
            
            # 根据加载器类型构建安装器 URL
            if loader_type == "neoforge":
                # NeoForge 安装器 URL
                installer_url = f"{self.BMCL_MAVEN}/net/neoforged/neoforge/{forge_version}/neoforge-{forge_version}-installer.jar"
            else:
                # Forge 安装器 URL
                full_version = f"{mc_version}-{forge_version}"
                installer_url = f"{self.BMCL_MAVEN}/net/minecraftforge/forge/{full_version}/forge-{full_version}-installer.jar"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                installer_path = temp_dir / "forge-installer.jar"
                
                logger.info(f"📥 下载安装器用于提取数据...")
                if not self.downloader.download_file(installer_url, installer_path, use_mirror=False):
                    logger.error("下载安装器失败")
                    return False
                
                # 提取 maven 目录下的文件到 libraries（这些是预打包的库）
                extracted_count = 0
                with zipfile.ZipFile(installer_path, 'r') as jar:
                    for file_info in jar.namelist():
                        # 提取 maven 目录下的文件到 libraries
                        if file_info.startswith("maven/"):
                            relative_path = file_info[6:]  # 去掉 "maven/" 前缀
                            if relative_path and not file_info.endswith("/"):
                                target_path = self.libraries_dir / relative_path
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                
                                with jar.open(file_info) as src, open(target_path, 'wb') as dst:
                                    dst.write(src.read())
                                extracted_count += 1
                                logger.debug(f"提取: {relative_path}")
                        
                        # 提取 data 目录下的文件用于 processors
                        if file_info.startswith("data/") and not file_info.endswith("/"):
                            # 跳过目录条目，只处理文件
                            target_path = temp_dir / file_info
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            with jar.open(file_info) as src, open(target_path, 'wb') as dst:
                                dst.write(src.read())
                
                logger.info(f"📦 已从安装器提取 {extracted_count} 个预打包库")
                self._update_progress("extract_data", 1, 1)
                
                # 2. 下载缺失的 Forge libraries（提取后再下载，避免重复下载已提取的文件）
                self._update_progress("forge_libraries", 0, 1)
                
                # 合并所有需要下载的库
                all_libraries = []
                
                # version.json 中的库
                version_libs = version_json.get("libraries", [])
                all_libraries.extend(version_libs)
                
                # install_profile 中的库 (用于执行 processors)
                installer_libs = install_profile.get("libraries", [])
                all_libraries.extend(installer_libs)
                
                logger.info(f"📦 需要检查的库: version={len(version_libs)}, installer={len(installer_libs)}")
                
                # 下载缺失的库（已存在的会自动跳过）
                if not self._download_forge_libraries(all_libraries):
                    logger.error("Forge 库下载失败")
                    return False
                
                # 3. 执行 processors
                processors = install_profile.get("processors", [])
                if processors:
                    self._update_progress("processors", 0, len(processors))
                    
                    data = install_profile.get("data", {})
                    
                    if not self._execute_processors(
                        processors, data, mc_version, forge_version,
                        temp_dir, java_path, custom_name
                    ):
                        logger.error("Forge processors 执行失败")
                        return False
            
            # 4. 生成版本 JSON
            self._update_progress("generate_json", 0, 1)
            
            if not self._generate_version_json(
                mc_version, forge_version, version_json, custom_name
            ):
                logger.error("生成版本 JSON 失败")
                return False
            
            self._update_progress("generate_json", 1, 1)
            
            logger.info("✅ Forge 安装完成")
            return True
            
        except Exception as e:
            logger.error(f"安装 Forge 时发生异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _install_legacy_forge(
        self,
        mc_version: str,
        forge_version: str,
        version_json: Dict,
        install_profile: Dict,
        custom_name: Optional[str]
    ) -> bool:
        """
        安装旧型 Forge (1.12.2及以下)
        不需要执行 processors
        """
        logger.info("📜 执行旧型 Forge 安装流程...")
        
        try:
            # 1. 下载 Forge libraries
            self._update_progress("forge_libraries", 0, 1)
            
            libraries = version_json.get("libraries", [])
            logger.info(f"📦 需要下载的库: {len(libraries)}")
            
            if not self._download_forge_libraries(libraries):
                logger.error("Forge 库下载失败")
                return False
            
            # 2. 复制 Forge JAR 到 libraries
            # 旧型 Forge 的主 JAR 通常在 install_profile.install.path 指定
            install_info = install_profile.get("install", {})
            forge_path = install_info.get("path")
            
            if forge_path:
                # 从安装器中提取 Forge JAR
                full_version = f"{mc_version}-{forge_version}"
                installer_url = f"{self.BMCL_MAVEN}/net/minecraftforge/forge/{full_version}/forge-{full_version}-installer.jar"
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    installer_path = Path(temp_dir) / "forge-installer.jar"
                    
                    if self.downloader.download_file(installer_url, installer_path, use_mirror=False):
                        with zipfile.ZipFile(installer_path, 'r') as jar:
                            # 查找并提取 forge jar
                            for file_info in jar.namelist():
                                if file_info.endswith(f"forge-{full_version}.jar") or \
                                   file_info.endswith(f"forge-{full_version}-universal.jar"):
                                    # 构建目标路径
                                    lib_path = self._maven_name_to_path(forge_path)
                                    if lib_path:
                                        target = self.libraries_dir / lib_path
                                        target.parent.mkdir(parents=True, exist_ok=True)
                                        
                                        with jar.open(file_info) as src, open(target, 'wb') as dst:
                                            dst.write(src.read())
                                        logger.info(f"✅ 已提取 Forge JAR: {target.name}")
                                        break
            
            # 3. 生成版本 JSON
            self._update_progress("generate_json", 0, 1)
            
            if not self._generate_version_json(
                mc_version, forge_version, version_json, custom_name
            ):
                logger.error("生成版本 JSON 失败")
                return False
            
            self._update_progress("generate_json", 1, 1)
            
            logger.info("✅ Forge 安装完成")
            return True
            
        except Exception as e:
            logger.error(f"安装旧型 Forge 时发生异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _download_forge_libraries(self, libraries: List[Dict]) -> bool:
        """
        下载 Forge 库文件
        
        Args:
            libraries: 库列表
            
        Returns:
            是否全部成功
        """
        download_tasks = []
        skipped_count = 0
        
        for lib in libraries:
            name = lib.get("name")
            if not name:
                continue
            
            # 解析库路径
            lib_path = self._maven_name_to_path(name)
            if not lib_path:
                continue
            
            save_path = self.libraries_dir / lib_path
            
            # 如果已存在，跳过
            if save_path.exists():
                continue
            
            # 构建下载 URL
            downloads = lib.get("downloads", {})
            artifact = downloads.get("artifact", {})
            
            url = None
            sha1 = None
            
            if artifact and artifact.get("url"):
                # 有完整的下载信息
                url = artifact.get("url")
                sha1 = artifact.get("sha1")
            elif lib.get("url"):
                # 库提供了基础 URL
                base_url = lib.get("url")
                url = base_url.rstrip("/") + "/" + lib_path
            
            # 如果没有 URL，说明这个库可能是：
            # 1. 通过 processors 生成的（如 client.jar）
            # 2. 已经在安装器的 maven/ 目录中（但可能用不同的名字）
            # 跳过这些库，让 processors 来处理
            if not url:
                logger.debug(f"⏭️ 跳过无 URL 的库（将由 processors 生成）: {name}")
                skipped_count += 1
                continue
            
            sha1 = artifact.get("sha1") if artifact else None
            
            download_tasks.append(DownloadTask(
                url=url,
                save_path=save_path,
                sha1=sha1,
                description=f"Forge Library: {name}"
            ))
        
        if skipped_count > 0:
            logger.info(f"⏭️ 跳过 {skipped_count} 个无 URL 的库（将由 processors 生成）")
        
        if not download_tasks:
            logger.info("✅ 所有 Forge 库已存在或将由 processors 生成，无需下载")
            return True
        
        logger.info(f"📥 开始下载 {len(download_tasks)} 个 Forge 库...")
        
        def progress_callback(task: DownloadTask):
            completed = sum(1 for t in download_tasks if t.status == "completed")
            self._update_progress("forge_libraries", completed, len(download_tasks))
        
        result = self.downloader.download_batch(download_tasks, progress_callback)
        
        success_rate = result["completed"] / result["total"] if result["total"] > 0 else 0
        logger.info(f"Forge 库下载完成: {result['completed']}/{result['total']} ({success_rate:.1%})")
        
        # 允许少量失败
        return result["failed"] <= result["total"] * 0.1
    
    def _execute_processors(
        self,
        processors: List[Dict],
        data: Dict,
        mc_version: str,
        forge_version: str,
        temp_dir: Path,
        java_path: str,
        custom_name: Optional[str] = None
    ) -> bool:
        """
        执行 Forge processors
        
        Args:
            processors: processor 列表
            data: 变量数据
            mc_version: MC 版本
            forge_version: Forge 版本
            temp_dir: 临时目录（包含提取的数据文件）
            java_path: Java 路径
            custom_name: 自定义版本名称
            
        Returns:
            是否全部成功
        """
        full_version = f"{mc_version}-{forge_version}"
        
        # 确定 MC JAR 的实际路径（考虑自定义名称）
        # 如果使用了自定义名称，JAR 在 versions/custom_name/mc_version.jar
        # 否则在 versions/mc_version/mc_version.jar
        if custom_name:
            mc_jar_path = self.minecraft_dir / "versions" / custom_name / f"{mc_version}.jar"
        else:
            mc_jar_path = self.minecraft_dir / "versions" / mc_version / f"{mc_version}.jar"
        
        logger.info(f"📍 MC JAR 路径: {mc_jar_path}")
        
        if not mc_jar_path.exists():
            logger.error(f"❌ MC JAR 不存在: {mc_jar_path}")
            return False
        
        # 准备变量替换映射
        variables = {
            "MINECRAFT_JAR": str(mc_jar_path),
            "SIDE": "client",
            "MINECRAFT_VERSION": mc_version,
            "ROOT": str(self.minecraft_dir),
            "INSTALLER": str(temp_dir / "forge-installer.jar"),
            "LIBRARY_DIR": str(self.libraries_dir),
        }
        
        # 从 data 中加载变量
        for key, value in data.items():
            if isinstance(value, dict):
                # client/server 分离
                value = value.get("client", value.get("server", ""))
            
            if isinstance(value, str):
                if value.startswith("[") and value.endswith("]"):
                    # Maven 库引用
                    maven_name = value[1:-1]
                    lib_path = self._maven_name_to_path(maven_name)
                    if lib_path:
                        variables[key] = str(self.libraries_dir / lib_path)
                elif value.startswith("/"):
                    # 安装器内的文件引用（如 /data/client.lzma）
                    # 文件已经被提取到 temp_dir/data/xxx，所以直接用 temp_dir + 路径
                    variables[key] = str(temp_dir / value[1:])
                else:
                    variables[key] = value
        
        logger.info(f"🔄 执行 {len(processors)} 个 processors...")
        
        for idx, processor in enumerate(processors):
            # 检查是否需要在客户端执行
            sides = processor.get("sides", ["client", "server"])
            if "client" not in sides:
                logger.debug(f"跳过服务端 processor: {processor.get('jar')}")
                continue
            
            jar_name = processor.get("jar")
            if not jar_name:
                continue
            
            logger.info(f"[{idx+1}/{len(processors)}] 执行: {jar_name}")
            
            # 获取 processor JAR 路径
            jar_path = self._maven_name_to_path(jar_name)
            if not jar_path:
                logger.error(f"无法解析 processor JAR: {jar_name}")
                return False
            
            processor_jar = self.libraries_dir / jar_path
            if not processor_jar.exists():
                logger.error(f"Processor JAR 不存在: {processor_jar}")
                return False
            
            # 构建 classpath
            classpath_items = [str(processor_jar)]
            for cp_lib in processor.get("classpath", []):
                cp_path = self._maven_name_to_path(cp_lib)
                if cp_path:
                    cp_jar = self.libraries_dir / cp_path
                    if cp_jar.exists():
                        classpath_items.append(str(cp_jar))
            
            classpath = ";".join(classpath_items)
            
            # 替换参数中的变量
            args = []
            for arg in processor.get("args", []):
                resolved = self._resolve_variable(arg, variables)
                if resolved:
                    args.append(resolved)
            
            # 获取主类（从 JAR 的 MANIFEST.MF 中读取）
            main_class = self._get_jar_main_class(processor_jar)
            if not main_class:
                logger.error(f"无法获取 processor 主类: {processor_jar}")
                return False
            
            # 执行 processor
            cmd = [java_path, "-cp", classpath, main_class] + args
            logger.debug(f"执行命令: {' '.join(cmd)}")
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5分钟超时
                    cwd=str(self.minecraft_dir)
                )
                
                if result.returncode != 0:
                    logger.error(f"Processor 执行失败: {result.stderr}")
                    logger.error(f"stdout: {result.stdout}")
                    return False
                
                logger.debug(f"Processor 输出: {result.stdout}")
                
            except subprocess.TimeoutExpired:
                logger.error(f"Processor 执行超时: {jar_name}")
                return False
            except Exception as e:
                logger.error(f"Processor 执行异常: {e}")
                return False
            
            self._update_progress("processors", idx + 1, len(processors))
        
        logger.info("✅ 所有 processors 执行完成")
        return True
    
    def _get_jar_main_class(self, jar_path: Path) -> Optional[str]:
        """从 JAR 的 MANIFEST.MF 中获取主类"""
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                manifest = jar.read("META-INF/MANIFEST.MF").decode("utf-8")
                for line in manifest.split("\n"):
                    if line.startswith("Main-Class:"):
                        return line.split(":", 1)[1].strip()
        except Exception as e:
            logger.error(f"读取 JAR 主类失败: {e}")
        return None
    
    def _resolve_variable(self, value: str, variables: Dict[str, str]) -> Optional[str]:
        """解析变量引用"""
        if value.startswith("{") and value.endswith("}"):
            var_name = value[1:-1]
            return variables.get(var_name)
        elif value.startswith("[") and value.endswith("]"):
            # Maven 库引用
            maven_name = value[1:-1]
            lib_path = self._maven_name_to_path(maven_name)
            if lib_path:
                return str(self.libraries_dir / lib_path)
        return value
    
    def _maven_name_to_path(self, name: str) -> Optional[str]:
        """
        将 Maven 名称转换为文件路径
        
        格式: groupId:artifactId:version[:classifier][@extension]
        例如: net.minecraftforge:forge:1.20.1-47.2.0:universal
        """
        try:
            # 处理扩展名
            extension = "jar"
            if "@" in name:
                name, extension = name.rsplit("@", 1)
            
            parts = name.split(":")
            if len(parts) < 3:
                return None
            
            group = parts[0].replace(".", "/")
            artifact = parts[1]
            version = parts[2]
            classifier = parts[3] if len(parts) > 3 else None
            
            if classifier:
                filename = f"{artifact}-{version}-{classifier}.{extension}"
            else:
                filename = f"{artifact}-{version}.{extension}"
            
            return f"{group}/{artifact}/{version}/{filename}"
            
        except Exception as e:
            logger.error(f"解析 Maven 名称失败: {name}, 错误: {e}")
            return None
    
    def _generate_version_json(
        self,
        mc_version: str,
        forge_version: str,
        version_json: Dict,
        custom_name: Optional[str]
    ) -> bool:
        """
        生成 Forge 版本 JSON 文件
        使用完全合并模式（类似PCL2）
        """
        try:
            # 确定版本名称
            if custom_name:
                final_name = custom_name.strip()
            else:
                final_name = version_json.get("id", f"{mc_version}-forge-{forge_version}")
            
            # 创建版本目录
            version_dir = self.minecraft_dir / "versions" / final_name
            version_dir.mkdir(parents=True, exist_ok=True)
            
            # 读取 MC 原版 JSON
            mc_json_path = self.minecraft_dir / "versions" / mc_version / f"{mc_version}.json"
            if not mc_json_path.exists():
                # 尝试在当前目录查找
                mc_json_path = version_dir / f"{mc_version}.json"
            
            if not mc_json_path.exists():
                logger.error(f"MC 原版 JSON 不存在: {mc_json_path}")
                return False
            
            with open(mc_json_path, "r", encoding="utf-8") as f:
                mc_data = json.load(f)
            
            # 合并配置（完全合并模式，不使用 inheritsFrom）
            merged_data = version_json.copy()
            merged_data["id"] = final_name
            merged_data["type"] = "release"
            
            # 删除 inheritsFrom（完全合并，不需要继承）
            if "inheritsFrom" in merged_data:
                del merged_data["inheritsFrom"]
                logger.info("🔧 已移除 inheritsFrom，使用完全合并模式")
            
            # 合并 libraries (MC + Forge，智能去重)
            forge_libs = merged_data.get("libraries", [])
            mc_libs = mc_data.get("libraries", [])
            
            # 构建 Forge 库名称集合
            forge_lib_keys = set()
            for lib in forge_libs:
                name = lib.get("name", "")
                if name:
                    parts = name.split(":")
                    if len(parts) >= 2:
                        # 只用 groupId:artifactId 作为去重键
                        forge_lib_keys.add(f"{parts[0]}:{parts[1]}")
            
            # 合并 libraries
            merged_libs = []
            
            # 先添加 MC 的库（跳过与 Forge 冲突的）
            for lib in mc_libs:
                name = lib.get("name", "")
                if name:
                    parts = name.split(":")
                    if len(parts) >= 2:
                        key = f"{parts[0]}:{parts[1]}"
                        if key not in forge_lib_keys:
                            merged_libs.append(lib)
                else:
                    merged_libs.append(lib)
            
            # 添加所有 Forge 库
            merged_libs.extend(forge_libs)
            
            merged_data["libraries"] = merged_libs
            
            # 保留 MC 的 assetIndex 和 assets
            if "assetIndex" in mc_data:
                merged_data["assetIndex"] = mc_data["assetIndex"]
            if "assets" in mc_data:
                merged_data["assets"] = mc_data["assets"]
            
            # 合并 arguments（MC + Forge）
            if "arguments" in mc_data:
                if "arguments" not in merged_data:
                    merged_data["arguments"] = {}
                
                # 合并 JVM 参数
                mc_jvm = mc_data.get("arguments", {}).get("jvm", [])
                forge_jvm = merged_data.get("arguments", {}).get("jvm", [])
                merged_data["arguments"]["jvm"] = mc_jvm + forge_jvm
                
                # 合并 game 参数
                mc_game = mc_data.get("arguments", {}).get("game", [])
                forge_game = merged_data.get("arguments", {}).get("game", [])
                merged_data["arguments"]["game"] = mc_game + forge_game
                
                logger.info(f"🔧 已合并参数: JVM={len(mc_jvm)}+{len(forge_jvm)}, game={len(mc_game)}+{len(forge_game)}")
            
            # 保存 JSON
            json_path = version_dir / f"{final_name}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 已生成版本 JSON: {json_path.name}")
            logger.info(f"   mainClass: {merged_data.get('mainClass')}")
            logger.info(f"   libraries: {len(merged_libs)} 个")
            
            # 处理 JAR 文件
            target_jar = version_dir / f"{final_name}.jar"
            old_jar = version_dir / f"{mc_version}.jar"  # 原版 JAR（在当前目录）
            mc_jar = self.minecraft_dir / "versions" / mc_version / f"{mc_version}.jar"  # 原版目录的 JAR
            
            if not target_jar.exists():
                if old_jar.exists():
                    # 重命名当前目录的原版 JAR
                    old_jar.rename(target_jar)
                    logger.info(f"✅ 已重命名 JAR: {mc_version}.jar → {final_name}.jar")
                elif mc_jar.exists():
                    # 从原版目录复制
                    shutil.copy2(mc_jar, target_jar)
                    logger.info(f"✅ 已复制 MC JAR: {target_jar.name}")
            
            # 删除当前目录中的原版 JSON（避免混淆）
            old_json = version_dir / f"{mc_version}.json"
            if old_json.exists() and old_json != json_path:
                old_json.unlink()
                logger.info(f"🗑️ 已删除原版 JSON: {mc_version}.json")
            
            return True
            
        except Exception as e:
            logger.error(f"生成版本 JSON 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _update_progress(self, stage: str, current: int, total: int):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(stage, current, total)

