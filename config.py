"""
配置模块 - 定义应用程序的基本配置
支持打包后的exe在任意位置运行，首次启动时选择目录
"""
from pathlib import Path
import os
import sys
import json
import hashlib

# 解析资源目录（兼容命令行运行与PyInstaller/Nuitka打包）
try:
    # PyInstaller
    if hasattr(sys, "_MEIPASS"):
        BASE_DIR = Path(sys._MEIPASS)
    # Nuitka (sys.frozen is True)
    elif getattr(sys, "frozen", False):
        # Nuitka standalone/onefile: __file__ points to the module inside the dist/temp folder
        # We use the parent of the current file (config.py) as the base directory
        BASE_DIR = Path(__file__).resolve().parent
    else:
        # Normal Python execution
        BASE_DIR = Path(__file__).resolve().parent
except Exception:
    BASE_DIR = Path(__file__).resolve().parent

RESOURCE_DIR = BASE_DIR / "resources"

# 调试输出资源目录位置（方便排查打包问题）
# 注意：这里使用 print 而不是 logger，因为 logger 可能还没初始化
print(f"Environment: frozen={getattr(sys, 'frozen', False)}, meipass={hasattr(sys, '_MEIPASS')}")
print(f"Base Dir: {BASE_DIR}")
print(f"Resource Dir: {RESOURCE_DIR}")
if not RESOURCE_DIR.exists():
    print("WARNING: Resource directory does not exist!")
else:
    print("Resource directory found.")

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
    # Syncthing API Key 派生策略
    # mode 可选：'device'（设备唯一）或 'network'（网络统一）
    SYNCTHING_API_KEY_MODE = os.environ.get("FG_ST_APIKEY_MODE", "device")
    # 用于派生的盐（建议设置为网络级别常量或环境变量）
    SYNCTHING_API_KEY_SALT = os.environ.get("FG_ST_APIKEY_SALT", "flowergame-2025")
    
    @classmethod
    def _derive_api_key(cls):
        """派生 Syncthing API Key（默认使用 SHA-256，返回十六进制字符串）"""
        # 优先使用环境变量覆盖（便于打包与运维）
        env_key = os.environ.get("STGUIAPIKEY")
        if env_key:
            return env_key
        
        # 设备唯一：使用主机名 + 盐
        if (cls.SYNCTHING_API_KEY_MODE or "").lower() == "device":
            base = f"device|{cls.HOSTNAME}|{cls.SYNCTHING_API_KEY_SALT}"
            return hashlib.sha256(base.encode("utf-8")).hexdigest()
        
        # 网络统一：使用 EasyTier 房间名 + 密码 + 盐
        if (cls.SYNCTHING_API_KEY_MODE or "").lower() == "network":
            base = f"network|{cls.EASYTIER_NETWORK_NAME}|{cls.EASYTIER_NETWORK_SECRET}|{cls.SYNCTHING_API_KEY_SALT}"
            return hashlib.sha256(base.encode("utf-8")).hexdigest()
        
        # 回退：静态默认值（不推荐）
        return "flowergame-syncthing-2025"
    
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
        
# 在类定义完成后，派生并设置 Syncthing API Key
Config.SYNCTHING_API_KEY = Config._derive_api_key()
