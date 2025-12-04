"""
Minecraft 版本 JSON 解析
解析版本配置文件，提取下载信息
"""
import platform
from typing import Dict, Any, Optional, List
from pathlib import Path
from utils.logger import logger
from .http_downloader import HttpDownloader


class RuleEvaluator:
    """规则评估器"""
    
    @staticmethod
    def get_os_name() -> str:
        """获取操作系统名称（Minecraft 格式）"""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "darwin":
            return "osx"
        elif system == "linux":
            return "linux"
        return system
    
    @staticmethod
    def get_os_arch() -> str:
        """获取系统架构"""
        machine = platform.machine().lower()
        if machine in ("amd64", "x86_64"):
            return "x64"
        elif machine in ("i386", "i686", "x86"):
            return "x86"
        elif machine.startswith("arm"):
            return "arm64" if "64" in machine else "arm"
        return machine
    
    @staticmethod
    def evaluate_rules(rules: List[Dict[str, Any]]) -> bool:
        """
        评估规则列表
        
        Args:
            rules: 规则列表
            
        Returns:
            是否允许（符合规则）
        """
        if not rules:
            return True  # 没有规则，默认允许
        
        os_name = RuleEvaluator.get_os_name()
        os_arch = RuleEvaluator.get_os_arch()
        
        allowed = False  # 默认不允许
        
        for rule in rules:
            action = rule.get("action", "allow")
            
            # 检查操作系统规则
            os_rule = rule.get("os")
            if os_rule:
                # 检查系统名称
                if "name" in os_rule and os_rule["name"] != os_name:
                    continue
                
                # 检查架构
                if "arch" in os_rule and os_rule["arch"] != os_arch:
                    continue
                
                # 检查版本（可选）
                if "version" in os_rule:
                    # 这里可以添加版本正则匹配逻辑
                    pass
            
            # 匹配规则，应用动作
            if action == "allow":
                allowed = True
            elif action == "disallow":
                allowed = False
        
        return allowed


class VersionInfo:
    """版本信息解析器"""
    
    def __init__(
        self,
        version_id: str,
        version_json: Dict[str, Any],
        minecraft_dir: Path,
        custom_dir_name: Optional[str] = None
    ):
        """
        初始化版本信息
        
        Args:
            version_id: 版本 ID（用于文件名）
            version_json: 版本 JSON 数据
            minecraft_dir: Minecraft 根目录
            custom_dir_name: 自定义目录名（如果不提供，则使用 version_id）
        """
        self.version_id = version_id  # 原始版本号，用于文件名
        self.dir_name = custom_dir_name if custom_dir_name else version_id  # 目录名
        self.data = version_json
        self.minecraft_dir = minecraft_dir
    
    @classmethod
    def from_url(
        cls,
        version_id: str,
        version_url: str,
        minecraft_dir: Path,
        downloader: HttpDownloader,
        custom_dir_name: Optional[str] = None
    ) -> Optional["VersionInfo"]:
        """
        从 URL 加载版本信息
        
        Args:
            version_id: 版本 ID（用于文件名）
            version_url: 版本 JSON URL
            minecraft_dir: Minecraft 根目录
            downloader: 下载器
            custom_dir_name: 自定义目录名
            
        Returns:
            版本信息对象，失败返回 None
        """
        logger.info(f"正在获取版本信息: {version_id}")
        version_json = downloader.get_json(version_url, use_mirror=True)
        
        if not version_json:
            logger.error(f"获取版本信息失败: {version_id}")
            return None
        
        return cls(version_id, version_json, minecraft_dir, custom_dir_name)
    
    def get_client_download_info(self) -> Optional[Dict[str, Any]]:
        """获取客户端 JAR 下载信息"""
        downloads = self.data.get("downloads", {})
        client_info = downloads.get("client")
        
        if not client_info:
            logger.warning("版本 JSON 中未找到客户端下载信息")
            return None
        
        return client_info
    
    def get_asset_index_info(self) -> Optional[Dict[str, Any]]:
        """获取资源索引信息"""
        asset_index = self.data.get("assetIndex")
        
        if not asset_index:
            logger.warning("版本 JSON 中未找到资源索引信息")
            return None
        
        return asset_index
    
    def get_libraries(self, filter_by_rules: bool = True) -> List[Dict[str, Any]]:
        """
        获取依赖库列表
        
        Args:
            filter_by_rules: 是否根据规则过滤
            
        Returns:
            依赖库列表
        """
        libraries = self.data.get("libraries", [])
        
        if not filter_by_rules:
            return libraries
        
        # 根据规则过滤
        filtered_libraries = []
        for lib in libraries:
            rules = lib.get("rules", [])
            if RuleEvaluator.evaluate_rules(rules):
                filtered_libraries.append(lib)
        
        return filtered_libraries
    
    def get_main_class(self) -> Optional[str]:
        """获取主类名"""
        return self.data.get("mainClass")
    
    def get_arguments(self) -> Dict[str, List]:
        """获取启动参数"""
        # 新版本格式
        if "arguments" in self.data:
            return self.data["arguments"]
        
        # 旧版本格式
        minecraft_arguments = self.data.get("minecraftArguments", "")
        return {
            "game": minecraft_arguments.split(),
            "jvm": []
        }
    
    def get_java_version(self) -> Dict[str, Any]:
        """获取 Java 版本要求"""
        java_version = self.data.get("javaVersion", {})
        return {
            "component": java_version.get("component", "jre-legacy"),
            "majorVersion": java_version.get("majorVersion", 8)
        }
    
    def get_version_dir(self) -> Path:
        """获取版本目录（使用自定义目录名）"""
        return self.minecraft_dir / "versions" / self.dir_name
    
    def get_client_jar_path(self) -> Path:
        """获取客户端 JAR 路径"""
        return self.get_version_dir() / f"{self.version_id}.jar"
    
    def get_version_json_path(self) -> Path:
        """获取版本 JSON 路径"""
        return self.get_version_dir() / f"{self.version_id}.json"
    
    def get_natives_dir(self) -> Path:
        """获取 natives 目录"""
        return self.get_version_dir() / "natives"
    
    def save_version_json(self) -> bool:
        """保存版本 JSON 到本地"""
        try:
            import json
            
            version_json_path = self.get_version_json_path()
            version_json_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(version_json_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"版本 JSON 已保存: {version_json_path}")
            return True
        
        except Exception as e:
            logger.error(f"保存版本 JSON 失败: {e}")
            return False
