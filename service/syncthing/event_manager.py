"""Syncthing事件管理模块
负责事件监听和回调处理
"""
import time
import threading
import requests
from utils.logger import Logger

logger = Logger().get_logger("SyncthingEventManager")


class EventManager:
    """事件管理器"""
    
    def __init__(self, api_url, headers):
        self.api_url = api_url
        self.headers = headers
        self.event_thread = None
        self.event_running = False
        self.event_callbacks = []  # 事件回调列表
    
    def register_callback(self, callback):
        """注册事件回调函数"""
        if callback not in self.event_callbacks:
            self.event_callbacks.append(callback)
            logger.info(f"注册事件回调: {callback.__name__}")
    
    def start_listener(self):
        """启动事件监听线程"""
        if self.event_running:
            logger.warning("事件监听已在运行")
            return
        
        self.event_running = True
        self.event_thread = threading.Thread(target=self._event_listener_loop, daemon=True)
        self.event_thread.start()
        logger.info("事件监听已启动")
    
    def stop_listener(self):
        """停止事件监听线程"""
        if not self.event_running:
            return
        
        self.event_running = False
        if self.event_thread:
            self.event_thread.join(timeout=2)
            self.event_thread = None
        logger.info("事件监听已停止")
    
    def _event_listener_loop(self):
        """事件监听循环"""
        last_event_id = 0
        
        while self.event_running:
            try:
                # 调用Syncthing的事件API (long polling)
                resp = requests.get(
                    f"{self.api_url}/rest/events",
                    params={"since": last_event_id},
                    headers=self.headers,
                    timeout=60  # 60秒超时
                )
                resp.raise_for_status()
                
                events = resp.json()
                for event in events:
                    event_id = event.get('id', 0)
                    event_type = event.get('type', '')
                    event_data = event.get('data', {})
                    
                    # 更新last_event_id
                    if event_id > last_event_id:
                        last_event_id = event_id
                    
                    # 调试输出关键事件类型（设备相关、下载相关等）
                    if event_type in ['DeviceConnected', 'DeviceDisconnected', 'DeviceDiscovered', 'LoginAttempt', 'ConfigSaved', 'ItemFinished', 'FolderSummary', 'DownloadProgress']:
                        logger.debug(f"Syncthing事件: {event_type} -> {event_data}")
                    
                    # 调用所有注册的回调（不筛选类型，交由上层处理）
                    for callback in self.event_callbacks:
                        try:
                            callback(event_type, event_data)
                        except Exception as e:
                            logger.debug(f"事件回调失败: {e}")
                
            except requests.exceptions.Timeout:
                # 超时是正常的，long polling会在没有事件时超时
                continue
            except Exception as e:
                if self.event_running:
                    logger.debug(f"事件监听错误: {e}")
                    time.sleep(1)  # 错误后等待一秒再重试
        
        logger.info("事件监听循环退出")
