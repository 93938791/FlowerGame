import sys
import os
import time
import signal

# 添加当前目录到搜索路径
sys.path.append(os.getcwd())

from config import Config
from service.syncthing.syncthing_manager import SyncthingManager
from utils.logger import Logger

def main():
    # 初始化配置
    if not Config.load_config():
        print("提示: 无法加载默认配置，尝试使用当前目录作为主目录...")
        # 临时设置当前目录为主目录用于测试
        Config.set_main_dir(Path(os.getcwd()))

    # 设置 Logger
    logger = Logger().get_logger("Listener")
    
    # 强制添加控制台输出 INFO (因为默认 Logger 只在控制台输出 WARNING)
    import logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = False # 防止传递给父 Logger 导致重复（虽然父 Logger 过滤 INFO，但以防万一）

    logger.info("=== Syncthing 自动添加设备监听器 ===")
    logger.info(f"API Key: {Config.SYNCTHING_API_KEY}")
    
    manager = SyncthingManager()
    
    # 检查是否运行
    if not manager.is_running():
        logger.info("Syncthing 未运行，正在启动...")
        try:
            manager.start()
        except Exception as e:
            logger.error(f"启动失败: {e}")
            return
    else:
        logger.info("Syncthing 已在运行，连接中...")
    
    # 启动事件监听（无论是否新启动，都需要确保监听器运行）
    # 注意：如果 manager.start() 被调用，它内部已经启动了监听器
    # 这里为了保险，检查一下或重复调用（EventManager 有状态检查，重复调用安全）
    
    logger.info("注册事件处理回调...")
    manager.event_manager.register_callback(manager._on_syncthing_event)
    
    logger.info("启动事件监听线程...")
    manager.event_manager.start_listener()
    
    logger.info("正在监听网络中新加入的 Syncthing 设备...")
    logger.info("策略: 发现 DeviceRejected 事件 -> 自动添加设备 (地址: dynamic, 自动分享: True)")
    logger.info("按 Ctrl+C 退出")
    
    def signal_handler(sig, frame):
        logger.info("正在退出...")
        manager.event_manager.stop_listener()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        manager.event_manager.stop_listener()

if __name__ == "__main__":
    main()
