import json
import zipfile
import asyncio
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import httpx
from utils.logger import logger
from service.minecraft.download.download_manager import MinecraftDownloadManager, DownloadProgress
from service.minecraft.download.loader_support import LoaderType

class MrPackInstaller:
    def __init__(self, minecraft_dir: Path):
        self.minecraft_dir = minecraft_dir
        self.progress_callback = None

    def set_progress_callback(self, callback: Callable[[str, int, int, str], None]):
        """设置进度回调 (stage, current, total, message)"""
        self.progress_callback = callback

    def _update_progress(self, stage: str, current: int, total: int, message: str):
        if self.progress_callback:
            self.progress_callback(stage, current, total, message)

    async def install(self, mrpack_path: str, instance_name: str):
        """
        安装 .mrpack 整合包
        
        Args:
            mrpack_path: .mrpack 文件路径
            instance_name: 实例名称 (将作为 version id)
        """
        mrpack_file = Path(mrpack_path)
        if not mrpack_file.exists():
            raise FileNotFoundError(f"文件不存在: {mrpack_path}")

        logger.info(f"开始安装整合包: {mrpack_file.name} -> {instance_name}")
        self._update_progress("init", 0, 0, "正在解析整合包...")

        try:
            # 将 ZipFile 操作放入线程池，避免阻塞事件循环
            loop = asyncio.get_running_loop()
            
            def read_index():
                with zipfile.ZipFile(mrpack_file, 'r') as zf:
                    if "modrinth.index.json" not in zf.namelist():
                        raise ValueError("无效的 .mrpack 文件: 缺少 modrinth.index.json")
                    with zf.open("modrinth.index.json") as f:
                        return json.load(f)

            index_data = await loop.run_in_executor(None, read_index)
            
            # 2. 解析依赖 (MC版本和加载器)
            dependencies = index_data.get("dependencies", {})
            mc_version = dependencies.get("minecraft")
            
            loader_type = None
            loader_version = None
            
            if "fabric-loader" in dependencies:
                loader_type = LoaderType.FABRIC
                loader_version = dependencies["fabric-loader"]
            elif "forge" in dependencies:
                loader_type = LoaderType.FORGE
                loader_version = dependencies["forge"]
            elif "neoforge" in dependencies:
                loader_type = LoaderType.NEOFORGE
                loader_version = dependencies["neoforge"]
            elif "quilt-loader" in dependencies:
                loader_type = "quilt" 
                loader_version = dependencies["quilt-loader"]
            
            if not mc_version:
                raise ValueError("无法识别 Minecraft 版本")
            
            logger.info(f"整合包依赖: MC={mc_version}, Loader={loader_type} {loader_version}")

            # 3. 安装基础游戏和加载器
            self._update_progress("base_install", 0, 1, f"正在安装游戏核心 {mc_version}...")
            
            # 定义一个适配 download_manager 的回调
            def dm_progress(p: DownloadProgress):
                self._update_progress("base_install", p.current, p.total, p.message)

            # 使用 DownloadManager 安装 (DownloadManager 内部已经是同步阻塞的，放入线程池执行)
            def run_download_manager():
                manager = MinecraftDownloadManager(
                    max_connections=16,
                    progress_callback=dm_progress
                )
                return manager.download_with_loader(
                    mc_version=mc_version,
                    loader_type=loader_type if isinstance(loader_type, LoaderType) else str(loader_type),
                    loader_version=loader_version,
                    custom_name=instance_name
                )
            
            success = await loop.run_in_executor(None, run_download_manager)
            
            if not success:
                raise Exception("基础游戏安装失败")
            
            # 4. 下载文件 (Mods, ResourcePacks 等)
            files = index_data.get("files", [])
            total_files = len(files)
            
            # 目标目录: versions/{instance_name}/
            version_dir = self.minecraft_dir / "versions" / instance_name
            
            # 确保 loop 在协程中可用
            loop = asyncio.get_running_loop()

            # 移除内部的 import asyncio，使用顶层导入
            # import asyncio
            async with httpx.AsyncClient(timeout=60.0) as client:  # 增加默认超时时间
                # 限制并发数为 5
                semaphore = asyncio.Semaphore(5)
                
                async def download_file(file_info, index):
                    # 捕获闭包变量，避免 asyncio 引用问题
                    try:
                        async with semaphore:
                            file_path = file_info["path"]
                            # 检查 env 字段，如果是服务端专用则跳过
                            env = file_info.get("env", {})
                            if isinstance(env, dict) and env.get("client") == "unsupported":
                                # logger.info(f"跳过不支持客户端的文件: {file_path}")
                                return True
                                
                            # 确保路径安全
                            if ".." in file_path:
                                return True
                                
                            target_path = version_dir / file_path
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            download_url = file_info["downloads"][0]
                            file_name = Path(file_path).name
                            
                            # 注意：self._update_progress 可能会在线程池中调用，这里是在协程中
                            self._update_progress("download_files", index + 1, total_files, f"正在下载: {file_name}")
                            
                            # 检查文件是否已存在且大小匹配
                            if target_path.exists():
                                if target_path.stat().st_size == file_info.get("fileSize", -1):
                                    return True

                            # 增加重试机制，使用退避策略
                            max_retries = 5
                            for attempt in range(max_retries):
                                try:
                                    # 使用更长的超时时间，适应大文件或慢速网络
                                    resp = await client.get(download_url, follow_redirects=True, timeout=60.0)
                                    if resp.status_code == 200:
                                        # 使用 run_in_executor 进行文件写入，避免阻塞事件循环
                                        await loop.run_in_executor(None, lambda: target_path.write_bytes(resp.content))
                                        return True
                                    else:
                                        logger.warning(f"下载失败 {file_name}: {resp.status_code} (重试 {attempt+1}/{max_retries})")
                                        await asyncio.sleep(2 * (attempt + 1)) # 线性退避
                                except httpx.TimeoutException:
                                    logger.warning(f"下载超时 {file_name} (重试 {attempt+1}/{max_retries})")
                                    await asyncio.sleep(2 * (attempt + 1))
                                except Exception as e:
                                    logger.warning(f"下载异常 {file_name}: {e} (重试 {attempt+1}/{max_retries})")
                                    await asyncio.sleep(2 * (attempt + 1))
                            
                            logger.error(f"文件下载最终失败: {file_name}")
                            return False
                    except Exception as e:
                        logger.error(f"下载任务异常 {file_info.get('path', 'unknown')}: {e}")
                        return False
                
                # 创建所有下载任务
                tasks = [download_file(f, i) for i, f in enumerate(files)]
                results = await asyncio.gather(*tasks)
                
                # 检查是否有失败的下载
                failed_count = results.count(False)
                if failed_count > 0:
                    raise Exception(f"{failed_count} 个文件下载失败，请检查日志")
            
            # 5. 解压 overrides (放入线程池)
            self._update_progress("overrides", 0, 0, "正在应用覆盖文件...")
            
            def extract_overrides():
                with zipfile.ZipFile(mrpack_file, 'r') as zf:
                    file_list = zf.namelist()
                    override_files = [n for n in file_list if n.startswith("overrides/") and not n.endswith("/")]
                    client_override_files = [n for n in file_list if n.startswith("client-overrides/") and not n.endswith("/")]
                    
                    # 如果有 client-overrides，优先使用
                    target_files = client_override_files if client_override_files else override_files
                    prefix = "client-overrides/" if client_override_files else "overrides/"
                    
                    total_overrides = len(target_files)
                    for i, name in enumerate(target_files):
                        rel_path = name[len(prefix):]
                        target_path = version_dir / rel_path
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        self._update_progress("overrides", i + 1, total_overrides, f"正在解压: {rel_path}")
                        
                        with zf.open(name) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())

            await loop.run_in_executor(None, extract_overrides)

            self._update_progress("done", 100, 100, "安装完成")
            logger.info(f"整合包 {instance_name} 安装完成")
            return True

        except Exception as e:
            logger.error(f"安装整合包失败: {e}", exc_info=True)
            raise e
