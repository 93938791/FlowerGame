import sys
import os
from pathlib import Path
import requests

# 添加当前目录到搜索路径
sys.path.append(os.getcwd())

from config import Config
from service.syncthing.syncthing_manager import SyncthingManager
from service.syncthing.folder_manager import FolderManager
from utils.logger import Logger

def main():
    # 初始化配置
    if not Config.load_config():
        print("提示: 无法加载默认配置，尝试使用当前目录作为主目录...")
        Config.set_main_dir(Path(os.getcwd()))

    logger = Logger().get_logger("RepairTool")
    
    # 强制添加控制台输出 INFO
    import logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = False
    
    logger.info("=== Syncthing Folder Marker 修复工具 ===")
    
    manager = SyncthingManager()
    
    # 确保 Syncthing 运行
    if not manager.is_running():
        logger.info("Syncthing 未运行，正在启动...")
        manager.start()
    
    # 模拟触发状态检查以激活自动修复
    logger.info("正在扫描所有文件夹状态...")
    config = manager.get_config()
    
    if config and 'folders' in config:
        for folder in config['folders']:
            folder_id = folder['id']
            logger.info(f"检查文件夹: {folder_id} ({folder['label']})")
            
            # 调用 get_folder_status，触发内部的自动修复逻辑
            status = manager.folder_manager.get_folder_status(folder_id)
            
            if status:
                state = status.get('state')
                error = status.get('error')
                if state == 'error':
                    if not error: # 如果自动修复成功，error 会被清除，state 变为 scanning
                        logger.info(f"✅ 文件夹 {folder_id} 修复成功或正在扫描")
                    else:
                        logger.warning(f"⚠️ 文件夹 {folder_id} 仍处于错误状态: {error}")
                else:
                    logger.info(f"✅ 文件夹 {folder_id} 状态正常: {state}")
            else:
                logger.warning(f"无法获取文件夹 {folder_id} 的状态")
    else:
        logger.warning("未找到任何文件夹配置")

if __name__ == "__main__":
    main()
