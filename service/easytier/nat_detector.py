"""
NAT类型检测模块
基于 RFC 5780 标准检测 NAT 类型
"""
import threading
import time
from utils.logger import Logger

# 尝试导入 pystun3 (注意：包名为 stun)
try:
    from stun import get_ip_info
    PYSTUN_AVAILABLE = True
except ImportError:
    # 尝试兼容性导入，以防版本差异
    try:
        from pystun3 import get_ip_info
        PYSTUN_AVAILABLE = True
    except ImportError:
        PYSTUN_AVAILABLE = False

logger = Logger().get_logger("NATDetector")

class NATDetector:
    """NAT类型检测器"""
    
    def __init__(self):
        self.nat_type = "未知"
        self.external_ip = None
        self.external_port = None
        self.is_running = False
        self._thread = None
        self.last_check_time = 0
        self.check_interval = 300  # 每5分钟检测一次
        
    def start_detection(self):
        """启动NAT检测（在后台线程中运行）"""
        if self.is_running:
            return
            
        if not PYSTUN_AVAILABLE:
            logger.warning("未安装 pystun3，无法进行 NAT 检测")
            self.nat_type = "检测组件缺失"
            return

        self.is_running = True
        self._thread = threading.Thread(target=self._detect_loop, daemon=True)
        self._thread.start()
        logger.info("NAT 检测服务已启动")
        
    def stop(self):
        """停止NAT检测"""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            # 线程会根据 is_running 标志自动退出，不需要强制终止
            pass
            
    def _detect_loop(self):
        """检测循环"""
        while self.is_running:
            try:
                self._perform_detection()
            except Exception as e:
                logger.error(f"NAT 检测过程出错: {e}")
            
            # 等待下一次检测，或者直到停止
            for _ in range(self.check_interval):
                if not self.is_running:
                    break
                time.sleep(1)
                
    def _perform_detection(self):
        """执行一次具体的检测"""
        logger.info("开始执行 RFC 5780 NAT 检测...")
        try:
            # source_ip="0.0.0.0", source_port=54320, stun_host=None, stun_port=3478
            # 使用默认的 STUN 服务器列表
            nat_type, external_ip, external_port = get_ip_info(
                source_ip="0.0.0.0",
                source_port=0 # 让系统随机选择端口
            )
            
            # 映射 NAT 类型名称为更标准的格式（可选中文）
            self.nat_type = self._normalize_nat_type(nat_type)
            self.external_ip = external_ip
            self.external_port = external_port
            self.last_check_time = time.time()
            
            logger.info(f"NAT 检测完成: 原始类型={nat_type}, 标准化={self.nat_type}, 公网IP={self.external_ip}")
            
        except Exception as e:
            logger.warning(f"NAT 检测失败: {e}")
            self.nat_type = "检测失败"

    def _normalize_nat_type(self, nat_type):
        """将 pystun3 的 NAT 类型名称标准化"""
        if not nat_type:
            return "未知"
            
        # 映射表
        # NAT1: Full Cone (全锥型) - 最宽松，最好
        # NAT2: Restricted Cone (限制锥型) - 也就是 Address Restricted
        # NAT3: Port Restricted Cone (端口限制锥型) - 最常见，大部分家用网络
        # NAT4: Symmetric (对称型) - 最严格，P2P困难
        mapping = {
            'Full Cone': 'NAT1 (Full Cone)',
            'Restric NAT': 'NAT2 (Restricted Cone)',
            'Restric Port NAT': 'NAT3 (Port Restricted)',
            'Symmetric NAT': 'NAT4 (Symmetric)',
            'Symmetric UDP Firewall': '防火墙限制',
            'Open Internet': '公开网络 (无NAT)',
            'Blocked': '网络受限'
        }
        
        return mapping.get(nat_type, nat_type)

    def get_status(self):
        """获取当前 NAT 状态"""
        return {
            "nat_type": self.nat_type,
            "external_ip": self.external_ip,
            "last_check": self.last_check_time
        }

# 单例实例
nat_detector = NATDetector()
