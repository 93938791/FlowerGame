"""
配置模块 - 定义应用程序的基本配置
支持打包后的exe在任意位置运行，首次启动时选择目录
"""
from pathlib import Path
import os
import sys
import json

# 解析资源目录（兼容命令行运行与PyInstaller打包）
try:
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
except Exception:
    BASE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = BASE_DIR / "resources"

# 配置文件路径（存储在用户主目录，打包后也能访问）
CONFIG_FILE = Path(os.path.expanduser("~")) / ".flowergame_config.json"


class Config:
    """配置类"""
    
    # 应用程序名称
    APP_NAME = "FlowerGame"
    
    # 应用程序版本
    APP_VERSION = "1.0.0"
    
    # ==================== 目录配置 ====================
    # 主目录：从配置文件读取，或需要用户选择
    _main_dir = None
    _initialized = False
    
    @classmethod
    def load_config(cls):
        """从配置文件加载目录配置"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    main_dir = config.get('main_dir')
                    if main_dir and Path(main_dir).exists():
                        cls._main_dir = Path(main_dir)
                        cls._initialized = True
                        return True
        except Exception as e:
            print(f"加载配置文件失败: {e}")
        return False
    
    @classmethod
    def save_config(cls, main_dir: Path):
        """保存目录配置到文件"""
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'main_dir': str(main_dir)}, f, ensure_ascii=False, indent=2)
            cls._main_dir = main_dir
            cls._initialized = True
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    @classmethod
    def get_main_dir(cls):
        """获取主目录，如果未配置则返回None"""
        if not cls._initialized:
            cls.load_config()
        return cls._main_dir
    
    @classmethod  
    def set_main_dir(cls, main_dir: Path):
        """设置主目录并保存配置"""
        return cls.save_config(main_dir)
    
    @classmethod
    @property
    def MAIN_DIR(cls):
        """主目录：FlowerGame文件夹"""
        return cls.get_main_dir()
    
    @classmethod
    @property
    def MINECRAFT_DIR(cls):
        """Minecraft 目录：FlowerGame/.minecraft"""
        main = cls.get_main_dir()
        return main / ".minecraft" if main else None
    
    @classmethod
    @property
    def CONFIG_DIR(cls):
        """配置目录：FlowerGame/config"""
        main = cls.get_main_dir()
        return main / "config" if main else None
    
    @classmethod
    @property  
    def CACHE_DIR(cls):
        """缓存目录：FlowerGame/cache"""
        main = cls.get_main_dir()
        return main / "cache" if main else None
    
    @classmethod
    @property
    def LOG_DIR(cls):
        """日志目录：FlowerGame/logs"""
        main = cls.get_main_dir()
        return main / "logs" if main else None
    
    @classmethod
    @property
    def SYNCTHING_HOME(cls):
        """Syncthing 目录：FlowerGame/syncthing"""
        main = cls.get_main_dir()
        return main / "syncthing" if main else None
    
    # 运行环境
    HOSTNAME = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or __import__("platform").node()
    
    # Syncthing配置
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
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 17890
    WEB_OPEN_BROWSER_ON_START = True  # 启动时自动打开浏览器
    WEB_CONSOLE_URL = "http://localhost:3063/web/"  # 公共Web控制台地址

    
    @classmethod
    def init_dirs(cls):
        """初始化所有目录"""
        main = cls.get_main_dir()
        if main is None:
            return False
        
        main.mkdir(parents=True, exist_ok=True)
        (main / ".minecraft").mkdir(parents=True, exist_ok=True)
        (main / "config").mkdir(parents=True, exist_ok=True)
        (main / "cache").mkdir(parents=True, exist_ok=True)
        (main / "logs").mkdir(parents=True, exist_ok=True)
        (main / "syncthing").mkdir(parents=True, exist_ok=True)
        return True
    
    @classmethod
    def is_configured(cls):
        """检查是否已配置目录"""
        return cls.get_main_dir() is not None
