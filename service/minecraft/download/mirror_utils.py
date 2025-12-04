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
            "resources.download.minecraft.net": "bmclapi2.bangbang93.com/assets",
            "meta.fabricmc.net": "bmclapi2.bangbang93.com/fabric-meta",
            "maven.fabricmc.net": "bmclapi2.bangbang93.com/maven"
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
    """镜像管理器"""
    
    def __init__(self):
        self.current_source = MirrorSource.BMCLAPI  # 默认使用 BMCLAPI
        self.fallback_sources = [MirrorSource.MCBBS, MirrorSource.OFFICIAL] # 备用源列表
    
    def set_source(self, source: MirrorSource):
        """设置镜像源"""
        self.current_source = source
    
    def get_version_manifest_url(self) -> str:
        """获取版本清单 URL"""
        return MirrorConfig.VERSION_MANIFEST_URLS[self.current_source]
    
    def get_download_url(self, url: str) -> str:
        """
        获取下载 URL（根据当前镜像源自动替换）
        
        Args:
            url: 原始 URL
            
        Returns:
            替换后的镜像 URL
        """
        if not url:
            return url
            
        # 官方源不需要替换
        if self.current_source == MirrorSource.OFFICIAL:
            return url
            
        # 检查域名映射
        mapping = MirrorConfig.DOMAIN_MAPPING[self.current_source]
        prefix_mapping = MirrorConfig.PATH_PREFIX_MAPPING[self.current_source]
        
        for original_domain, mirror_domain in mapping.items():
            if original_domain in url:
                # 获取前缀
                prefix = prefix_mapping.get(original_domain, "")
                
                # 替换域名
                new_url = url.replace(original_domain, mirror_domain + prefix)
                return new_url
        
        return url

    def switch_to_fallback(self):
        """切换到备用源"""
        if self.fallback_sources:
            next_source = self.fallback_sources.pop(0)
            self.current_source = next_source
            return True
        return False
