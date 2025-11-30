"""Syncthing远程设备管理模块
负责获取远程设备的文件夹列表
"""
import requests
from utils.logger import Logger
from config import Config

logger = Logger().get_logger("SyncthingRemoteManager")


class RemoteManager:
    """远程设备管理器"""
    
    def __init__(self, device_id=None):
        self.device_id = device_id
    
    def set_device_id(self, device_id):
        """设置设备ID"""
        self.device_id = device_id
    
    def get_remote_device_folders(self, device_ip, device_id=None):
        """
        获取远程设备的文件夹列表
        
        Args:
            device_ip: 远程设备的虚拟IP地址
            device_id: 远程设备的ID（可选，用于验证）
            
        Returns:
            list: 远程设备的文件夹列表，失败返回None
        """
        try:
            headers = {"X-API-Key": Config.SYNCTHING_API_KEY}
            
            # 首先从 system/status 获取设备ID和设备名（这是最可靠的方式）
            remote_device_id = None
            remote_device_name = 'Unknown'
            
            try:
                status_url = f"http://{device_ip}:{Config.SYNCTHING_API_PORT}/rest/system/status"
                logger.debug(f"正在访问远程设备状态API: {status_url}")
                status_resp = requests.get(status_url, headers=headers, timeout=5)
                status_resp.raise_for_status()
                
                if status_resp.status_code == 200:
                    status_data = status_resp.json()
                    remote_device_id = status_data.get('myID')
                    if remote_device_id:
                        logger.info(f"✅ 从 {device_ip} 的 system/status 获取到设备ID: {remote_device_id[:7]}...")
                    else:
                        logger.error(f"❌ 从 {device_ip} 的 system/status 未找到 myID，响应键: {list(status_data.keys())}")
                else:
                    logger.error(f"❌ 访问 {device_ip} 的 system/status 失败，状态码: {status_resp.status_code}")
            except Exception as e:
                logger.error(f"❌ 从 {device_ip} 的 system/status 获取设备ID失败: {e}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
            
            if not remote_device_id:
                logger.error(f"❌ 无法从 {device_ip} 获取设备ID")
                return None
            
            # 验证设备ID（如果提供了）
            if device_id:
                if remote_device_id != device_id:
                    logger.warning(f"设备ID不匹配: 期望 {device_id[:7]}..., 实际 {remote_device_id[:7]}...")
                    return None
            
            # 然后从 config 获取文件夹列表
            config_url = f"http://{device_ip}:{Config.SYNCTHING_API_PORT}/rest/config"
            logger.debug(f"正在访问远程设备配置API: {config_url}")
            resp = requests.get(config_url, headers=headers, timeout=5)
            resp.raise_for_status()
            
            # 检查响应状态
            if resp.status_code != 200:
                logger.error(f"从 {device_ip} 获取配置失败，HTTP状态码: {resp.status_code}")
                return None
            
            remote_config = resp.json()
            
            # 检查配置是否有效
            if not remote_config:
                logger.error(f"从 {device_ip} 获取的配置为空")
                return None
            
            # 尝试从 config 获取设备名（如果存在）
            remote_device_name = remote_config.get('myName', 'Unknown')
            # 如果 config 中没有设备名，使用设备ID的前7位作为显示名
            if remote_device_name == 'Unknown':
                remote_device_name = f"设备 {remote_device_id[:7]}..."
            
            # 获取文件夹列表（只返回未暂停的文件夹，即正在分享的）
            folders = []
            
            # 确保 folders 是列表
            folders_list = remote_config.get('folders', [])
            if not isinstance(folders_list, list):
                logger.error(f"从 {device_ip} 获取的 folders 不是列表类型: {type(folders_list)}")
                return None
            
            for folder in folders_list:
                # 确保 folder 是字典
                if not isinstance(folder, dict):
                    logger.warning(f"跳过无效的文件夹项（不是字典）: {type(folder)}")
                    continue
                
                # 只返回未暂停的文件夹（正在分享的）
                if not folder.get('paused', False):
                    # 检查文件夹是否共享给本机
                    # 注意：远程设备的配置中，文件夹的设备列表包含的是共享给哪些设备
                    # 如果本机在列表中，说明这个文件夹是共享给本机的
                    devices_list = folder.get('devices', [])
                    if not isinstance(devices_list, list):
                        devices_list = []
                    
                    folder_devices = []
                    for d in devices_list:
                        if isinstance(d, dict):
                            dev_id = d.get('deviceID')
                            if dev_id:
                                folder_devices.append(dev_id)
                    
                    # 检查本机是否在设备列表中
                    shared_to_me = False
                    if self.device_id:
                        shared_to_me = self.device_id in folder_devices
                    
                    # 重要：返回所有未暂停的文件夹，不管是否已共享给本机
                    # 因为用户可能想要同步，即使还没有被添加到设备列表
                    # 当用户点击同步时，会自动将本机添加到远程设备的文件夹设备列表中
                    folders.append({
                        'id': folder.get('id'),
                        'label': folder.get('label', folder.get('id')),
                        'path': folder.get('path'),  # 远程设备的路径
                        'device_id': remote_device_id,
                        'device_ip': device_ip,
                        'device_name': remote_device_name,
                        'shared_to_me': shared_to_me  # 是否已共享给本机
                    })
                    logger.debug(f"发现远程设备 {remote_device_name} 的文件夹: {folder.get('id')}, 共享给本机: {shared_to_me}")
            
            if len(folders) > 0:
                logger.info(f"从 {remote_device_name} ({device_ip}) 获取到 {len(folders)} 个文件夹: {[f.get('id') for f in folders]}")
            return folders
        except requests.exceptions.Timeout:
            logger.warning(f"获取远程设备 {device_ip} 的文件夹列表超时")
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning(f"获取远程设备 {device_ip} 的文件夹列表HTTP错误: {e}, 状态码: {e.response.status_code if hasattr(e, 'response') else 'N/A'}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"无法连接到远程设备 {device_ip} 的Syncthing API: {e}")
            return None
        except Exception as e:
            logger.error(f"获取远程设备文件夹列表失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return None
