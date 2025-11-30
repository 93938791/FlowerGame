"""
配置模块 - 定义应用程序的基本配置
"""
from pathlib import Path
import os
import sys

# 解析资源目录（兼容命令行运行与PyInstaller打包）
try:
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
except Exception:
    BASE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = BASE_DIR / "resources"

class Config:
    """配置类"""
    
    # 应用程序名称
    APP_NAME = "FlowerGame"
    
    # 应用程序版本
    APP_VERSION = "1.0.0"
    
    # 配置目录
    CONFIG_DIR = Path(os.path.expanduser("~")) / ".FlowerGame" / "config"
    
    # 缓存目录
    CACHE_DIR = Path(os.path.expanduser("~")) / ".FlowerGame" / "cache"
    
    # 日志目录
    LOG_DIR = Path(os.path.expanduser("~")) / ".FlowerGame" / "logs"
    
    # 运行环境
    HOSTNAME = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or __import__("platform").node()
    RESOURCE_DIR = BASE_DIR / "resources"
    
    # Syncthing配置
    SYNCTHING_HOME = Path(os.path.expanduser("~")) / ".FlowerGame" / "syncthing"
    SYNCTHING_BIN = RESOURCE_DIR / "syncthing" / "syncthing.exe"
    SYNCTHING_API_PORT = 8384
    SYNCTHING_API_KEY = "flowergame-syncthing-2025"
    SYNC_FOLDER_ID = "flowergame-sync"
    SYNC_FOLDER_LABEL = "FlowerGame 同步文件夹"
    
    # Easytier配置
    EASYTIER_BIN = RESOURCE_DIR / "easytier" / "easytier-core.exe"
    EASYTIER_CLI = RESOURCE_DIR / "easytier" / "easytier-cli.exe"
    EASYTIER_NETWORK_NAME = "flowergame-network"
    EASYTIER_NETWORK_SECRET = "flowergame-2025"
    EASYTIER_PUBLIC_PEERS = [
        "tcp://easytier1.public.kkrainbow.top:11010",
        "tcp://easytier2.public.kkrainbow.top:11010"
    ]
    
    # Web服务配置
    WEB_HOST = "127.0.0.1"
    WEB_PORT = 17890
    WEB_OPEN_BROWSER_ON_START = False
    @classmethod
    def init_dirs(cls):
        """初始化所有目录"""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.SYNCTHING_HOME.mkdir(parents=True, exist_ok=True)
