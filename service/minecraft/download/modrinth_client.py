"""
Modrinth客户端 - 用于从Modrinth下载模组和资源包
"""
import requests
import json
from typing import List, Dict, Optional
from utils.logger import Logger

logger = Logger().get_logger("ModrinthClient")


class ModrinthClient:
    """Modrinth客户端"""
    
    def __init__(self, config, download_thread_ref):
        """
        初始化Modrinth客户端
        
        Args:
            config: 下载配置对象
            download_thread_ref: 下载线程引用，用于取消下载
        """
        self.config = config
        self.download_thread_ref = download_thread_ref
        self.api_base = "https://api.modrinth.com/v2"
        self.cdn_base = "https://cdn.modrinth.com"
    
    def search_mods(self, query: str, game_version: Optional[str] = None, loader: Optional[str] = None, 
                   category: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """
        搜索Modrinth上的模组
        
        Args:
            query: 搜索关键词
            game_version: Minecraft版本
            loader: 加载器类型（fabric, forge, neoforge等）
            category: 模组分类
            limit: 结果数量限制
        
        Returns:
            模组搜索结果列表
        """
        try:
            params = {
                "query": query,
                "limit": limit,
                "index": "relevance"
            }
            
            # 添加可选参数
            if game_version:
                params["game_versions"] = [game_version]
            if loader:
                params["loaders"] = [loader]
            if category:
                params["categories"] = [category]
            
            url = f"{self.api_base}/search"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get("hits", [])
        except Exception as e:
            logger.error(f"搜索模组失败: {e}")
            return []
    
    def get_mod_versions(self, mod_id: str, game_version: Optional[str] = None, loader: Optional[str] = None) -> List[Dict]:
        """
        获取模组的所有版本
        
        Args:
            mod_id: 模组ID
            game_version: Minecraft版本
            loader: 加载器类型
        
        Returns:
            模组版本列表
        """
        try:
            params = {}
            if game_version:
                params["game_versions"] = [game_version]
            if loader:
                params["loaders"] = [loader]
            
            url = f"{self.api_base}/project/{mod_id}/version"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"获取模组版本失败: {e}")
            return []
    
    def get_mod_details(self, mod_id: str) -> Optional[Dict]:
        """
        获取模组的详细信息
        
        Args:
            mod_id: 模组ID
        
        Returns:
            模组详细信息
        """
        try:
            url = f"{self.api_base}/project/{mod_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"获取模组详情失败: {e}")
            return None
    
    def get_resourcepack_versions(self, pack_id: str, game_version: Optional[str] = None) -> List[Dict]:
        """
        获取资源包的所有版本
        
        Args:
            pack_id: 资源包ID
            game_version: Minecraft版本
        
        Returns:
            资源包版本列表
        """
        try:
            params = {}
            if game_version:
                params["game_versions"] = [game_version]
            
            url = f"{self.api_base}/project/{pack_id}/version"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"获取资源包版本失败: {e}")
            return []