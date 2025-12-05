"""
Minecraft 镜像源管理工具
支持自动切换镜像源，优先使用国内加速源
"""
from typing import List, Optional
from enum import Enum


class MirrorSource(Enum):
    """镜像源类型"""
    BMCLAPI = "bmclapi"  # BMCLAPI 镜像（国内）
    OFFICIAL = "official"  # 官方源


class MirrorConfig:
    """镜像配置"""
    
    # 版本清单 URL
    VERSION_MANIFEST_URLS = {
        MirrorSource.BMCLAPI: "https://bmclapi2.bangbang93.com/mc/game/version_manifest_v2.json",
        MirrorSource.OFFICIAL: "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    }
    
    # 资源域名映射
    DOMAIN_MAPPING = {
        MirrorSource.BMCLAPI: {
            "piston-meta.mojang.com": "bmclapi2.bangbang93.com",
            "launchermeta.mojang.com": "bmclapi2.bangbang93.com",
            "launcher.mojang.com": "bmclapi2.bangbang93.com",
            "libraries.minecraft.net": "bmclapi2.bangbang93.com/maven",
            "resources.download.minecraft.net": "bmclapi2.bangbang93.com/assets",
            "meta.fabricmc.net": "bmclapi2.bangbang93.com/fabric-meta",
            "maven.fabricmc.net": "bmclapi2.bangbang93.com/maven",
            "maven.minecraftforge.net": "bmclapi2.bangbang93.com/maven",
            "files.minecraftforge.net/maven": "bmclapi2.bangbang93.com/maven",
            "authlib-injector.yushi.moe": "bmclapi2.bangbang93.com/mirrors/authlib-injector",
            "maven.neoforged.net": "bmclapi2.bangbang93.com/maven"
        },
        MirrorSource.OFFICIAL: {}  # 官方源不做映射
    }
    
    # 路径前缀映射（BMCLAPI 需要特殊处理）
    PATH_PREFIX_MAPPING = {
        MirrorSource.BMCLAPI: {
            "piston-meta.mojang.com": "",
            "launchermeta.mojang.com": "",
            "launcher.mojang.com": "",
            "libraries.minecraft.net": "",
            "resources.download.minecraft.net": "",
            "meta.fabricmc.net": "",
            "maven.fabricmc.net": "",
            "maven.minecraftforge.net": "",
            "files.minecraftforge.net/maven": "",
            "authlib-injector.yushi.moe": "",
            "maven.neoforged.net": ""
        },
        MirrorSource.OFFICIAL: {}
    }


class MirrorManager:
    """镜像管理器"""
    
    def __init__(self):
        self.current_source = MirrorSource.BMCLAPI  # 默认使用 BMCLAPI
        self.fallback_sources = []
    
    def set_source(self, source: MirrorSource):
        """设置镜像源"""
        self.current_source = source
    
    def get_version_manifest_url(self) -> str:
        """获取版本清单 URL"""
        return MirrorConfig.VERSION_MANIFEST_URLS[self.current_source]
    
    def get_download_url(self, url: str) -> str:
        """
        获取下载 URL（根据当前镜像源自动替换）
        优先使用国内镜像；当当前源为 OFFICIAL 时原样返回，以便真正回退到官方源。
        """
        if not url:
            return url

        # 当前源明确为官方时，不做任何替换，确保回退生效
        if self.current_source == MirrorSource.OFFICIAL:
            return url

        # Liteloader 特例：直接替换为 BMCL 路径（更换域名与固定路径）
        if "dl.liteloader.com/versions/versions.json" in url:
            return url.replace("http://dl.liteloader.com/versions/versions.json",
                               "https://bmclapi.bangbang93.com/maven/com/mumfrey/liteloader/versions.json")

        # 检查域名映射
        mapping = MirrorConfig.DOMAIN_MAPPING.get(self.current_source, {})
        prefix_mapping = MirrorConfig.PATH_PREFIX_MAPPING.get(self.current_source, {})

        for original_domain, mirror_domain in mapping.items():
            if original_domain in url:
                prefix = prefix_mapping.get(original_domain, "")
                new_url = url.replace(original_domain, mirror_domain + prefix)

                # Neoforge 特例：移除 releases 路径段
                if self.current_source == MirrorSource.BMCLAPI:
                    if original_domain == "maven.neoforged.net" and "/releases/" in new_url:
                        new_url = new_url.replace("/maven/releases/", "/maven/")

                return new_url

        return url

    def switch_to_fallback(self):
        """切换到备用源"""
        if self.fallback_sources:
            next_source = self.fallback_sources.pop(0)
            self.current_source = next_source
            return True
        return False
