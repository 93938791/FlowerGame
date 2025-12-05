"""Syncthing设备管理模块
负责设备的添加、移除和连接管理
"""
import time
import requests
from utils.logger import Logger

logger = Logger().get_logger("SyncthingDeviceManager")


class DeviceManager:
    """设备管理器"""
    
    def __init__(self, api_url, headers, config_manager, device_id=None):
        self.api_url = api_url
        self.headers = headers
        self.config_manager = config_manager
        self.device_id = device_id
    
    def set_device_id(self, device_id):
        """设置设备ID"""
        self.device_id = device_id
    
    def get_device_id(self):
        """获取本机设备ID"""
        try:
            resp = requests.get(f"{self.api_url}/rest/system/status", headers=self.headers, timeout=5)
            resp.raise_for_status()
            return resp.json()["myID"]
        except Exception as e:
            logger.error(f"获取设备ID失败: {e}")
            return None
    
    def add_device(self, device_id, device_name=None, device_address=None, async_mode=True):
        """添加远程设备
        
        Args:
            device_id: 设备ID
            device_name: 设备名称
            device_address: 设备地址（虚拟IP），例如 "10.126.126.2"
            async_mode: 是否异步执行（默认True，避免阻塞主程序）
            
        Returns:
            bool: True-新增成功或更新成功, False-失败, None-设备已存在且无需更新
        """
        # 检查是否是自己的设备ID，不应该添加自己
        if device_id == self.device_id:
            logger.debug(f"跳过添加自己的设备: {device_id[:7]}...")
            return None
        
        config = self.config_manager.get_config()
        if not config:
            return False
        
        # 检查设备是否已存在
        device_exists = False
        for device in config.get("devices", []):
            if device["deviceID"] == device_id:
                device_exists = True
                logger.debug(f"设备已存在: {device_id}")
                
                # 确保使用虚拟IP地址
                if device_address:
                    tcp_address = f"tcp://{device_address}:22000"
                    current_addresses = device.get("addresses", [])
                    
                    # 检查是否需要更新地址
                    if tcp_address not in current_addresses or current_addresses != [tcp_address]:
                        device["addresses"] = [tcp_address]
                        logger.info(f"更新已存在设备地址: {tcp_address}")
                        
                        # 保存配置
                        result = self.config_manager.set_config(config, async_mode=False)
                        if result:
                            # 触发Syncthing重新连接该设备
                            self.restart_device_connection(device_id)
                        return result
                
                # 设备已存在且配置正确，无需操作
                return None
        
        # 设备不存在，需要添加
        if not device_exists:
            # 必须提供虚拟IP地址，严格依赖 EasyTier 网络
            if not device_address:
                logger.warning("未提供虚拟IP地址，严格模式下不添加设备")
                return False

            # 配置仅虚拟IP地址（不使用 dynamic）
            tcp_address = f"tcp://{device_address}:22000"
            addresses = [tcp_address]
            logger.info(f"使用虚拟IP地址: {tcp_address}")
            
            # 添加新设备
            new_device = {
                "deviceID": device_id,
                "name": device_name or device_id[:7],
                "addresses": addresses,
                "compression": "metadata",
                "introducer": False,
                "skipIntroductionRemovals": False,
                "paused": False,
                # 自动接受共享文件夹（多客户端同步必需）
                "autoAcceptFolders": True
            }
            
            config["devices"].append(new_device)
            logger.info(f"添加新设备: {device_name or device_id[:7]} ({device_id[:7]}...) 地址: {addresses}")
            
            # 输出详细诊断信息
            logger.info(f"✅ 设备配置详情:")
            logger.info(f"   设备ID: {device_id}")
            logger.info(f"   设备名称: {device_name or device_id[:7]}")
            logger.info(f"   虚拟IP: {device_address}")
            logger.info(f"   连接地址: {addresses}")
            
            return self.config_manager.set_config(config, async_mode=async_mode)
    
    def enable_auto_accept_folders(self):
        """启用所有设备的自动接受共享文件夹（多客户端同步必需）"""
        try:
            config = self.config_manager.get_config()
            if not config:
                logger.warning("无法获取配置，跳过启用自动接受")
                return False
            
            # 检查所有设备
            devices = config.get('devices', [])
            updated_count = 0
            
            for device in devices:
                if not device.get('autoAcceptFolders', False):
                    device['autoAcceptFolders'] = True
                    updated_count += 1
            
            if updated_count > 0:
                # 同步保存配置
                result = self.config_manager.set_config(config, async_mode=False)
                if result:
                    logger.info(f"✅ 已启用 {updated_count} 个设备的自动接受共享文件夹")
                    logger.info("🔄 多客户端同步将自动工作")
                    return True
                else:
                    logger.warning("启用自动接受失败")
                    return False
            else:
                logger.info("✅ 所有设备已启用自动接受共享文件夹")
                return True
        except Exception as e:
            logger.error(f"启用自动接受失败: {e}")
            return False
    
    def restart_device_connection(self, device_id):
        """触发Syncthing重新连接指定设备"""
        try:
            # 通过设置设备为暂停再恢复来触发重连
            logger.info(f"触发设备重连: {device_id[:7]}...")
            
            # 获取配置
            config = self.config_manager.get_config()
            if not config:
                return False
            
            # 找到设备
            for device in config.get('devices', []):
                if device['deviceID'] == device_id:
                    # 先暂停
                    device['paused'] = True
                    self.config_manager.set_config(config, async_mode=False)
                    
                    # 等待一下
                    time.sleep(1)
                    
                    # 再恢复
                    device['paused'] = False
                    self.config_manager.set_config(config, async_mode=False)
                    
                    logger.info(f"✅ 已触发设备 {device_id[:7]}... 重连")
                    return True
            
            logger.warning(f"未找到设备: {device_id}")
            return False
        except Exception as e:
            logger.error(f"触发设备重连失败: {e}")
            return False
    
    def get_connections(self):
        """获取连接状态"""
        try:
            resp = requests.get(f"{self.api_url}/rest/system/connections", headers=self.headers, timeout=5)
            resp.raise_for_status()
            connections = resp.json()
            return connections
        except Exception as e:
            logger.error(f"获取连接状态失败: {e}")
            return None
    
    def get_traffic_stats(self):
        """
        获取Syncthing流量统计信息
        
        Returns:
            dict: 流量统计信息
                {
                    'tx_speed': 上传速度(bytes/s),
                    'rx_speed': 下载速度(bytes/s)
                }
        """
        try:
            # 获取连接信息，其中包含流量统计
            resp = requests.get(f"{self.api_url}/rest/system/connections", headers=self.headers, timeout=5)
            resp.raise_for_status()
            connections = resp.json()
            
            if not connections or 'connections' not in connections:
                return None
            
            # 计算总的上传和下载速度
            total_tx_speed = 0
            total_rx_speed = 0
            
            for device_id, conn_info in connections.get('connections', {}).items():
                if conn_info.get('connected', False):
                    # 从连接信息中获取流量速度
                    # Syncthing API 的 connections 端点可能不直接提供速度信息
                    # 我们需要从其他端点获取，或者使用连接信息中的其他字段
                    pass
            
            # 尝试从 /rest/stats/device 获取设备统计信息
            try:
                stats_resp = requests.get(f"{self.api_url}/rest/stats/device", headers=self.headers, timeout=5)
                if stats_resp.status_code == 200:
                    stats_data = stats_resp.json()
                    # 解析统计信息（需要根据实际API响应格式调整）
                    # 这里先返回None，等待实际测试后完善
                    pass
            except:
                pass
            
            # 由于Syncthing API可能不直接提供实时速度，我们返回None
            # 让调用方使用EasyTier的统计
            return None
            
        except Exception as e:
            logger.debug(f"获取Syncthing流量统计失败: {e}")
            return None
