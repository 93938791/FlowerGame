"""
日志工具模块
支持日志轮转和自动清理，避免占用过多磁盘空间
"""
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timedelta
from config import Config


class SafeStreamHandler(logging.StreamHandler):
    """安全的流处理器，即使流为None也不会报错"""
    
    def emit(self, record):
        """重写emit方法，安全处理None流"""
        try:
            if self.stream is None or not hasattr(self.stream, 'write'):
                # 如果流不可用，直接返回，不报错
                return
            # 尝试写入
            super().emit(record)
        except (AttributeError, OSError, ValueError):
            # 捕获所有可能的异常，避免日志错误影响程序运行
            pass
        except Exception:
            # 其他异常也忽略，确保不会因为日志问题导致程序崩溃
            pass


class DuplicateFilter(logging.Filter):
    """重复日志过滤器，避免短时间内输出大量相同的日志"""
    
    def __init__(self, max_duplicates=3, time_window=5):
        """
        初始化重复日志过滤器
        :param max_duplicates: 最大重复次数
        :param time_window: 时间窗口（秒）
        """
        super().__init__()
        self.max_duplicates = max_duplicates
        self.time_window = time_window
        self.log_cache = {}
    
    def filter(self, record):
        """过滤重复日志"""
        # 使用日志消息作为唯一标识
        log_key = record.getMessage()
        current_time = datetime.now().timestamp()
        
        if log_key in self.log_cache:
            # 检查是否在时间窗口内
            last_time, count = self.log_cache[log_key]
            if current_time - last_time < self.time_window:
                # 增加计数
                self.log_cache[log_key] = (current_time, count + 1)
                
                # 如果超过最大重复次数，过滤掉
                if count >= self.max_duplicates:
                    return False
                
                # 第一次重复时，添加重复提示
                if count == self.max_duplicates:
                    record.msg = f"{record.msg} [重复日志，后续将被过滤]"
            else:
                # 超出时间窗口，重置计数
                self.log_cache[log_key] = (current_time, 1)
        else:
            # 新日志，添加到缓存
            self.log_cache[log_key] = (current_time, 1)
        
        return True

class Logger:
    """日志管理器"""
    
    _instance = None
    
    # 日志配置
    MAX_LOG_SIZE = 5 * 1024 * 1024  # 单个日志文件最大5MB
    BACKUP_COUNT = 3  # 保留3个备份文件
    MAX_LOG_DAYS = 7  # 保留最近7天的日志文件
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        from config import Config
        
        # 如果 Config 未配置，使用临时目录
        if not Config.is_configured():
            # 首次启动，使用临时目录
            import tempfile
            log_dir = Path(tempfile.gettempdir()) / "FlowerGame" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
        else:
            Config.init_dirs()
            log_dir = Config.LOG_DIR
        
        # 清理旧日志文件
        self._cleanup_old_logs(log_dir)
        
        # 创建日志文件
        log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        
        # 配置详细日志格式，便于调试
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
            datefmt='%H:%M:%S'  # 只显示时间，不显示日期（日期在文件名中）
        )
        
        # 创建重复日志过滤器
        duplicate_filter = DuplicateFilter(max_duplicates=2, time_window=3)
        
        # 使用RotatingFileHandler实现日志轮转
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.MAX_LOG_SIZE,
            backupCount=self.BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有DEBUG及以上级别
        file_handler.setFormatter(formatter)
        file_handler.addFilter(duplicate_filter)  # 添加重复日志过滤
        
        # 控制台处理器（使用安全的流处理器）
        # 只显示WARNING及以上级别，减少控制台刷屏
        import sys
        console_handler = None
        try:
            # 使用SafeStreamHandler，即使流为None也不会报错
            console_handler = SafeStreamHandler(sys.stdout)
            console_handler.setLevel(logging.WARNING)  # 控制台只显示WARNING及ERROR
            console_handler.setFormatter(formatter)
            console_handler.addFilter(duplicate_filter)  # 添加重复日志过滤
        except Exception:
            # 如果创建失败，不创建控制台处理器
            console_handler = None
        
        # 根日志器
        from config import Config
        self.logger = logging.getLogger(Config.APP_NAME)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        if console_handler is not None:
            self.logger.addHandler(console_handler)
        
        # 添加全局过滤器到根日志器
        self.logger.addFilter(duplicate_filter)
    
    def _cleanup_old_logs(self, log_dir):
        """清理旧的日志文件"""
        try:
            if not log_dir.exists():
                return
            
            # 计算过期时间
            expire_date = datetime.now() - timedelta(days=self.MAX_LOG_DAYS)
            
            deleted_count = 0
            total_size = 0
            
            # 遍历日志目录
            for log_file in log_dir.glob("app_*.log*"):
                try:
                    # 获取文件修改时间
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    file_size = log_file.stat().st_size
                    
                    # 如果文件过期，删除它
                    if file_mtime < expire_date:
                        log_file.unlink()
                        deleted_count += 1
                        total_size += file_size
                except Exception as e:
                    # 忽略无法删除的文件（可能正在被使用）
                    continue
            
            if deleted_count > 0:
                # 使用print而不是logger，因为logger可能还未初始化
                print(f"已清理 {deleted_count} 个旧日志文件，释放 {total_size / 1024 / 1024:.2f} MB 空间")
        except Exception as e:
            # 清理失败不影响程序运行
            pass
    
    def get_logger(self, name=None):
        """获取日志器"""
        from config import Config
        if name:
            return logging.getLogger(f"{Config.APP_NAME}.{name}")
        return self.logger

# 全局日志实例
logger = Logger().get_logger()
