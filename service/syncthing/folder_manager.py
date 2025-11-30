"""Syncthing文件夹管理模块
负责文件夹的添加、移除、暂停和恢复等操作
"""
from pathlib import Path
import requests
from utils.logger import Logger
from config import Config

logger = Logger().get_logger("SyncthingFolderManager")


class FolderManager:
    """文件夹管理器"""
    
    def __init__(self, api_url, headers, config_manager, device_id=None):
        self.api_url = api_url
        self.headers = headers
        self.config_manager = config_manager
        self.device_id = device_id
    
    def set_device_id(self, device_id):
        """设置设备ID"""
        self.device_id = device_id
    
    def add_folder(self, folder_path, folder_id=None, folder_label=None, devices=None, watcher_delay=10, paused=True, async_mode=True):
        """
        添加同步文件夹
        
        Args:
            folder_path: 本地文件夹路径
            folder_id: 文件夹ID（默认使用配置的ID）
            folder_label: 文件夹标签
            devices: 共享设备ID列表
            watcher_delay: 文件监控延迟(秒),文件静默这么久后才同步
            paused: 是否暂停同步（默认为True，需要手动启动）
            async_mode: 是否异步执行（默认True，避免阻塞主程序）
        """
        folder_path = Path(folder_path)
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建同步目录: {folder_path}")
        
        # 创建 .stfolder 标记文件夹（Syncthing 必需）
        stfolder_marker = folder_path / ".stfolder"
        if not stfolder_marker.exists():
            stfolder_marker.mkdir(exist_ok=True)
            logger.info(f"创建 .stfolder 标记文件夹: {stfolder_marker}")
        
        config = self.config_manager.get_config()
        if not config:
            return False
        
        folder_id = folder_id or Config.SYNC_FOLDER_ID
        folder_label = folder_label or Config.SYNC_FOLDER_LABEL
        
        # 检查文件夹是否已存在
        for folder in config.get("folders", []):
            if folder["id"] == folder_id:
                logger.info(f"文件夹已存在: {folder_id}")
                # 更新路径、设备、延迟和暂停状态
                folder["path"] = str(folder_path)
                folder["fsWatcherDelayS"] = watcher_delay
                folder["paused"] = paused  # 更新暂停状态
                if devices:
                    folder["devices"] = [{"deviceID": dev_id} for dev_id in devices]
                    logger.info(f"✅ 更新文件夹设备列表: 共享给 {len(devices)} 个设备: {[dev_id[:7] + '...' for dev_id in devices]}")
                else:
                    logger.warning(f"⚠️ 文件夹 {folder_id} 未共享给任何设备")
                logger.info(f"更新文件夹: 延迟={watcher_delay}秒, 暂停={paused}")
                return self.config_manager.set_config(config, async_mode=async_mode)
        
        # 创建新文件夹
        new_folder = {
            "id": folder_id,
            "label": folder_label,
            "path": str(folder_path),
            "type": "sendreceive",
            "devices": [{"deviceID": dev_id} for dev_id in (devices or [])],
            "rescanIntervalS": 60,
            "fsWatcherEnabled": True,
            "fsWatcherDelayS": watcher_delay,  # 懒同步延迟
            "ignorePerms": False,
            "autoNormalize": True,
            "minDiskFree": {"value": 0.5, "unit": "%"},
            "versioning": {"type": "", "params": {}},
            "copiers": 0,
            "pullerMaxPendingKiB": 0,
            "hashers": 0,
            "order": "random",
            "ignoreDelete": False,
            "scanProgressIntervalS": 0,
            "pullerPauseS": 0,
            "maxConflicts": 10,
            "disableSparseFiles": False,
            "disableTempIndexes": False,
            "paused": paused,  # 使用参数控制是否暂停
            "weakHashThresholdPct": 25,
            "markerName": ".stfolder"
        }
        
        # 输出详细的设备共享信息
        if devices:
            logger.info(f"✅ 创建同步文件夹: {folder_id}, 共享给 {len(devices)} 个设备: {[dev_id[:7] + '...' for dev_id in devices]}")
        else:
            logger.warning(f"⚠️ 创建同步文件夹: {folder_id}, 但未共享给任何设备")
        logger.info(f"文件夹配置: 延迟={watcher_delay}秒, 暂停={paused}")
        config["folders"].append(new_folder)
        
        return self.config_manager.set_config(config, async_mode=async_mode)
    
    def add_device_to_folder(self, folder_id, device_id):
        """
        添加设备到文件夹
        
        Args:
            folder_id: 文件夹ID
            device_id: 设备ID
            
        Returns:
            bool: 是否成功
        """
        try:
            config = self.config_manager.get_config()
            if not config:
                return False
            
            # 查找文件夹
            for folder in config.get('folders', []):
                if folder['id'] == folder_id:
                    # 检查设备是否已存在
                    existing_devices = folder.get('devices', [])
                    for dev in existing_devices:
                        if dev['deviceID'] == device_id:
                            logger.info(f"设备已在文件夹中: {device_id[:7]}")
                            return True
                    
                    # 添加设备
                    existing_devices.append({'deviceID': device_id})
                    folder['devices'] = existing_devices
                    logger.info(f"已添加设备 {device_id[:7]}... 到文件夹 {folder_id}")
                    return self.config_manager.set_config(config, async_mode=True)
            
            logger.warning(f"未找到文件夹: {folder_id}")
            return False
        except Exception as e:
            logger.error(f"添加设备到文件夹失败: {e}")
            return False
    
    def resume_folder(self, folder_id):
        """
        恢复文件夹同步
        
        Args:
            folder_id: 文件夹ID
            
        Returns:
            bool: 是否成功
        """
        try:
            config = self.config_manager.get_config()
            if not config:
                return False
            
            # 查找文件夹
            for folder in config.get('folders', []):
                if folder['id'] == folder_id:
                    # 确保 .stfolder 标记文件夹存在
                    folder_path = Path(folder.get('path', ''))
                    if folder_path.exists():
                        stfolder_marker = folder_path / ".stfolder"
                        if not stfolder_marker.exists():
                            stfolder_marker.mkdir(exist_ok=True)
                            logger.info(f"创建 .stfolder 标记文件夹: {stfolder_marker}")
                    
                    # 检查是否有共享设备（get_config已自动过滤本机ID）
                    folder_devices = folder.get('devices', [])
                    if not folder_devices:
                        logger.warning(f"⚠️ 文件夹 {folder_id} 未共享给任何设备，无法同步")
                        return False
                    
                    device_ids = [d['deviceID'] for d in folder_devices]
                    logger.info(f"✅ 恢复文件夹同步: {folder_id}, 共享给 {len(device_ids)} 个设备: {[dev_id[:7] + '...' for dev_id in device_ids]}")
                    
                    folder['paused'] = False
                    logger.info(f"已恢复文件夹同步: {folder_id}")
                    # 使用异步模式，避免阻塞主窗口
                    result = self.config_manager.set_config(config, async_mode=True)
                    
                    return result
            
            logger.warning(f"未找到文件夹: {folder_id}")
            return False
        except Exception as e:
            logger.error(f"恢复文件夹同步失败: {e}")
            return False
    
    def pause_folder(self, folder_id):
        """
        暂停文件夹同步
        
        Args:
            folder_id: 文件夹ID
            
        Returns:
            bool: 是否成功
        """
        try:
            config = self.config_manager.get_config()
            if not config:
                return False
            
            # 查找文件夹
            for folder in config.get('folders', []):
                if folder['id'] == folder_id:
                    folder['paused'] = True
                    logger.info(f"已暂停文件夹同步: {folder_id}")
                    # 使用异步模式，避免阻塞主窗口
                    return self.config_manager.set_config(config, async_mode=True)
            
            logger.warning(f"未找到文件夹: {folder_id}")
            return False
        except Exception as e:
            logger.error(f"暂停文件夹同步失败: {e}")
            return False
    
    def remove_folder(self, folder_id, async_mode=True):
        """
        移除同步文件夹
        
        Args:
            folder_id: 文件夹ID
            async_mode: 是否异步执行（默认True，避免阻塞主程序）
            
        Returns:
            bool: 是否成功
        """
        try:
            # 使用 use_cache=False 确保获取最新配置，避免删除已不存在的文件夹
            config = self.config_manager.get_config(use_cache=False)
            if not config:
                return False
            
            # 查找并移除文件夹
            folders = config.get('folders', [])
            folder_found = False
            for i, folder in enumerate(folders):
                if folder['id'] == folder_id:
                    folders.pop(i)
                    folder_found = True
                    logger.info(f"已从配置中移除文件夹: {folder_id}")
                    break
            
            if not folder_found:
                logger.warning(f"未找到文件夹: {folder_id}，可能已被删除")
                # 即使未找到，也清除缓存，确保下次获取最新配置
                self.config_manager.invalidate_cache()
                return False
            
            # 保存配置（会清除缓存）
            result = self.config_manager.set_config(config, async_mode=async_mode)
            if result:
                logger.info(f"✅ 已成功移除文件夹: {folder_id}")
            else:
                logger.error(f"❌ 移除文件夹失败: {folder_id}")
            
            return result
        except Exception as e:
            logger.error(f"移除文件夹失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 发生错误时也清除缓存
            self.config_manager.invalidate_cache()
            return False
    
    def get_folder_status(self, folder_id=None):
        """获取文件夹同步状态"""
        folder_id = folder_id or Config.SYNC_FOLDER_ID
        try:
            resp = requests.get(
                f"{self.api_url}/rest/db/status",
                params={"folder": folder_id},
                headers=self.headers,
                timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"获取文件夹状态失败: {e}")
            return None
    
    def get_completion(self, device_id, folder_id=None):
        """获取同步完成度"""
        folder_id = folder_id or Config.SYNC_FOLDER_ID
        try:
            resp = requests.get(
                f"{self.api_url}/rest/db/completion",
                params={"device": device_id, "folder": folder_id},
                headers=self.headers,
                timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"获取同步完成度失败: {e}")
            return None
    
    def is_syncing(self):
        """检查是否正在同步"""
        status = self.get_folder_status()
        if status:
            return status.get("state") in ["syncing", "scanning"]
        return False
    
    def get_sync_progress(self):
        """获取同步进度信息"""
        status = self.get_folder_status()
        if not status:
            return None
        
        state = status.get("state", "unknown")
        global_bytes = status.get("globalBytes", 0)
        in_sync_bytes = status.get("inSyncBytes", 0)
        
        if global_bytes > 0:
            progress = (in_sync_bytes / global_bytes) * 100
        else:
            progress = 100
        
        return {
            "state": state,
            "progress": progress,
            "globalBytes": global_bytes,
            "inSyncBytes": in_sync_bytes
        }
