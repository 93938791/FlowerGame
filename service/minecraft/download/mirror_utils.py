"""
镜像工具类 - 用于处理镜像URL转换和镜像健康检查
"""
import threading
import time
import requests
from utils.logger import Logger

logger = Logger().get_logger("MirrorUtils")


class MirrorUtils:
    """镜像工具类"""
    
    def __init__(self, config):
        """
        初始化镜像工具
        
        Args:
            config: 下载配置对象
        """
        self.config = config
        self.mirror_health = {}
        self.mirror_latency = {}
        self.modrinth_source_order = ["modrinth", "bmclapi", "github"]
    
    def init_mirror_health_async(self):
        """异步初始化镜像健康状态"""
        def _init_health():
            time.sleep(0.5)  # 延迟执行，避免阻塞主线程
            self._check_mirror_health()
        
        thread = threading.Thread(target=_init_health, daemon=True)
        thread.start()
    
    def _check_mirror_health(self):
        """检查镜像健康状态"""
        try:
            # 检查BMCLAPI镜像
            bmclapi_url = f"https://{self.config.BMCLAPI_DOMAIN}/"
            start_time = time.time()
            response = requests.get(bmclapi_url, timeout=5)
            latency = (time.time() - start_time) * 1000  # 转换为毫秒
            self.mirror_health["bmclapi"] = response.status_code == 200
            self.mirror_latency["bmclapi"] = latency
            logger.debug(f"[镜像健康] BMCLAPI: {'可用' if self.mirror_health['bmclapi'] else '不可用'} | 延迟: {latency:.2f}ms")
        except Exception as e:
            logger.debug(f"[镜像健康] BMCLAPI检查失败: {e}")
            self.mirror_health["bmclapi"] = False
            self.mirror_latency["bmclapi"] = float("inf")
    
    def convert_to_mirror_url(self, url: str) -> str:
        """
        将官方URL转换为镜像URL
        
        Args:
            url: 官方URL
        
        Returns:
            转换后的镜像URL
        """
        if not self.config.use_mirror:
            return url
        
        # 处理Minecraft官方URL
        if "piston-meta.mojang.com" in url:
            # 版本清单和版本JSON
            return url.replace("piston-meta.mojang.com", self.config.BMCLAPI_DOMAIN)
        elif "launchermeta.mojang.com" in url:
            # 启动器元数据
            return url.replace("launchermeta.mojang.com", self.config.BMCLAPI_DOMAIN)
        elif "launcher.mojang.com" in url:
            # 启动器文件
            return url.replace("launcher.mojang.com", self.config.BMCLAPI_DOMAIN)
        elif "libraries.minecraft.net" in url:
            # 库文件
            return url.replace("libraries.minecraft.net", f"{self.config.BMCLAPI_DOMAIN}/libraries")
        elif "resources.download.minecraft.net" in url:
            # 资源文件
            return url.replace("resources.download.minecraft.net", f"{self.config.BMCLAPI_DOMAIN}/assets")
        elif "files.minecraftforge.net" in url or "maven.minecraftforge.net" in url:
            # Forge文件
            return url.replace("files.minecraftforge.net", f"{self.config.BMCLAPI_DOMAIN}/forge")
            return url.replace("maven.minecraftforge.net", f"{self.config.BMCLAPI_DOMAIN}/maven/net/minecraftforge")
        elif "maven.fabricmc.net" in url:
            # Fabric文件
            return url.replace("maven.fabricmc.net", f"{self.config.BMCLAPI_DOMAIN}/maven/net/fabricmc")
        elif "maven.neoforged.net" in url:
            # NeoForge文件
            return url.replace("maven.neoforged.net", f"{self.config.BMCLAPI_DOMAIN}/maven/net/neoforged")
        elif "repo1.maven.org" in url:
            # Maven中央仓库
            return url.replace("repo1.maven.org/maven2", f"{self.config.BMCLAPI_DOMAIN}/maven")
        
        # 其他URL不转换
        return url
    
    def get_fastest_source_order(self, source_type: str, default_order: list) -> list:
        """
        获取最快的源顺序
        
        Args:
            source_type: 源类型
            default_order: 默认顺序
        
        Returns:
            排序后的源顺序
        """
        # 简单实现，返回默认顺序
        return default_order