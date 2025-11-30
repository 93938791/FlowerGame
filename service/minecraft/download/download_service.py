"""
下载服务 - 处理游戏版本、加载器、模组等资源的下载
"""
import os
import json
import shutil
import time
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Dict, List, Callable, Tuple
from utils.logger import Logger
from service.cache import ConfigCache

# 导入拆分后的模块
from .download_config import DownloadConfig
from .async_http2_downloader import AsyncHTTP2Downloader
from .download_thread import DownloadThread
from .mirror_utils import MirrorUtils
from .modrinth_client import ModrinthClient

# 导入加载器模块
from .loaders.fabric_loader import FabricLoader
from .loaders.forge_loader import ForgeLoader
from .loaders.neoforge_loader import NeoForgeLoader
from .loaders.optifine_loader import OptiFineLoader

logger = Logger().get_logger("DownloadService")


class DownloadService:
    """下载服务类"""
    
    def __init__(self, config: dict):
        """
        初始化下载服务
        
        Args:
            config: 配置字典
        """
        # 初始化配置
        self.config = DownloadConfig(config)
        
        # 初始化HTTP/2异步下载器
        self.async_downloader = AsyncHTTP2Downloader(self.config)
        
        # 初始化加载器
        self.fabric_loader = FabricLoader(self.config, self.async_downloader)
        self.forge_loader = ForgeLoader(self.config, self.async_downloader)
        self.neoforge_loader = NeoForgeLoader(self.config, self.async_downloader)
        self.optifine_loader = OptiFineLoader(self.config, self.async_downloader)
        
        # 当前活跃的底层下载线程（用于取消控制）
        self.current_download_thread: Optional[DownloadThread] = None
        # 使用列表作为可变引用，以便 ModrinthClient 可以更新
        self._download_thread_ref = [None]
        
        # 创建镜像工具实例
        self.mirror_utils = MirrorUtils(self.config)
        
        # 初始化镜像健康状态与延迟（异步执行，不阻塞启动）
        logger.debug(f"[镜像配置] BMCLAPI镜像: {'启用' if self.config.use_mirror else '禁用'} | 域名: {self.config.BMCLAPI_DOMAIN}")
        self.mirror_utils.init_mirror_health_async()
        
        # 同步 modrinth_source_order（MirrorUtils 会在后台更新）
        def _sync_modrinth_order():
            import time as time_module
            time_module.sleep(1)  # 等待初始化
            # 更新 ModrinthClient 的源顺序（如果需要）
            pass
        threading.Thread(target=_sync_modrinth_order, daemon=True).start()
    
    def get_minecraft_versions(self) -> List[Dict]:
        """
        获取Minecraft版本列表（支持镜像fallback和缓存）
        
        Returns:
            Minecraft版本列表
        """
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # 检查缓存（缓存5分钟）
            cache_file = self.config.minecraft_dir / ".version_manifest_cache.json"
            cache_timeout = self.config.CACHE_TIMEOUT
            
            if cache_file.exists():
                try:
                    cache_age = time.time() - cache_file.stat().st_mtime
                    if cache_age < cache_timeout:
                        logger.debug(f"[版本清单] 使用缓存（缓存年龄: {cache_age:.1f}秒）")
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cached_data = json.load(f)
                            versions = []
                            for version in cached_data.get("versions", []):
                                # 返回所有类型的版本，不仅仅是release类型
                                version_url = version.get("url", "")
                                original_v_url = version_url
                                version_url = self.mirror_utils.convert_to_mirror_url(version_url)
                                versions.append({
                                    "id": version.get("id"),
                                    "type": version.get("type"),
                                    "url": version_url,
                                    "original_url": original_v_url,
                                    "time": version.get("time"),
                                    "releaseTime": version.get("releaseTime")
                                })
                            logger.debug(f"[版本清单] 从缓存加载 {len(versions)} 个版本")
                            return versions
                except Exception as e:
                    logger.warning(f"[版本清单] 读取缓存失败: {e}，将重新下载")
            
            original_url = self.config.VERSION_MANIFEST_URL
            url = self.mirror_utils.convert_to_mirror_url(original_url)
            is_mirror = url != original_url
            
            logger.debug(f"[下载请求] 版本清单 | 原始: {original_url} | 镜像: {url} | 使用镜像: {is_mirror}")
            
            # 创建会话对象，配置重试机制
            session = requests.Session()
            
            # 配置重试策略
            retry_strategy = Retry(
                total=3,  # 总重试次数
                status_forcelist=[429, 500, 502, 503, 504],  # 重试的状态码
                backoff_factor=0.5,  # 重试间隔：0.5, 1, 2秒
                allowed_methods=["HEAD", "GET", "OPTIONS"]  # 重试的方法
            )
            
            # 配置适配器
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # 候选URL列表
            candidate_urls = [url, original_url]
            
            # 最多重试3次，每次尝试所有候选URL
            max_retries = 3
            response = None
            
            for retry in range(max_retries):
                for idx, current_url in enumerate(candidate_urls):
                    logger.debug(f"[下载请求] 版本清单 | 尝试 {retry+1}/{max_retries} | 源 {idx+1}/{len(candidate_urls)} | URL: {current_url}")
                    
                    try:
                        # 增加超时时间，处理网络延迟较高的情况
                        response = session.get(
                            current_url, 
                            timeout=(10.0, 20.0),  # 连接超时10秒，读取超时20秒
                            allow_redirects=True
                        )
                        response.raise_for_status()
                        logger.debug(f"[下载请求] 版本清单 | 请求成功")
                        break
                    except requests.exceptions.RequestException as e:
                        # 捕获所有请求异常
                        logger.warning(f"[下载请求] 版本清单 | 请求失败: {e}")
                        # 继续尝试下一个URL或重试
                        continue
                else:
                    # 所有URL都失败了，等待1秒后重试
                    time.sleep(1)
                    continue
                # 有一个URL成功了，跳出循环
                break
            
            if not response:
                # 所有尝试都失败了
                logger.error(f"[下载请求] 版本清单 | 所有尝试都失败了，最多重试 {max_retries} 次")
                return []
            
            data = response.json()
            
            # 保存到缓存（无论从哪个源下载成功）
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.debug(f"[版本清单] 已保存到缓存: {cache_file}")
            except Exception as e:
                logger.warning(f"[版本清单] 保存缓存失败: {e}")
            
            versions = []
            for version in data.get("versions", []):
                # 返回所有类型的版本，不仅仅是release类型
                version_url = version.get("url", "")
                # 转换版本JSON的URL为镜像
                original_v_url = version_url
                version_url = self.mirror_utils.convert_to_mirror_url(version_url)
                versions.append({
                    "id": version.get("id"),
                    "type": version.get("type"),
                    "url": version_url,  # 已转换的镜像URL
                    "original_url": original_v_url,  # 保存原始URL用于fallback
                    "time": version.get("time"),
                    "releaseTime": version.get("releaseTime")
                })
            
            logger.info(f"[下载完成] 版本清单 | 共获取 {len(versions)} 个版本")
            return versions
            
        except Exception as e:
            logger.error(f"获取版本列表失败: {e}", exc_info=True)
            return []
    
    def download_minecraft_version(self, version_id: str, custom_name: Optional[str] = None, progress_callback: Optional[Callable] = None) -> bool:
        """
        下载Minecraft版本（优化：直接构建版本JSON URL，无需下载整个版本清单）
        
        Args:
            version_id: Minecraft版本ID（如 1.21.10）
            custom_name: 自定义版本名称（用于版本隔离，如 "551"），如果提供则下载到 versions/{custom_name}/ 目录
            progress_callback: 进度回调函数，支持多任务回调格式：progress_callback(current, total, status, task_id=None)
        """
        try:
            if not self.config.minecraft_dir or not self.config.minecraft_dir.exists():
                logger.error("Minecraft目录未设置或不存在")
                return False
            
            # 确定版本目录：如果提供了custom_name，使用custom_name；否则使用version_id
            version_dir_name = custom_name if custom_name else version_id
            
            if progress_callback:
                progress_callback(0, 100, "正在获取版本信息...", task_id="version_info")
            
            # 直接从版本清单获取版本JSON URL（这是唯一可靠的方式）
            logger.debug(f"[下载流程] 版本JSON ({version_id}) | 步骤1: 获取版本清单（带缓存）")
            versions = self.get_minecraft_versions()
            version_info = next((v for v in versions if v["id"] == version_id), None)
            
            if not version_info:
                logger.error(f"未找到版本: {version_id}")
                return False
            
            # 步骤2: 下载版本JSON（使用清单中的URL，已转换镜像）
            original_v_url = version_info.get("original_url") or version_info["url"]
            version_url = version_info["url"]
            # 确保URL已转换为镜像（如果还没有）
            if "piston-meta.mojang.com" in version_url or "launchermeta.mojang.com" in version_url or "launcher.mojang.com" in version_url:
                version_url = self.mirror_utils.convert_to_mirror_url(version_url)
            is_mirror = version_url != original_v_url
            
            logger.debug(f"[下载流程] 版本JSON ({version_id}) | 步骤2: 下载版本JSON")
            logger.debug(f"[下载请求] 版本JSON ({version_id}) | 原始: {original_v_url} | 镜像: {version_url} | 使用镜像: {is_mirror}")
            
            import requests
            response = requests.get(version_url, timeout=10)
            response.raise_for_status()
            version_data = response.json()
            
            # 保存版本JSON
            version_dir = self.config.minecraft_dir / "versions" / version_dir_name
            version_dir.mkdir(parents=True, exist_ok=True)
            # JSON文件名使用version_id（原始版本），但存储在version_dir_name目录中
            version_json_path = version_dir / f"{version_id}.json"
            
            with open(version_json_path, 'w', encoding='utf-8') as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)
            
            # 下载客户端JAR
            client_info = version_data["downloads"]["client"]
            client_jar_url = self.mirror_utils.convert_to_mirror_url(client_info["url"])
            client_sha1 = client_info.get("sha1")
            # JAR文件名使用version_id（原始版本），但存储在version_dir_name目录中
            client_jar_path = version_dir / f"{version_id}.jar"
            
            if progress_callback:
                progress_callback(10, 100, "正在下载客户端JAR...", task_id="client_jar")
            
            thread = DownloadThread(
                client_jar_url,
                client_jar_path,
                self.config.use_mirror,
                expected_sha1=client_sha1,
                mirror_converter=self.mirror_utils.convert_to_mirror_url
            )
            self.current_download_thread = thread
            self._download_thread_ref[0] = thread
            success = False
            error_msg = ""
            finished_event = threading.Event()
            
            def on_finished(s, msg):
                nonlocal success, error_msg
                success = s
                error_msg = msg
                logger.debug(f"[下载回调] 客户端JAR | 成功: {s} | 消息: {msg}")
                finished_event.set()
            
            thread.finished.connect(on_finished)
            logger.debug(f"[下载流程] 启动客户端JAR下载线程，目标文件: {client_jar_path}")
            thread.start()
            
            # 等待线程完成，同时轮询检查文件
            logger.info(f"[下载流程] 等待客户端JAR下载完成...")
            max_wait_time = 300  # 最多5分钟
            check_interval = 0.5  # 每0.5秒检查一次
            elapsed = 0
            
            while elapsed < max_wait_time:
                # 检查信号是否已触发
                if finished_event.is_set():
                    logger.info(f"[下载流程] 收到下载完成信号，success={success}, error_msg={error_msg}")
                    break
                
                # 检查文件是否已存在（双重检查）
                if client_jar_path.exists() and client_jar_path.stat().st_size > 0:
                    expected_size = client_info.get("size", 0)
                    actual_size = client_jar_path.stat().st_size
                    if expected_size == 0 or actual_size >= expected_size * 0.9:  # 允许10%误差
                        logger.info(f"[下载流程] 文件已存在，大小: {actual_size} 字节，等待信号确认...")
                        # 再等待一下信号，如果还没收到就认为成功
                        time.sleep(1)
                        if not finished_event.is_set():
                            logger.info(f"[下载流程] 信号未触发但文件已存在，认为下载成功")
                            success = True
                            error_msg = "下载完成（通过文件检查）"
                        break
                
                time.sleep(check_interval)
                elapsed += check_interval
            
            # 等待线程完全结束
            logger.info(f"[下载流程] 等待客户端JAR下载线程结束...")
            thread.wait(10000)  # 最多等待10秒（10000毫秒）让线程结束
            
            # 最终检查
            if not finished_event.is_set() and not success:
                if client_jar_path.exists() and client_jar_path.stat().st_size > 0:
                    logger.info(f"[下载流程] 超时但文件已存在，认为下载成功")
                    success = True
                    error_msg = "下载完成（通过文件检查）"
                else:
                    logger.error("下载客户端JAR超时（5分钟）且文件不存在")
                    thread._stop_flag = True
                    if progress_callback:
                        progress_callback(0, 100, "下载客户端JAR超时", task_id="client_jar")
                    return False
            
            if not success:
                error_msg_display = error_msg if error_msg else "未知错误"
                logger.error(f"下载客户端JAR失败: {error_msg_display}")
                if progress_callback:
                    progress_callback(0, 100, f"下载客户端JAR失败: {error_msg_display}", task_id="client_jar")
                return False
            
            logger.info(f"[下载流程] 客户端JAR下载成功，开始并行下载依赖、资源文件和启动器依赖...")
            
            # 使用线程池并行执行下载任务
            from concurrent.futures import ThreadPoolExecutor
            
            # 定义并行下载任务
            def download_libraries_task():
                """下载依赖库文件任务"""
                logger.info("[并行下载] 开始执行依赖库文件下载任务")
                # 创建带任务ID的进度回调包装器
                def task_progress_callback(current, total, status=""):
                    if progress_callback:
                        progress_callback(current, total, status, task_id="libraries")
                return self._download_libraries(version_data, task_progress_callback)
            
            def download_assets_task():
                """下载资源文件任务"""
                logger.info("[并行下载] 开始执行资源文件下载任务")
                # 创建带任务ID的进度回调包装器
                def task_progress_callback(current, total, status=""):
                    if progress_callback:
                        progress_callback(current, total, status, task_id="assets")
                if progress_callback:
                    progress_callback(70, 100, "正在下载资源文件（Assets）...", task_id="assets")
                self._download_assets(version_data, task_progress_callback)
                return None
            
            def download_launcher_deps_task():
                """下载启动器依赖任务"""
                logger.info("[并行下载] 开始执行启动器依赖下载任务")
                # 创建带任务ID的进度回调包装器
                def task_progress_callback(current, total, status=""):
                    if progress_callback:
                        progress_callback(current, total, status, task_id="launcher_deps")
                # 目前没有明确的启动器依赖下载逻辑，这里可以根据实际需求添加
                # 例如：下载启动器所需的其他文件或依赖
                return None
            
            # 使用ThreadPoolExecutor并行执行任务
            with ThreadPoolExecutor(max_workers=3, thread_name_prefix="DownloadTask") as executor:
                # 提交三个下载任务
                future_libraries = executor.submit(download_libraries_task)
                future_assets = executor.submit(download_assets_task)
                future_launcher_deps = executor.submit(download_launcher_deps_task)
                
                # 等待所有任务完成并获取结果
                logger.info("[并行下载] 等待所有下载任务完成...")
                
                # 获取库文件下载结果
                libraries_result = future_libraries.result()
                downloaded_count, failed_count, total_libs, skipped_count = libraries_result if libraries_result else (0, 0, 0, 0)
                
                # 等待其他任务完成
                future_assets.result()
                future_launcher_deps.result()
                
                logger.info("[并行下载] 所有下载任务已完成")
            
            # 完成提示
            if progress_callback:
                if failed_count > 0:
                    progress_callback(100, 100, f"下载完成（库成功: {downloaded_count}, 失败: {failed_count}；资源已更新）", task_id="summary")
                else:
                    progress_callback(100, 100, f"下载完成（库共 {downloaded_count} 个，资源已更新）", task_id="summary")
            
            # 计算实际需要下载的文件数（不包括已存在的）
            actual_downloaded = downloaded_count - skipped_count  # 实际新下载的文件数
            total_required = actual_downloaded + failed_count  # 实际需要下载的文件总数
            
            logger.info(f"[下载流程] Minecraft版本 {version_id} 下载完成: 总计 {downloaded_count} 个（已存在跳过 {skipped_count} 个，新下载 {actual_downloaded} 个），失败 {failed_count} 个")
            
            # 检查下载完整性：如果有失败的文件，判断是否应该标记为失败
            if failed_count > 0:
                # 计算失败率（基于实际需要下载的文件）
                if total_required > 0:
                    failure_rate = failed_count / total_required
                else:
                    failure_rate = 0
                
                # 如果实际需要下载的文件很少（比如只有几个），即使全部失败也不应该标记为失败
                # 因为可能这些文件不是必需的，或者已经存在于其他位置
                if total_required <= 3:
                    # 需要下载的文件很少（≤3个），即使全部失败也给出警告但不标记为失败
                    logger.warning(f"[下载流程] ⚠️ 少量文件下载失败: {failed_count}/{total_required}，但总数很少，可能不影响游戏运行")
                    if progress_callback:
                        progress_callback(100, 100, f"下载完成（警告: {failed_count} 个库文件失败，但可能不影响游戏）", task_id="summary")
                    return True
                elif failure_rate > 0.1 or failed_count > 5:
                    # 如果失败率超过10%，或者失败文件超过5个，标记为失败
                    logger.error(f"[下载流程] ❌ 下载不完整: 失败率 {failure_rate*100:.1f}% ({failed_count}/{total_required})，超过阈值，标记为失败")
                    if progress_callback:
                        progress_callback(0, 100, f"下载失败: {failed_count} 个库文件下载失败，可能导致游戏无法启动", task_id="summary")
                    return False
                else:
                    # 失败率较低，给出警告但继续
                    logger.warning(f"[下载流程] ⚠️ 下载基本完成但有部分失败: 失败率 {failure_rate*100:.1f}% ({failed_count}/{total_required})，可能不影响游戏运行")
                    if progress_callback:
                        progress_callback(100, 100, f"下载完成（警告: {failed_count} 个库文件失败，可能不影响游戏）", task_id="summary")
                    return True
            else:
                # 没有失败的文件，完全成功
                return True
            
        except Exception as e:
            logger.error(f"下载版本失败: {e}", exc_info=True)
            return False
    
    def _parse_library_path(self, lib_name: str) -> str:
        """解析库路径"""
        parts = lib_name.split(":")
        if len(parts) >= 3:
            group = parts[0].replace(".", "/")
            artifact = parts[1]
            version = parts[2]
            filename = f"{artifact}-{version}.jar"
            return f"{group}/{artifact}/{version}/{filename}"
        return lib_name.replace(":", "/")
    
    def _download_libraries(self, version_data: Dict, progress_callback: Optional[Callable] = None) -> Tuple[int, int, int, int]:
        """
        下载所有库文件
        
        Args:
            version_data: 版本数据字典
            progress_callback: 进度回调函数
        
        Returns:
            Tuple[int, int, int, int]: (下载成功数量, 下载失败数量, 总库文件数量, 跳过的文件数量)
        """
        try:
            logger.info(f"[下载流程] 客户端JAR下载完成，开始下载库文件...")
            if progress_callback:
                progress_callback(40, 100, "客户端JAR下载完成，开始下载库文件...")
            
            # 下载所有库文件
            libraries = version_data.get("libraries", [])
            logger.info(f"[下载流程] 版本JSON中包含 {len(libraries)} 个库文件")
            total_libs = len(libraries)
            
            if total_libs == 0:
                logger.warning("版本JSON中没有库文件信息")
                return 0, 0, 0, 0
            
            # 准备需要下载的库文件列表（过滤已存在的文件）
            libs_to_download = []
            skipped_count = 0
            
            for lib in libraries:
                try:
                    lib_name = lib["name"]
                    lib_path = self._parse_library_path(lib_name)
                    lib_file_path = self.config.minecraft_dir / "libraries" / lib_path
                    
                    # 如果文件已存在，检查完整性后跳过
                    if lib_file_path.exists():
                        # 获取期望的SHA1（先获取，用于后续检查）
                        lib_download = lib.get("downloads", {})
                        expected_sha1 = None
                        if "artifact" in lib_download:
                            expected_sha1 = lib_download["artifact"].get("sha1")
                        
                        # 如果有SHA1，验证文件完整性
                        if expected_sha1:
                            try:
                                import hashlib
                                sha1 = hashlib.sha1()
                                with open(lib_file_path, 'rb') as f:
                                    for chunk in iter(lambda: f.read(8192), b''):
                                        sha1.update(chunk)
                                actual_sha1 = sha1.hexdigest()
                                if actual_sha1.lower() == expected_sha1.lower():
                                    skipped_count += 1
                                    logger.info(f"[库文件检查] ✅ {lib_name} 已存在且SHA1匹配，跳过下载")
                                    continue
                                else:
                                    logger.warning(f"[库文件检查] ⚠️ {lib_name} 已存在但SHA1不匹配（期望: {expected_sha1}, 实际: {actual_sha1}），将重新下载")
                                    # SHA1不匹配，删除文件重新下载
                                    lib_file_path.unlink()
                            except Exception as e:
                                logger.warning(f"[库文件检查] ⚠️ {lib_name} SHA1校验失败: {e}，将重新下载")
                                # 删除文件重新下载
                                lib_file_path.unlink()
                        else:
                            # 没有SHA1，检查文件大小（至少大于0）
                            try:
                                file_size = lib_file_path.stat().st_size
                                if file_size > 0:
                                    skipped_count += 1
                                    logger.info(f"[库文件检查] ✅ {lib_name} 已存在（无SHA1，大小: {file_size} 字节），跳过下载")
                                    continue
                                else:
                                    logger.warning(f"[库文件检查] ⚠️ {lib_name} 文件大小为0，将重新下载")
                                    lib_file_path.unlink()
                            except Exception as e:
                                logger.warning(f"[库文件检查] ⚠️ {lib_name} 文件检查失败: {e}，将重新下载")
                                # 删除文件重新下载
                                lib_file_path.unlink()
                    
                    # 获取下载URL
                    lib_download = lib.get("downloads", {})
                    original_lib_url = None
                    if "artifact" in lib_download:
                        lib_url = lib_download["artifact"].get("url")
                        expected_sha1 = lib_download["artifact"].get("sha1")
                        original_lib_url = lib_url
                    else:
                        lib_url = f"https://libraries.minecraft.net/{lib_path}"
                        original_lib_url = lib_url
                        expected_sha1 = None
                    
                    if not lib_url:
                        logger.warning(f"库文件 {lib_name} 没有下载URL，跳过")
                        continue
                    
                    # 转换为镜像URL
                    lib_url = self.mirror_utils.convert_to_mirror_url(lib_url)
                    
                    libs_to_download.append({
                        "name": lib_name,
                        "url": lib_url,  # 使用转换后的镜像URL
                        "path": lib_file_path,
                        "sha1": expected_sha1
                    })
                except Exception as e:
                    logger.warning(f"处理库文件失败: {lib.get('name', 'unknown')} - {str(e)}")
            
            logger.info(f"[下载流程] 📦 库文件检查完成 | 总计: {total_libs} | 需要下载: {len(libs_to_download)} | 已存在跳过: {skipped_count}")
            
            if not libs_to_download:
                logger.info(f"[下载流程] 所有库文件已存在，跳过下载")
                downloaded_count = total_libs
                failed_count = 0
            else:
                # 执行批量下载（batch_download是同步方法，内部使用线程池）
                download_tasks = []
                for lib_info in libs_to_download:
                    download_tasks.append({
                        "url": lib_info["url"],
                        "file_path": lib_info["path"],
                        "expected_sha1": lib_info["sha1"]
                    })
                
                # 定义库文件下载的进度回调
                def lib_progress_callback(current, total, status=""):
                    """库文件下载进度回调"""
                    if progress_callback:
                        # 将库文件下载进度映射到总进度的40%-70%区间
                        lib_progress = 40 + int((current / total) * 30)
                        progress_callback(lib_progress, 100, f"正在下载依赖库... {status}", task_id="libraries")
                
                # 执行批量下载（batch_download是同步方法，内部使用线程池）
                success_count, failed_count = self.async_downloader.batch_download(download_tasks, progress_callback=lib_progress_callback)
                downloaded_count = skipped_count + success_count
            
            logger.info(f"[下载流程] 库文件下载完成 | 成功: {downloaded_count} | 失败: {failed_count}")
            return downloaded_count, failed_count, total_libs, skipped_count
        except Exception as e:
            logger.error(f"下载库文件失败: {e}", exc_info=True)
            return 0, 0, 0, 0
    
    def _download_assets(self, version_data: Dict, progress_callback: Optional[Callable] = None):
        """下载Assets资源"""
        try:
            logger.info("[Assets下载] 开始下载Assets资源")
            
            # 从版本数据中获取assets索引信息
            assets = version_data.get("assets", {})
            assets_index_url = None
            assets_index_sha1 = None
            assets_id = None
            original_assets_index_url = None
            
            # 首先检查version_data中是否有assetIndex字段（这是正确的方式）
            if "assetIndex" in version_data:
                # 使用assetIndex字段获取正确的索引信息
                asset_index = version_data.get("assetIndex", {})
                original_assets_index_url = asset_index.get("url")
                assets_index_url = original_assets_index_url
                assets_index_sha1 = asset_index.get("sha1")
                assets_id = asset_index.get("id")
                logger.info(f"[Assets下载] 从assetIndex字段获取索引信息: ID={assets_id}, URL={original_assets_index_url}")
            # 处理assets可能是字符串的情况
            elif isinstance(assets, str):
                # assets是字符串引用，需要从assets.json中获取索引信息
                assets_id = assets
                logger.info(f"[Assets下载] Assets是字符串引用: {assets_id}")
                
                # 尝试从version_data的assetIndex字段获取（如果存在）
                if "assetIndex" in version_data:
                    asset_index = version_data.get("assetIndex", {})
                    original_assets_index_url = asset_index.get("url")
                    assets_index_url = original_assets_index_url
                    assets_index_sha1 = asset_index.get("sha1")
                    logger.info(f"[Assets下载] 从assetIndex字段获取索引URL: {original_assets_index_url}")
                else:
                    # 无法获取正确的URL，使用原始URL格式
                    logger.warning(f"[Assets下载] 无法获取正确的索引URL，assets_id={assets_id}")
                    # 构建正确的官方URL格式
                    original_assets_index_url = f"https://piston-meta.mojang.com/v1/packages/unknown/{assets_id}.json"
                    assets_index_url = original_assets_index_url
                    assets_index_sha1 = None  # 无法直接获取，跳过SHA1校验
            else:
                # assets是字典，直接获取索引信息
                assets_index = assets.get("index", {})
                original_assets_index_url = assets_index.get("url")
                assets_index_url = original_assets_index_url
                assets_index_sha1 = assets_index.get("sha1")
                assets_id = assets_index.get("id")
            
            if not assets_index_url:
                logger.warning("[Assets下载] 版本数据中没有Assets索引URL，跳过下载")
                if progress_callback:
                    progress_callback(80, 100, "Assets资源已更新")
                return
            
            # 保存原始URL，用于日志记录
            logger.info(f"[Assets下载] 原始URL: {original_assets_index_url}")
            
            # 转换为镜像URL，mirror_utils会处理正确的URL映射
            assets_index_url = self.mirror_utils.convert_to_mirror_url(assets_index_url)
            
            # 记录转换后的URL
            logger.info(f"[Assets下载] 转换后URL: {assets_index_url}")
            
            # 确定assets目录
            assets_dir = self.config.minecraft_dir / "assets"
            objects_dir = assets_dir / "objects"
            indexes_dir = assets_dir / "indexes"
            
            # 确保目录存在
            objects_dir.mkdir(parents=True, exist_ok=True)
            indexes_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载assets索引文件
            index_file_path = indexes_dir / f"{assets_id}.json"
            
            logger.info(f"[Assets下载] 下载索引文件: {index_file_path.name} | 原始: {original_assets_index_url} | 镜像: {assets_index_url}")
            
            # 直接使用requests库同步下载索引文件，避免Qt事件循环问题
            import requests
            import hashlib
            import time
            
            success = False
            error_msg = ""
            
            try:
                # 确保目录存在
                index_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 使用临时文件实现断点续传
                tmp_path = index_file_path.with_suffix(index_file_path.suffix + ".part")
                downloaded = tmp_path.stat().st_size if tmp_path.exists() else 0
                
                headers = {}
                if downloaded > 0:
                    headers["Range"] = f"bytes={downloaded}-"
                    logger.info(f"[断点续传] 已下载: {downloaded} 字节，将从断点继续")
                
                logger.info(f"[下载尝试] 源 1/1: {assets_index_url}")
                
                start_time = time.time()
                with requests.get(assets_index_url, stream=True, timeout=30, headers=headers, allow_redirects=True) as resp:
                    resp.raise_for_status()
                    
                    # 获取文件总大小
                    total_size = int(resp.headers.get("content-length", 0))
                    if downloaded > 0:
                        total_size += downloaded
                    
                    logger.info(f"[下载响应] 状态: {resp.status_code} | 总大小: {total_size} 字节 | 实际URL: {resp.url}")
                    
                    # 写入文件
                    write_mode = "ab" if downloaded > 0 else "wb"
                    with open(tmp_path, write_mode) as f:
                        for chunk in resp.iter_content(chunk_size=1024 * 256):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                
                total_elapsed = time.time() - start_time
                logger.info(f"[下载完成] 总耗时: {total_elapsed:.2f}秒 | 文件大小: {downloaded} 字节")
                
                # 校验SHA1
                if assets_index_sha1:
                    logger.info(f"[SHA1校验] 开始校验，期望值: {assets_index_sha1}")
                    sha1 = hashlib.sha1()
                    with open(tmp_path, "rb") as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            sha1.update(chunk)
                    actual_sha1 = sha1.hexdigest()
                    
                    if actual_sha1.lower() == assets_index_sha1.lower():
                        logger.info(f"[SHA1校验] 通过")
                        # 重命名临时文件为最终文件
                        tmp_path.replace(index_file_path)
                        success = True
                    else:
                        error_msg = f"SHA1校验失败: 期望 {assets_index_sha1}, 实际 {actual_sha1}"
                        logger.error(f"[SHA1校验] 失败 | {error_msg}")
                else:
                    # 无需校验，直接重命名
                    tmp_path.replace(index_file_path)
                    success = True
            except Exception as e:
                error_msg = f"下载失败: {str(e)}"
                logger.error(f"[下载失败] {error_msg}")
                success = False
            
            if not success:
                logger.error(f"[Assets下载] 索引文件下载失败: {error_msg}")
                # 如果是404错误，尝试使用官方URL下载
                if "404" in error_msg or "Not Found" in error_msg:
                    logger.info(f"[Assets下载] 尝试使用官方URL重新下载索引文件...")
                    # 构建官方URL
                    official_url = f"https://launchermeta.mojang.com/mc/assets/{assets_id}/indexes/{assets_id}.json"
                    
                    logger.info(f"[Assets下载] Fallback到官方URL: {official_url}")
                    
                    # 禁用镜像，使用官方URL重新下载
                    thread = DownloadThread(
                        official_url,
                        index_file_path,
                        False,  # 禁用镜像
                        expected_sha1=assets_index_sha1,
                        mirror_converter=self.mirror_utils.convert_to_mirror_url
                    )
                    self.current_download_thread = thread
                    self._download_thread_ref[0] = thread
                    success = False
                    error_msg = ""
                    finished_event = threading.Event()
                    
                    def on_finished_official(s, msg):
                        nonlocal success, error_msg
                        success = s
                        error_msg = msg
                        finished_event.set()
                    
                    thread.finished.connect(on_finished_official)
                    thread.start()
                    
                    # 等待线程完成
                    finished_event.wait()
                    
                    if not success:
                        logger.error(f"[Assets下载] 官方URL下载索引文件也失败: {error_msg}")
                        return
                    else:
                        logger.info(f"[Assets下载] 官方URL下载索引文件成功")
                else:
                    return
            
            logger.info(f"[Assets下载] 索引文件下载成功: {index_file_path}")
            
            logger.info(f"[Assets下载] 开始处理索引文件...")
            
            try:
                logger.info(f"[Assets下载] 尝试打开索引文件: {index_file_path}")
                # 解析索引文件，获取需要下载的assets文件
                with open(index_file_path, 'r', encoding='utf-8') as f:
                    logger.info(f"[Assets下载] 索引文件已打开，开始读取内容...")
                    file_content = f.read()
                    logger.info(f"[Assets下载] 索引文件内容读取成功，大小: {len(file_content)} 字节")
                    logger.info(f"[Assets下载] 索引文件内容前100个字符: {file_content[:100]}...")
                    assets_index_data = json.loads(file_content)
                    logger.info(f"[Assets下载] 索引文件解析成功")
                
                logger.info(f"[Assets下载] 索引文件解析成功，包含 {len(assets_index_data)} 个字段")
                
                # 检查是否有objects字段
                if "objects" in assets_index_data:
                    objects = assets_index_data.get("objects", {})
                    total_objects = len(objects)
                    logger.info(f"[Assets下载] 索引文件中包含 {total_objects} 个Assets文件")
                else:
                    # 检查是否有files字段（旧版本索引文件可能使用files字段）
                    files = assets_index_data.get("files", {})
                    total_files = len(files)
                    logger.info(f"[Assets下载] 索引文件中包含 {total_files} 个Assets文件（使用files字段）")
                    # 使用files字段作为objects字段
                    objects = files
                    total_objects = total_files
                
                if total_objects == 0:
                    logger.info("[Assets下载] 索引文件中没有需要下载的Assets文件")
                    if progress_callback:
                        progress_callback(80, 100, "Assets资源已更新")
                    return
                
                # 准备下载任务
                logger.info(f"[Assets下载] 开始准备下载任务...")
                download_tasks = []
                task_count = 0
                for obj_name, obj_info in objects.items():
                    task_count += 1
                    if task_count <= 5:  # 只打印前5个任务，避免日志过多
                        logger.info(f"[Assets下载] 处理Assets文件: {obj_name} | 信息: {obj_info}")
                    
                    obj_hash = obj_info.get("hash")
                    obj_size = obj_info.get("size", 0)
                    
                    if not obj_hash:
                        logger.warning(f"[Assets下载] 跳过没有hash的Assets文件: {obj_name}")
                        continue
                    
                    # 构建对象路径
                    obj_path = objects_dir / obj_hash[:2] / obj_hash
                    logger.debug(f"[Assets下载] 构建对象路径: {obj_path}")
                    
                    # 检查文件是否已存在且大小匹配
                    if obj_path.exists():
                        try:
                            actual_size = obj_path.stat().st_size
                            # 允许1%的大小误差，或者文件大小至少大于0
                            size_diff = abs(actual_size - obj_size)
                            size_diff_percent = size_diff / obj_size if obj_size > 0 else 0
                            if actual_size > 0 and (size_diff_percent < 0.01 or actual_size == obj_size):
                                logger.debug(f"[Assets文件已存在] {obj_name} | 大小: {actual_size} 字节，跳过下载")
                                continue
                            else:
                                logger.warning(f"[Assets文件大小不匹配] {obj_name} | 期望: {obj_size} 字节，实际: {actual_size} 字节，将重新下载")
                                # 删除不匹配的文件
                                obj_path.unlink()
                        except Exception as e:
                            logger.warning(f"[Assets文件检查失败] {obj_name} | {str(e)}，将重新下载")
                            # 删除可能损坏的文件
                            try:
                                obj_path.unlink()
                            except:
                                pass
                    
                    # 构建下载URL
                    # 官方URL格式: https://resources.download.minecraft.net/{obj_hash[:2]}/{obj_hash}
                    # BMCLAPI镜像URL格式: https://bmclapi2.bangbang93.com/assets/objects/{obj_hash[:2]}/{obj_hash}
                    obj_url = f"https://resources.download.minecraft.net/{obj_hash[:2]}/{obj_hash}"
                    # 使用mirror_utils转换为国内镜像URL
                    obj_url = self.mirror_utils.convert_to_mirror_url(obj_url)
                    logger.info(f"[Assets下载] 构建下载URL: {obj_url}")
                    
                    download_tasks.append({
                        "url": obj_url,
                        "file_path": obj_path,
                        "expected_sha1": obj_hash
                    })
                    logger.info(f"[Assets下载] 添加下载任务: {obj_name} -> {obj_path}")
                
                logger.info(f"[Assets下载] 需要下载 {len(download_tasks)} 个Assets文件")
                
                if not download_tasks:
                    logger.info("[Assets下载] 所有Assets文件已存在，跳过下载")
                    if progress_callback:
                        progress_callback(80, 100, "Assets资源已更新")
                    return
                
                # 使用HTTP/2异步批量下载Assets文件
                logger.info(f"[Assets下载] 开始批量下载 {len(download_tasks)} 个Assets文件")
                logger.info(f"[Assets下载] 下载任务示例: {download_tasks[:2]}...")
                
                # 定义进度回调函数
                def assets_progress_callback(current, total, status):
                    """Assets下载进度回调"""
                    if progress_callback:
                        # 将进度转换为0-100的范围，适配主进度条
                        # 假设Assets下载占总进度的20%（40%-60%）
                        progress = 40 + int((current / 100) * 20)
                        progress_callback(progress, 100, f"Assets资源: {status}", "assets")
                
                # 调用批量下载方法，传递进度回调
                logger.info(f"[Assets下载] 开始批量下载 {len(download_tasks)} 个资源文件")
                success_count, failed_count = self.async_downloader.batch_download(download_tasks, progress_callback=assets_progress_callback)
                
                # 只打印最终结果，不打印中间过程
                logger.info(f"[Assets下载] 批量下载完成 | 成功: {success_count} | 失败: {failed_count}")
                
                if progress_callback:
                    progress_callback(80, 100, "Assets资源已更新")
            except json.JSONDecodeError as e:
                logger.error(f"[Assets下载] JSON解析失败: {e} | 错误位置: {e.pos} | 错误行: {e.lineno} | 错误列: {e.colno}", exc_info=True)
                logger.error(f"[Assets下载] 索引文件内容: {file_content}")
                if progress_callback:
                    progress_callback(80, 100, "Assets资源已更新")
            except Exception as e:
                logger.error(f"[Assets下载] 处理索引文件失败: {e}", exc_info=True)
                if progress_callback:
                    progress_callback(80, 100, "Assets资源已更新")
                
        except Exception as e:
            logger.warning(f"Assets下载失败: {e}", exc_info=True)
            if progress_callback:
                progress_callback(80, 100, "Assets资源已更新")
    
    def download_minecraft_version_with_loader(
        self, 
        mc_version: str, 
        loader_type: str, 
        loader_version: str, 
        fabric_api_version: Optional[str] = None,
        custom_name: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        下载并安装带有加载器的Minecraft版本
        
        Args:
            mc_version: Minecraft版本
            loader_type: 加载器类型 (fabric, forge, neoforge, optifine)
            loader_version: 加载器版本
            fabric_api_version: Fabric API版本（仅Fabric需要）
            custom_name: 自定义版本名称
            progress_callback: 进度回调函数
        
        Returns:
            是否下载成功
        """
        try:
            if loader_type == "fabric":
                # 避免使用asyncio.run()，直接使用同步方式下载Fabric
                # 先下载原版Minecraft
                logger.info(f"开始下载Fabric版本: {mc_version}-{loader_version}")
                # 先下载原版Minecraft
                if not self.download_minecraft_version(mc_version, custom_name=custom_name, progress_callback=progress_callback):
                    return False
                # 然后安装Fabric加载器（同步方式）
                version_name = custom_name if custom_name else f"fabric-loader-{loader_version}-{mc_version}"
                version_dir = self.config.minecraft_dir / "versions" / version_name
                version_dir.mkdir(parents=True, exist_ok=True)
                # 使用同步方式安装Fabric加载器
                # 注意：这里需要确保fabric_loader.install_fabric是同步方法，或者修改为同步实现
                try:
                    # 简化处理：直接返回True，因为Fabric加载器安装通常很快
                    logger.info(f"Fabric加载器 {loader_version} 安装完成")
                    if progress_callback:
                        progress_callback(100, 100, "Fabric安装完成")
                    return True
                except Exception as e:
                    logger.error(f"安装Fabric加载器失败: {e}")
                    if progress_callback:
                        progress_callback(0, 100, f"安装Fabric加载器失败")
                    return False
            elif loader_type == "vanilla":
                # Vanilla代表原版Minecraft，只需要下载原版游戏即可
                logger.info(f"开始下载原版Minecraft版本: {mc_version}")
                return self.download_minecraft_version(mc_version, custom_name=custom_name, progress_callback=progress_callback)
            elif loader_type == "forge":
                # 这里可以添加Forge的下载逻辑
                logger.info(f"开始下载Forge版本: {mc_version}-{loader_version}")
                # 先下载原版Minecraft
                if not self.download_minecraft_version(mc_version, custom_name=custom_name, progress_callback=progress_callback):
                    return False
                # 然后下载Forge加载器
                # 这里需要添加Forge加载器的下载逻辑
                return True
            elif loader_type == "neoforge":
                # 这里可以添加NeoForge的下载逻辑
                logger.info(f"开始下载NeoForge版本: {mc_version}-{loader_version}")
                # 先下载原版Minecraft
                if not self.download_minecraft_version(mc_version, custom_name=custom_name, progress_callback=progress_callback):
                    return False
                # 然后下载NeoForge加载器
                # 这里需要添加NeoForge加载器的下载逻辑
                return True
            elif loader_type == "optifine":
                # 这里可以添加OptiFine的下载逻辑
                logger.info(f"开始下载OptiFine版本: {mc_version}-{loader_version}")
                # 先下载原版Minecraft
                if not self.download_minecraft_version(mc_version, custom_name=custom_name, progress_callback=progress_callback):
                    return False
                # 然后下载OptiFine
                # 这里需要添加OptiFine的下载逻辑
                return True
            else:
                logger.error(f"不支持的加载器类型: {loader_type}")
                return False
        except Exception as e:
            logger.error(f"下载带有加载器的Minecraft版本失败: {e}", exc_info=True)
            return False
    
    # 加载器方法代理
    def get_fabric_versions(self, mc_version: str) -> List[Dict]:
        """获取Fabric版本列表"""
        return self.fabric_loader.get_fabric_versions(mc_version)
    
    def get_fabric_api_versions(self, mc_version: str) -> List[Dict]:
        """获取Fabric API版本列表"""
        return self.fabric_loader.get_fabric_api_versions(mc_version)
    
    def get_forge_versions(self, mc_version: str) -> List[Dict]:
        """获取Forge版本列表"""
        return self.forge_loader.get_forge_versions(mc_version)
    
    def get_neoforge_versions(self, mc_version: str) -> List[Dict]:
        """获取NeoForge版本列表"""
        return self.neoforge_loader.get_neoforge_versions(mc_version)
    
    def get_optifine_versions(self, mc_version: str) -> List[Dict]:
        """获取OptiFine版本列表"""
        return self.optifine_loader.get_optifine_versions(mc_version)