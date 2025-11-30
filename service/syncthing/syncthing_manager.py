"""Syncthing管理模块
负责Syncthing的启动、配置和API交互
"""
import os
import time
import psutil
from utils.logger import Logger
from utils.process_helper import ProcessHelper
from config import Config
from .config_manager import ConfigManager
from .device_manager import DeviceManager
from .folder_manager import FolderManager
from .event_manager import EventManager
from .remote_manager import RemoteManager

logger = Logger().get_logger("SyncthingManager")


class SyncthingManager:
    """Syncthing管理器"""
    
    def __init__(self):
        self.process = None
        self.api_url = f"http://localhost:{Config.SYNCTHING_API_PORT}"
        self.headers = {"X-API-Key": Config.SYNCTHING_API_KEY}
        self.device_id = None
        
        # 初始化各个管理器
        self.config_manager = ConfigManager(self.api_url, self.headers)
        self.device_manager = DeviceManager(self.api_url, self.headers, self.config_manager)
        self.folder_manager = FolderManager(self.api_url, self.headers, self.config_manager)
        self.event_manager = EventManager(self.api_url, self.headers)
        self.remote_manager = RemoteManager()
    
    def start(self):
        """启动Syncthing服务"""
        if not Config.SYNCTHING_BIN.exists():
            raise FileNotFoundError(f"Syncthing程序不存在: {Config.SYNCTHING_BIN}")
        
        # 先杀死占用端口的进程
        ProcessHelper.kill_by_port(Config.SYNCTHING_API_PORT)
        
        # 准备环境变量
        env = os.environ.copy()
        env["STHOMEDIR"] = str(Config.SYNCTHING_HOME)
        
        # 启动参数：禁用浏览器、禁用升级检查
        # gui-address=0.0.0.0 表示监听所有网络接口（包括虚拟网卡）
        # Syncthing v2.0+ 不再支持 --listen-address，监听地址通过配置文件管理
        args = [
            "--no-browser",
            "--no-upgrade",
            f"--gui-address=0.0.0.0:{Config.SYNCTHING_API_PORT}",
            f"--gui-apikey={Config.SYNCTHING_API_KEY}",
            "--home", str(Config.SYNCTHING_HOME)
        ]
        
        # 启动进程
        self.process = ProcessHelper.start_process(
            Config.SYNCTHING_BIN,
            args=args,
            env=env,
            hide_window=True
        )
        
        # 等待API就绪（增加超时时间）
        if not ProcessHelper.wait_for_port(Config.SYNCTHING_API_PORT, timeout=60):
            raise RuntimeError("Syncthing启动超时")
        
        # 等待API完全可用
        time.sleep(3)
        
        # 获取本机设备ID
        self.device_id = self.device_manager.get_device_id()
        logger.info(f"Syncthing启动成功，设备ID: {self.device_id}")
        
        # 设置各个管理器的设备ID
        self.config_manager.set_device_id(self.device_id)
        self.device_manager.set_device_id(self.device_id)
        self.folder_manager.set_device_id(self.device_id)
        self.remote_manager.set_device_id(self.device_id)
        
        # 禁用本地发现和全局发现，强制只使用EasyTier虚拟IP
        self.config_manager.disable_discovery()
        
        # 配置监听地址（确保监听所有接口）
        self.config_manager.configure_listen_address()
        
        # 启用所有设备的自动接受共享文件夹（多客户端同步必需）
        self.device_manager.enable_auto_accept_folders()
        
        # 启动事件监听
        self.event_manager.start_listener()
        
        return True
    
    def stop(self):
        """停止Syncthing服务（彻底清理所有进程）"""
        # 停止事件监听
        self.event_manager.stop_listener()
        
        # 先尝试通过API优雅地关闭Syncthing（缩短超时时间）
        try:
            logger.info("尝试通过API关闭Syncthing...")
            import requests
            resp = requests.post(
                f"{self.api_url}/rest/system/shutdown",
                headers=self.headers,
                timeout=1  # 缩短超时时间到1秒
            )
            if resp.status_code == 200:
                logger.info("✅ Syncthing API关闭请求已发送")
                time.sleep(0.3)  # 缩短等待时间到0.3秒
        except Exception as e:
            logger.warning(f"API关闭失败，将强制结束进程: {e}")
        
        # 强制结束当前进程
        if self.process:
            try:
                ProcessHelper.kill_process(self.process, timeout=3)
            except Exception as e:
                logger.warning(f"结束进程失败: {e}")
            self.process = None
        
        # 杀死所有占用端口的进程
        ProcessHelper.kill_by_port(Config.SYNCTHING_API_PORT)
        
        # 彻底清理所有Syncthing相关进程
        self._kill_all_syncthing_processes()
        
        logger.info("✅ Syncthing已彻底停止")
    
    def _kill_all_syncthing_processes(self):
        """彻底清理所有Syncthing相关进程"""
        try:
            syncthing_names = ['syncthing.exe', 'syncthing']
            killed_count = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    proc_name = proc.info.get('name', '').lower()
                    proc_exe = proc.info.get('exe', '')
                    
                    # 检查进程名
                    is_syncthing = False
                    for name in syncthing_names:
                        if name.lower() in proc_name:
                            is_syncthing = True
                            break
                    
                    # 检查可执行文件路径
                    if not is_syncthing and proc_exe:
                        exe_name = os.path.basename(proc_exe).lower()
                        for name in syncthing_names:
                            if name.lower() in exe_name:
                                is_syncthing = True
                                break
                    
                    if is_syncthing:
                        logger.info(f"发现Syncthing进程: {proc_name} (PID: {proc.info['pid']})，正在清理...")
                        try:
                            proc.terminate()
                            proc.wait(timeout=2)
                            killed_count += 1
                            logger.info(f"✅ 已清理进程 PID: {proc.info['pid']}")
                        except psutil.TimeoutExpired:
                            logger.warning(f"进程 {proc.info['pid']} 未响应，强制杀死...")
                            proc.kill()
                            proc.wait(timeout=1)
                            killed_count += 1
                        except psutil.NoSuchProcess:
                            pass
                        except Exception as e:
                            logger.warning(f"清理进程 {proc.info['pid']} 失败: {e}")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    logger.debug(f"检查进程失败: {e}")
            
            if killed_count > 0:
                logger.info(f"✅ 共清理了 {killed_count} 个Syncthing进程")
            else:
                logger.debug("未发现残留的Syncthing进程")
                
        except Exception as e:
            logger.error(f"清理Syncthing进程失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # 委托给各个管理器的方法
    def get_device_id(self):
        """获取本机设备ID"""
        return self.device_manager.get_device_id()
    
    def get_config(self, filter_self=True, use_cache=True):
        """获取完整配置"""
        return self.config_manager.get_config(filter_self, use_cache)
    
    def set_config(self, config, async_mode=False):
        """设置完整配置"""
        return self.config_manager.set_config(config, async_mode)
    
    def add_device(self, device_id, device_name=None, device_address=None, async_mode=True):
        """添加远程设备"""
        return self.device_manager.add_device(device_id, device_name, device_address, async_mode)
    
    def add_folder(self, folder_path, folder_id=None, folder_label=None, devices=None, watcher_delay=10, paused=True, async_mode=True):
        """添加同步文件夹"""
        return self.folder_manager.add_folder(folder_path, folder_id, folder_label, devices, watcher_delay, paused, async_mode)
    
    def add_device_to_folder(self, folder_id, device_id):
        """添加设备到文件夹"""
        return self.folder_manager.add_device_to_folder(folder_id, device_id)
    
    def resume_folder(self, folder_id):
        """恢复文件夹同步"""
        return self.folder_manager.resume_folder(folder_id)
    
    def pause_folder(self, folder_id):
        """暂停文件夹同步"""
        return self.folder_manager.pause_folder(folder_id)
    
    def remove_folder(self, folder_id, async_mode=True):
        """移除同步文件夹"""
        return self.folder_manager.remove_folder(folder_id, async_mode)
    
    def get_connections(self):
        """获取连接状态"""
        return self.device_manager.get_connections()
    
    def get_traffic_stats(self):
        """获取流量统计信息"""
        return self.device_manager.get_traffic_stats()
    
    def get_folder_status(self, folder_id=None):
        """获取文件夹同步状态"""
        return self.folder_manager.get_folder_status(folder_id)
    
    def get_completion(self, device_id, folder_id=None):
        """获取同步完成度"""
        return self.folder_manager.get_completion(device_id, folder_id)
    
    def is_syncing(self):
        """检查是否正在同步"""
        return self.folder_manager.is_syncing()
    
    def get_sync_progress(self):
        """获取同步进度信息"""
        return self.folder_manager.get_sync_progress()
    
    def register_event_callback(self, callback):
        """注册事件回调函数"""
        return self.event_manager.register_callback(callback)
    
    def start_event_listener(self):
        """启动事件监听"""
        return self.event_manager.start_listener()
    
    def stop_event_listener(self):
        """停止事件监听"""
        return self.event_manager.stop_listener()
    
    def get_remote_device_folders(self, device_ip, device_id=None):
        """获取远程设备的文件夹列表"""
        return self.remote_manager.get_remote_device_folders(device_ip, device_id)
