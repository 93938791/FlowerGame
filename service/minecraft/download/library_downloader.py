"""
Minecraft 依赖库下载器
处理 libraries 的下载，支持 rules 过滤和 natives 提取
"""
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from utils.logger import logger
from .http_downloader import HttpDownloader, DownloadTask
from .version_info import RuleEvaluator


class LibraryDownloader:
    """依赖库下载器"""
    
    def __init__(self, minecraft_dir: Path, downloader: HttpDownloader):
        """
        初始化依赖库下载器
        
        Args:
            minecraft_dir: Minecraft 根目录
            downloader: HTTP 下载器
        """
        self.minecraft_dir = minecraft_dir
        self.downloader = downloader
        self.libraries_dir = minecraft_dir / "libraries"
        
        # 确保目录存在
        self.libraries_dir.mkdir(parents=True, exist_ok=True)
    
    def download_libraries(
        self,
        libraries: List[Dict[str, Any]],
        natives_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        下载依赖库
        
        Args:
            libraries: 依赖库列表（已通过 rules 过滤）
            natives_dir: natives 解压目录
            progress_callback: 进度回调 (current, total)
            
        Returns:
            是否全部下载成功
        """
        total_libs = len(libraries)
        logger.info(f"开始下载依赖库，共 {total_libs} 个")
        
        if total_libs == 0:
            return True
        
        # 创建下载任务
        download_tasks = []
        native_tasks = []  # 需要解压的 natives
        
        logger.info(f"🔍 开始解析 {total_libs} 个依赖库...")
        
        for idx, lib in enumerate(libraries, 1):
            # 获取下载信息
            downloads = lib.get("downloads", {})
            
            # 处理普通库
            artifact = downloads.get("artifact")
            if artifact:
                task = self._create_library_task(artifact, lib.get("name", "unknown"))
                if task:
                    download_tasks.append(task)
            elif "name" in lib and "url" in lib:
                # Fabric格式：直接有name和url字段，没有downloads结构
                task = self._create_fabric_library_task(lib)
                if task:
                    download_tasks.append(task)
            
            # 处理 natives（平台相关的本地库）
            classifiers = downloads.get("classifiers")
            if classifiers and natives_dir:
                natives = lib.get("natives", {})
                os_name = RuleEvaluator.get_os_name()
                
                # 获取当前平台的 natives 键名
                native_key = natives.get(os_name)
                if native_key:
                    # 替换变量（如 ${arch}）
                    native_key = native_key.replace("${arch}", RuleEvaluator.get_os_arch())
                    
                    native_info = classifiers.get(native_key)
                    if native_info:
                        task = self._create_library_task(
                            native_info,
                            f"{lib.get('name', 'unknown')} (native)"
                        )
                        if task:
                            download_tasks.append(task)
                            native_tasks.append((task, lib.get("extract", {})))
        
        # 批量下载
        def batch_progress(task: DownloadTask):
            completed = sum(1 for t in download_tasks if t.status == "completed")
            if progress_callback:
                progress_callback(completed, total_libs)
            
            # 每 10 个库输出一次日志
            if task.status == "completed" and completed % 10 == 0:
                logger.info(f"✅ 已下载 {completed}/{total_libs} 个依赖库")
            elif task.status == "failed":
                logger.warning(f"✗ {task.description}")
        
        result = self.downloader.download_batch(download_tasks, batch_progress)
        
        # 解压 natives
        if natives_dir and native_tasks:
            logger.info(f"正在解压 {len(native_tasks)} 个 native 库...")
            natives_dir.mkdir(parents=True, exist_ok=True)
            
            for task, extract_rules in native_tasks:
                if task.status == "completed":
                    self._extract_native(task.save_path, natives_dir, extract_rules)
        
        logger.info(
            f"依赖库下载完成: 成功 {result['completed']}/{result['total']}, "
            f"失败 {result['failed']}"
        )
        
        return result["failed"] == 0
    
    def _create_library_task(
        self,
        artifact_info: Dict[str, Any],
        lib_name: str
    ) -> Optional[DownloadTask]:
        """
        创建库下载任务
        
        Args:
            artifact_info: artifact 信息
            lib_name: 库名称
            
        Returns:
            下载任务，失败返回 None
        """
        url = artifact_info.get("url")
        path = artifact_info.get("path")
        sha1 = artifact_info.get("sha1")
        
        if not url or not path:
            logger.warning(f"库信息不完整: {lib_name}")
            return None
        
        save_path = self.libraries_dir / path
        
        return DownloadTask(
            url=url,
            save_path=save_path,
            sha1=sha1,
            description=f"Library: {lib_name}"
        )
    
    def _create_fabric_library_task(
        self,
        lib: Dict[str, Any]
    ) -> Optional[DownloadTask]:
        """
        创建 Fabric/Forge 格式的库下载任务
        格式：{"name": "xxx", "url": "xxx"}
        
        Args:
            lib: 库信息
            
        Returns:
            下载任务，失败返回 None
        """
        name = lib.get("name")
        url = lib.get("url")
        
        if not name:
            logger.warning("库缺少 name 字段")
            return None
        
        # 解析 Maven 名称获取路径
        lib_info = self.parse_library_name(name)
        if not lib_info:
            logger.warning(f"库名称解析失败: {name}")
            return None
        
        # 构建本地保存路径
        group_path = lib_info["group"].replace(".", "/")
        artifact = lib_info["artifact"]
        version = lib_info["version"]
        classifier = lib_info.get("classifier")
        
        if classifier:
            file_name = f"{artifact}-{version}-{classifier}.jar"
        else:
            file_name = f"{artifact}-{version}.jar"
        
        relative_path = f"{group_path}/{artifact}/{version}/{file_name}"
        save_path = self.libraries_dir / relative_path
        
        # 如果文件已存在，跳过
        if save_path.exists():
            logger.debug(f"库已存在，跳过: {name}")
            return None
        
        # 构建完整的下载URL
        if url:
            # 如果url是完整的（以.jar结尾），直接使用
            if url.endswith(".jar"):
                download_url = url
            else:
                # 否则拼接路径
                download_url = url.rstrip("/") + "/" + relative_path
        else:
            # 根据库名称判断使用哪个仓库
            if "fabricmc" in name.lower() or "fabric" in name.lower():
                download_url = f"https://maven.fabricmc.net/{relative_path}"
            elif "minecraftforge" in name.lower() or "forge" in name.lower():
                # 使用 BMCL Maven 镜像（Forge 库）
                download_url = f"https://bmclapi2.bangbang93.com/maven/{relative_path}"
            else:
                # 默认使用 BMCL Maven 镜像
                download_url = f"https://bmclapi2.bangbang93.com/maven/{relative_path}"
        
        logger.debug(f"库: {name}")
        logger.debug(f"  下载URL: {download_url}")
        logger.debug(f"  保存路径: {save_path}")
        
        return DownloadTask(
            url=download_url,
            save_path=save_path,
            sha1=None,  # 这类库通常不提供sha1
            description=f"Library: {name}"
        )
    
    def _extract_native(
        self,
        zip_path: Path,
        target_dir: Path,
        extract_rules: Dict[str, Any]
    ):
        """
        解压 native 库
        
        Args:
            zip_path: ZIP 文件路径
            target_dir: 目标目录
            extract_rules: 解压规则（排除列表）
        """
        try:
            exclude = extract_rules.get("exclude", [])
            
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for file_info in zip_ref.infolist():
                    file_name = file_info.filename
                    
                    # 检查是否应该排除
                    should_exclude = False
                    for pattern in exclude:
                        if file_name.startswith(pattern):
                            should_exclude = True
                            break
                    
                    if not should_exclude:
                        zip_ref.extract(file_info, target_dir)
            
            logger.debug(f"✓ 解压 native: {zip_path.name}")
        
        except Exception as e:
            logger.error(f"解压 native 失败: {zip_path.name}, 错误: {e}")
    
    def parse_library_name(self, name: str) -> Optional[Dict[str, str]]:
        """
        解析库名称（Maven 格式）
        
        格式: groupId:artifactId:version[:classifier]
        例如: com.mojang:authlib:3.11.49
        
        Args:
            name: 库名称
            
        Returns:
            解析结果 {group, artifact, version, classifier}
        """
        parts = name.split(":")
        if len(parts) < 3:
            return None
        
        result = {
            "group": parts[0],
            "artifact": parts[1],
            "version": parts[2],
            "classifier": parts[3] if len(parts) > 3 else None
        }
        
        return result
    
    def get_library_path(self, library_info: Dict[str, str]) -> Path:
        """
        根据库信息获取文件路径
        
        Args:
            library_info: 库信息（从 parse_library_name 获取）
            
        Returns:
            文件路径
        """
        group_path = library_info["group"].replace(".", "/")
        artifact = library_info["artifact"]
        version = library_info["version"]
        classifier = library_info.get("classifier")
        
        # 构建文件名
        if classifier:
            file_name = f"{artifact}-{version}-{classifier}.jar"
        else:
            file_name = f"{artifact}-{version}.jar"
        
        # 构建完整路径
        return self.libraries_dir / group_path / artifact / version / file_name
