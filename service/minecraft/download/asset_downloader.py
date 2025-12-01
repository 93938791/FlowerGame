"""
Minecraft 资源文件下载器
处理 assets（音效、语言、材质等）的下载
"""
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from utils.logger import logger
from .http_downloader import HttpDownloader, DownloadTask


class AssetDownloader:
    """资源文件下载器"""
    
    def __init__(self, minecraft_dir: Path, downloader: HttpDownloader):
        """
        初始化资源下载器
        
        Args:
            minecraft_dir: Minecraft 根目录
            downloader: HTTP 下载器
        """
        self.minecraft_dir = minecraft_dir
        self.downloader = downloader
        self.assets_dir = minecraft_dir / "assets"
        self.indexes_dir = self.assets_dir / "indexes"
        self.objects_dir = self.assets_dir / "objects"
        
        # 确保目录存在
        self.indexes_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(parents=True, exist_ok=True)
    
    def download_assets(
        self,
        asset_index_info: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> bool:
        """
        下载资源文件
        
        Args:
            asset_index_info: 资源索引信息（从版本 JSON 获取）
            progress_callback: 进度回调 (stage, current, total)
            
        Returns:
            是否下载成功
        """
        # 获取索引信息
        asset_id = asset_index_info.get("id")
        asset_url = asset_index_info.get("url")
        asset_sha1 = asset_index_info.get("sha1")
        
        if not all([asset_id, asset_url]):
            logger.error("资源索引信息不完整")
            return False
        
        logger.info(f"开始下载资源文件，索引: {asset_id}")
        
        # 1. 下载资源索引 JSON
        if progress_callback:
            progress_callback("index", 0, 1)
        
        index_file = self.indexes_dir / f"{asset_id}.json"
        if not self.downloader.download_file(asset_url, index_file, asset_sha1):
            logger.error("下载资源索引失败")
            return False
        
        if progress_callback:
            progress_callback("index", 1, 1)
        
        # 2. 解析索引文件
        import json
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)
        except Exception as e:
            logger.error(f"解析资源索引失败: {e}")
            return False
        
        # 3. 下载所有资源对象
        objects = index_data.get("objects", {})
        total_objects = len(objects)
        logger.info(f"需要下载 {total_objects} 个资源文件")
        
        if total_objects == 0:
            return True
        
        # 创建下载任务
        download_tasks = []
        for asset_name, asset_info in objects.items():
            hash_value = asset_info.get("hash")
            size = asset_info.get("size", 0)
            
            if not hash_value:
                continue
            
            # 资源 URL 格式: https://resources.download.minecraft.net/<前2位hash>/<完整hash>
            asset_url = f"https://resources.download.minecraft.net/{hash_value[:2]}/{hash_value}"
            
            # 保存路径: objects/<前2位hash>/<完整hash>
            save_path = self.objects_dir / hash_value[:2] / hash_value
            
            task = DownloadTask(
                url=asset_url,
                save_path=save_path,
                sha1=hash_value,
                description=f"Asset: {asset_name}"
            )
            download_tasks.append(task)
        
        # 批量下载
        def batch_progress(task: DownloadTask):
            completed = sum(1 for t in download_tasks if t.status == "completed")
            if progress_callback:
                progress_callback("objects", completed, total_objects)
            
            # 每 50 个文件输出一次日志
            if task.status == "completed" and completed % 50 == 0:
                logger.info(f"✅ 已下载 {completed}/{total_objects} 个资源文件")
            elif task.status == "failed":
                logger.warning(f"✗ {task.description}")
        
        result = self.downloader.download_batch(download_tasks, batch_progress)
        
        logger.info(
            f"资源下载完成: 成功 {result['completed']}/{result['total']}, "
            f"失败 {result['failed']}"
        )
        
        return result["failed"] == 0
