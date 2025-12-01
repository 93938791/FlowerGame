"""
Minecraft 镜像源管理工具
支持自动切换镜像源，优先使用国内加速源
"""
from typing import List, Optional
from enum import Enum


class MirrorSource(Enum):
    """镜像源类型"""
    BMCLAPI = "bmclapi"  # BMCLAPI 镜像（国内）
    MCBBS = "mcbbs"      # MCBBS 镜像（国内）
    OFFICIAL = "official"  # 官方源


class MirrorConfig:
    """镜像配置"""
    
    # 版本清单 URL
    VERSION_MANIFEST_URLS = {
        MirrorSource.BMCLAPI: "https://bmclapi2.bangbang93.com/mc/game/version_manifest_v2.json",
        MirrorSource.MCBBS: "https://download.mcbbs.net/mc/game/version_manifest_v2.json",
        MirrorSource.OFFICIAL: "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    }
    
    # 资源域名映射
    DOMAIN_MAPPING = {
        MirrorSource.BMCLAPI: {
            "piston-meta.mojang.com": "bmclapi2.bangbang93.com",
            "piston-data.mojang.com": "bmclapi2.bangbang93.com",
            "launcher.mojang.com": "bmclapi2.bangbang93.com",
            "launchermeta.mojang.com": "bmclapi2.bangbang93.com",
            "libraries.minecraft.net": "bmclapi2.bangbang93.com/maven",
            "resources.download.minecraft.net": "bmclapi2.bangbang93.com/assets"
        },
        MirrorSource.MCBBS: {
            "piston-meta.mojang.com": "download.mcbbs.net",
            "piston-data.mojang.com": "download.mcbbs.net",
            "launcher.mojang.com": "download.mcbbs.net",
            "launchermeta.mojang.com": "download.mcbbs.net",
            "libraries.minecraft.net": "download.mcbbs.net/maven",
            "resources.download.minecraft.net": "download.mcbbs.net/assets"
        },
        MirrorSource.OFFICIAL: {}  # 官方源不做映射
    }
    
    # 路径前缀映射（BMCLAPI 需要特殊处理）
    PATH_PREFIX_MAPPING = {
        MirrorSource.BMCLAPI: {
            "piston-meta.mojang.com": "",
            "piston-data.mojang.com": "/openbmclapi",
            "launcher.mojang.com": "",
            "launchermeta.mojang.com": "",
            "libraries.minecraft.net": "",
            "resources.download.minecraft.net": ""
        },
        MirrorSource.MCBBS: {},
        MirrorSource.OFFICIAL: {}
    }


class MirrorManager:
    """镜像源管理器"""
    
    def __init__(self, preferred_sources: Optional[List[MirrorSource]] = None):
        """
        初始化镜像管理器
        
        Args:
            preferred_sources: 优先使用的镜像源列表，默认优先国内源
        """
        self.preferred_sources = preferred_sources or [
            MirrorSource.BMCLAPI,
            MirrorSource.MCBBS,
            MirrorSource.OFFICIAL
        ]
        self.current_source = self.preferred_sources[0]
        self.failed_sources = set()
    
    def get_version_manifest_url(self) -> str:
        """获取版本清单 URL"""
        return MirrorConfig.VERSION_MANIFEST_URLS[self.current_source]
    
    def convert_url(self, original_url: str, source: Optional[MirrorSource] = None) -> str:
        """
        转换 URL 到镜像源
        
        Args:
            original_url: 原始 URL
            source: 指定镜像源，None 则使用当前源
            
        Returns:
            转换后的 URL
        """
        if source is None:
            source = self.current_source
        
        # 官方源直接返回
        if source == MirrorSource.OFFICIAL:
            return original_url
        
        # 解析 URL
        if not original_url.startswith("http"):
            return original_url
        
        # 提取域名和路径
        url_parts = original_url.replace("https://", "").replace("http://", "").split("/", 1)
        if len(url_parts) < 2:
            return original_url
        
        original_domain = url_parts[0]
        path = url_parts[1]
        
        # 获取映射配置
        domain_mapping = MirrorConfig.DOMAIN_MAPPING.get(source, {})
        path_prefix_mapping = MirrorConfig.PATH_PREFIX_MAPPING.get(source, {})
        
        # 转换域名
        new_domain = domain_mapping.get(original_domain)
        if not new_domain:
            return original_url  # 不在映射表中，返回原 URL
        
        # 添加路径前缀
        path_prefix = path_prefix_mapping.get(source, {}).get(original_domain, "")
        
        # 构建新 URL
        new_url = f"https://{new_domain}{path_prefix}/{path}"
        return new_url
    
    def switch_to_next_source(self) -> bool:
        """
        切换到下一个可用的镜像源
        
        Returns:
            是否成功切换（如果所有源都失败则返回 False）
        """
        self.failed_sources.add(self.current_source)
        
        # 查找下一个可用源
        for source in self.preferred_sources:
            if source not in self.failed_sources:
                self.current_source = source
                return True
        
        # 所有源都失败，重置并使用官方源
        self.failed_sources.clear()
        self.current_source = MirrorSource.OFFICIAL
        return False
    
    def mark_source_failed(self, source: MirrorSource):
        """标记某个源失败"""
        self.failed_sources.add(source)
    
    def reset(self):
        """重置镜像管理器"""
        self.current_source = self.preferred_sources[0]
        self.failed_sources.clear()
    
    def get_all_mirror_urls(self, original_url: str) -> List[tuple]:
        """
        获取所有可能的镜像 URL
        
        Args:
            original_url: 原始 URL
            
        Returns:
            [(镜像源, 转换后的URL), ...] 列表
        """
        urls = []
        for source in self.preferred_sources:
            converted_url = self.convert_url(original_url, source)
            urls.append((source, converted_url))
        return urls
