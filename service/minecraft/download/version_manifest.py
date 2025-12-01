"""
Minecraft 版本清单管理
支持缓存和版本查询
"""
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from utils.logger import logger
from .http_downloader import HttpDownloader
from .mirror_utils import MirrorManager


class VersionManifest:
    """版本清单管理器"""
    
    CACHE_EXPIRY_HOURS = 24  # 缓存有效期（小时）
    
    @classmethod
    def _get_cache_dir(cls):
        """获取缓存目录"""
        from config import Config
        if not Config.is_configured():
            # 如果未配置，使用临时目录
            import tempfile
            cache_dir = Path(tempfile.gettempdir()) / "FlowerGame" / "cache" / "minecraft"
        else:
            Config.init_dirs()
            cache_dir = Config.CACHE_DIR / "minecraft"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    
    @classmethod
    def _get_cache_file(cls):
        """获取缓存文件路径"""
        return cls._get_cache_dir() / ".version_manifest_cache.json"
    
    def __init__(
        self,
        downloader: Optional[HttpDownloader] = None,
        mirror_manager: Optional[MirrorManager] = None
    ):
        """
        初始化版本清单管理器
        
        Args:
            downloader: HTTP 下载器
            mirror_manager: 镜像管理器
        """
        self.downloader = downloader or HttpDownloader(mirror_manager=mirror_manager)
        self.mirror_manager = mirror_manager or MirrorManager()
        self.manifest_data: Optional[Dict[str, Any]] = None
    
    def load_manifest(self, force_refresh: bool = False) -> bool:
        """
        加载版本清单
        
        Args:
            force_refresh: 强制刷新（忽略缓存）
            
        Returns:
            是否加载成功
        """
        # 尝试从缓存加载
        if not force_refresh and self._load_from_cache():
            logger.info("从缓存加载版本清单成功")
            return True
        
        # 从网络下载
        logger.info("正在从网络获取版本清单...")
        manifest_url = self.mirror_manager.get_version_manifest_url()
        
        manifest_data = self.downloader.get_json(manifest_url, use_mirror=True)
        if not manifest_data:
            logger.error("获取版本清单失败")
            return False
        
        self.manifest_data = manifest_data
        
        # 保存到缓存
        self._save_to_cache()
        logger.info(f"版本清单加载成功，共 {len(self.manifest_data.get('versions', []))} 个版本")
        
        return True
    
    def get_version_info(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定版本的信息
        
        Args:
            version_id: 版本 ID（如 1.20.1）
            
        Returns:
            版本信息，未找到返回 None
        """
        if not self.manifest_data:
            if not self.load_manifest():
                return None
        
        versions = self.manifest_data.get("versions", [])
        for version in versions:
            if version.get("id") == version_id:
                return version
        
        logger.warning(f"未找到版本: {version_id}")
        return None
    
    def get_latest_release(self) -> Optional[str]:
        """获取最新正式版版本 ID"""
        if not self.manifest_data:
            if not self.load_manifest():
                return None
        
        return self.manifest_data.get("latest", {}).get("release")
    
    def get_latest_snapshot(self) -> Optional[str]:
        """获取最新快照版版本 ID"""
        if not self.manifest_data:
            if not self.load_manifest():
                return None
        
        return self.manifest_data.get("latest", {}).get("snapshot")
    
    def list_versions(
        self,
        version_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        列出所有版本
        
        Args:
            version_type: 版本类型过滤（release, snapshot, old_beta, old_alpha）
            limit: 限制返回数量
            
        Returns:
            版本列表
        """
        if not self.manifest_data:
            if not self.load_manifest():
                return []
        
        versions = self.manifest_data.get("versions", [])
        
        # 类型过滤
        if version_type:
            versions = [v for v in versions if v.get("type") == version_type]
        
        # 限制数量
        if limit:
            versions = versions[:limit]
        
        return versions
    
    def search_versions(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索版本
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的版本列表
        """
        if not self.manifest_data:
            if not self.load_manifest():
                return []
        
        versions = self.manifest_data.get("versions", [])
        return [v for v in versions if keyword.lower() in v.get("id", "").lower()]
    
    def _load_from_cache(self) -> bool:
        """从缓存加载"""
        cache_file = self._get_cache_file()
        if not cache_file.exists():
            return False
        
        try:
            cache_file = self._get_cache_file()
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            
            # 检查缓存是否过期
            cache_time = datetime.fromisoformat(cache_data.get("cache_time", ""))
            expiry_time = cache_time + timedelta(hours=self.CACHE_EXPIRY_HOURS)
            
            if datetime.now() > expiry_time:
                logger.debug("缓存已过期")
                return False
            
            self.manifest_data = cache_data.get("manifest")
            return True
        
        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
            return False
    
    def _save_to_cache(self):
        """保存到缓存"""
        try:
            cache_file = self._get_cache_file()
            cache_data = {
                "cache_time": datetime.now().isoformat(),
                "manifest": self.manifest_data
            }
            
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"版本清单已缓存到: {cache_file}")
        
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")
    
    def clear_cache(self):
        """清除缓存"""
        cache_file = self._get_cache_file()
        if cache_file.exists():
            cache_file.unlink()
            logger.info("版本清单缓存已清除")
