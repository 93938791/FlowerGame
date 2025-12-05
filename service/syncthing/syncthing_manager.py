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
        log_file = Config.LOG_DIR / "syncthing.log" if Config.LOG_DIR else None
        self.process = ProcessHelper.start_process(
            Config.SYNCTHING_BIN,
            args=args,
            env=env,
            hide_window=True,
            log_file=log_file
        )
        
        # 等待API就绪（增加超时时间）
        if not ProcessHelper.wait_for_port(Config.SYNCTHING_API_PORT, timeout=60):
            # 读取日志文件最后几行
            error_msg = "Syncthing启动超时"
            if log_file and log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        last_lines = lines[-20:] if len(lines) > 20 else lines
                        error_msg += f"\n最后日志:\n{''.join(last_lines)}"
                except Exception as e:
                    error_msg += f"\n无法读取日志: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
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
        
        # 确保 GUI 配置中的默认行为是自动接受
        self.config_manager.enable_default_auto_accept()
        
        # 启动事件监听
        # 注册设备自动添加的事件处理
        self.event_manager.register_callback(self._on_syncthing_event)
        self.event_manager.start_listener()
        
        return True

    def is_running(self):
        """检查 Syncthing 是否正在运行"""
        return self.process is not None and ProcessHelper.is_process_running(self.process)
    
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

    def scan_network_shares(self, peers):
        """
        扫描网络中所有节点的分享目录
        
        Args:
            peers: Easytier节点列表 (包含 ipv4)
            
        Returns:
            list: 分享目录列表 (已过滤本地存在的文件夹，并按ID去重)
        """
        # 1. 获取本地已存在的文件夹ID集合（未启动时跳过，避免REST连接被拒绝）
        local_folder_ids = set()
        local_config = None
        if self.is_running():
            try:
                local_config = self.config_manager.get_config()
                if local_config and 'folders' in local_config:
                    for f in local_config['folders']:
                        local_folder_ids.add(f['id'])
            except Exception as e:
                logger.warning(f"获取本地配置失败: {e}")
        else:
            logger.info("Syncthing 未运行，扫描远程分享时跳过本地配置过滤")

        # 2. 扫描并聚合远程分享
        # 使用字典按folder_id去重
        unique_shares = {}
        
        for peer in peers:
            # 跳过自己
            if peer.get('is_local'):
                continue
                
            ip = peer.get('ipv4')
            if not ip:
                continue
                
            logger.info(f"正在扫描节点 {ip} ({peer.get('hostname')}) 的分享...")
            
            try:
                folders = self.remote_manager.get_remote_device_folders(ip)
                
                if folders:
                    for folder_info in folders:
                        folder_id = folder_info.get('id')
                        if not folder_id:
                            continue
                        
                        # 策略1: 过滤掉本地已经存在的文件夹（仅当本地配置可用时）
                        if local_config and folder_id in local_folder_ids:
                            continue
                        
                        # 策略2: 去重
                        # 如果这个ID已经扫描到了，我们只需要更新它的来源信息（可选）
                        # 这里简单处理：保留第一个发现的，或者保留元数据最完整的
                        if folder_id not in unique_shares:
                            share_info = {
                                'device_id': folder_info.get('device_id'), 
                                'device_name': peer.get('hostname'),
                                'device_ip': ip,
                                'folder_id': folder_id,
                                'folder_label': folder_info.get('label', folder_id),
                                'folder_path': folder_info.get('path'),
                                'is_connected': False # 既然本地没有，那肯定未连接
                            }
                            unique_shares[folder_id] = share_info
                        else:
                            # 可以在这里记录"该资源有多个来源"，目前UI不需要，略过
                            pass
                            
            except Exception as e:
                logger.warning(f"扫描节点 {ip} 失败: {e}")
                continue
        
        return list(unique_shares.values())

    def share_save(self, version_id, save_name, save_path):
        """
        分享存档
        
        Args:
            version_id: 游戏版本ID
            save_name: 存档名称
            save_path: 存档绝对路径
        """
        # 构造唯一的文件夹ID
        folder_id = f"save-{version_id}-{save_name}"
        label = f"存档-{save_name} ({version_id})"
        
        # 默认开启版本控制，防止误删
        versioning = {
            "type": "simple",
            "params": {
                "keep": "5"  # 保留最近5个版本
            }
        }
        
        devices = []
        try:
            config = self.config_manager.get_config()
            if config and 'devices' in config:
                for d in config['devices']:
                    dev_id = d.get('deviceID')
                    if dev_id:
                        devices.append(dev_id)
        except Exception:
            pass

        return self.folder_manager.add_folder(
            folder_id=folder_id,
            folder_label=label,
            folder_path=str(save_path),
            folder_type="sendreceive",
            devices=devices,
            paused=False,
            versioning=versioning,
            async_mode=False
        )

    def connect_share(self, device_id, folder_id, local_path, folder_label=None, device_ip=None, device_name=None):
        """
        连接远程分享
        
        Args:
            device_id: 远程设备ID
            folder_id: 文件夹ID
            local_path: 本地存储路径
            folder_label: 文件夹标签
            device_ip: 远程设备IP (用于添加设备)
            device_name: 远程设备名称 (用于添加设备)
        """
        # 1. 确保设备已添加
        # 注意：device_manager.get_device 可能不存在，需要实现或检查配置
        config = self.config_manager.get_config()
        device_exists = False
        if config:
            for device in config.get('devices', []):
                if device['deviceID'] == device_id:
                    device_exists = True
                    break
        
        if not device_exists:
            if device_ip:
                logger.info(f"设备 {device_id} 不存在，正在添加... (IP: {device_ip})")
                self.add_device(device_id, device_name, device_ip)
                # 等待配置生效
                time.sleep(1)
            else:
                logger.warning(f"无法添加设备 {device_id}: 缺少IP地址")
                return False
            
        # 2. 添加文件夹并共享给该设备
        # 注意：Syncthing 需要双方都添加对方设备，并共享文件夹
        # 如果对方已经共享给我们（Auto Accept），我们只需要添加文件夹即可
        
        # 默认开启版本控制，防止误删
        versioning = {
            "type": "simple",
            "params": {
                "keep": "5"  # 保留最近5个版本
            }
        }
        
        return self.folder_manager.add_folder(
            folder_id=folder_id,
            folder_label=folder_label or folder_id,
            folder_path=str(local_path),
            folder_type="sendreceive",
            devices=[device_id], # 明确指定共享给该设备
            paused=False,
            versioning=versioning
        )
    
    def add_device(self, device_id, device_name=None, device_address=None, async_mode=True):
        """添加远程设备"""
        return self.device_manager.add_device(device_id, device_name, device_address, async_mode)
    
    def add_folder(self, folder_path, folder_id=None, folder_label=None, devices=None, watcher_delay=10, paused=True, async_mode=True):
        """添加同步文件夹"""
        return self.folder_manager.add_folder(folder_path, folder_id, folder_label, devices, watcher_delay, paused, async_mode)

    def get_traffic_stats(self):
        """获取Syncthing流量统计（若不可用返回None）"""
        try:
            return self.device_manager.get_traffic_stats()
        except Exception:
            return None

    # ==================== 事件处理 ====================
    def _on_syncthing_event(self, event_type, data):
        """处理 Syncthing 事件，实现自动添加未知设备"""
        try:
            # 处理设备请求被拒绝事件（通常是未添加的设备尝试连接）
            if event_type == 'DeviceRejected':
                dev_id = data.get('device')
                dev_name = data.get('name') or dev_id[:7]
                
                if dev_id:
                    logger.info(f"发现新设备请求 (DeviceRejected): {dev_id} ({dev_name})")
                    # 按照需求使用 dynamic 地址并开启自动分享
                    self.device_manager.add_device(dev_id, device_name=dev_name, device_address="dynamic", async_mode=False)
                return

            # 设备连接/发现事件：自动添加未知设备
            if event_type in ['DeviceConnected', 'DeviceDiscovered', 'LoginAttempt']:
                # 尝试从事件数据提取设备ID与地址
                dev_id = data.get('id') or data.get('device') or data.get('deviceID')
                addr = data.get('addr') or data.get('address') or ''

                if not dev_id:
                    return

                # 检查设备是否已经存在
                config = self.config_manager.get_config()
                exists = False
                if config:
                    for d in config.get('devices', []):
                        if d.get('deviceID') == dev_id:
                            exists = True
                            break

                if exists:
                    return

                # 从地址中提取IPv4，并按虚拟IP地址构造连接地址
                ip = None
                try:
                    # 可能形如 "tcp://10.126.126.2:22000" 或 "10.126.126.2:22000"
                    txt = str(addr)
                    if '://' in txt:
                        txt = txt.split('://', 1)[1]
                    ip_port = txt.split('/')[-1]
                    ip_part = ip_port.split(':')[0]
                    if ip_part and ip_part.count('.') == 3:
                        ip = ip_part
                except Exception:
                    pass

                if not ip:
                    # 无法从事件获取地址时，不进行自动添加（避免添加到非虚拟网卡）
                    return

                # 自动添加设备，仅使用虚拟IP地址
                logger.info(f"自动添加未知设备: {dev_id[:7]}... @ {ip}")
                self.device_manager.add_device(dev_id, device_name=dev_id[:7], device_address=ip, async_mode=False)
        except Exception as e:
            logger.debug(f"事件处理失败: {e}")
