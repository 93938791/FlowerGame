"""Syncthing配置管理模块
负责配置的获取、设置和缓存管理
"""
import time
import copy
import threading
import requests
from utils.logger import Logger

logger = Logger().get_logger("SyncthingConfigManager")


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, api_url, headers, device_id=None):
        self.api_url = api_url
        self.headers = headers
        self.device_id = device_id
        
        # 配置缓存机制
        self._config_cache = None  # 缓存的配置
        self._config_cache_time = 0  # 缓存时间戳
        self._config_cache_ttl = 1.0  # 缓存有效期（秒），1秒内使用缓存
        self._config_cache_lock = threading.Lock()  # 缓存锁，确保线程安全
    
    def set_device_id(self, device_id):
        """设置设备ID"""
        self.device_id = device_id
    
    def get_config(self, filter_self=True, use_cache=True):
        """获取完整配置
        
        Args:
            filter_self: 是否过滤本机ID（默认True）
            use_cache: 是否使用缓存（默认True，提高性能）
        """
        # 检查缓存
        if use_cache:
            with self._config_cache_lock:
                current_time = time.time()
                # 如果缓存有效且未过期，直接返回缓存
                if (self._config_cache is not None and 
                    self._config_cache_time > 0 and 
                    (current_time - self._config_cache_time) < self._config_cache_ttl):
                    logger.debug("使用缓存的配置")
                    # 返回缓存的深拷贝，避免外部修改影响缓存
                    return copy.deepcopy(self._config_cache)
        
        try:
            # 从API获取最新配置
            resp = requests.get(f"{self.api_url}/rest/config", headers=self.headers, timeout=5)
            resp.raise_for_status()
            config = resp.json()
            
            # 关键修复：每次读取配置时自动过滤本机ID
            # 防止 Syncthing 自动添加本机到设备列表
            if config and self.device_id and filter_self:
                # 1. 过滤设备列表中的本机ID
                if 'devices' in config:
                    original_count = len(config['devices'])
                    config['devices'] = [dev for dev in config['devices'] if dev.get('deviceID') != self.device_id]
                    removed = original_count - len(config['devices'])
                    if removed > 0:
                        logger.debug(f"⚠️ get_config中过滤了设备列表中的 {removed} 个本机ID")
                
                # 2. 过滤文件夹设备列表中的本机ID（关键！）
                if 'folders' in config:
                    for folder in config['folders']:
                        if 'devices' in folder:
                            original_count = len(folder['devices'])
                            folder['devices'] = [dev for dev in folder['devices'] if dev.get('deviceID') != self.device_id]
                            removed = original_count - len(folder['devices'])
                            if removed > 0:
                                logger.debug(f"⚠️ 从文件夹 {folder.get('id')} 中过滤了 {removed} 个本机ID")
            
            # 更新缓存
            if use_cache:
                with self._config_cache_lock:
                    self._config_cache = copy.deepcopy(config)  # 深拷贝保存
                    self._config_cache_time = time.time()
                    logger.debug("配置缓存已更新")
            
            return config
        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            # 如果API请求失败，尝试返回缓存（如果有）
            if use_cache:
                with self._config_cache_lock:
                    if self._config_cache is not None:
                        logger.warning("API请求失败，使用过期缓存")
                        return copy.deepcopy(self._config_cache)
            return None
    
    def invalidate_cache(self):
        """使配置缓存失效（在配置更新后调用）"""
        with self._config_cache_lock:
            self._config_cache = None
            self._config_cache_time = 0
            logger.debug("配置缓存已失效")
    
    def set_config(self, config, async_mode=False):
        """设置完整配置
        
        Args:
            config: 配置对象
            async_mode: 是否异步执行（避免阻塞主程序）
        """
        def _do_set_config():
            try:
                # 关键修复：每次保存配置前都清理本机ID（防止被重新添加）
                if config and self.device_id:
                    # 1. 清理设备列表
                    if 'devices' in config:
                        original_count = len(config['devices'])
                        config['devices'] = [dev for dev in config['devices'] if dev.get('deviceID') != self.device_id]
                        removed = original_count - len(config['devices'])
                        if removed > 0:
                            logger.warning(f"⚠️ set_config检测到设备列表中有 {removed} 个本机ID（已清理）")
                    
                    # 2. 清理文件夹设备列表
                    if 'folders' in config:
                        for folder in config['folders']:
                            if 'devices' in folder:
                                original_count = len(folder['devices'])
                                folder['devices'] = [dev for dev in folder['devices'] if dev.get('deviceID') != self.device_id]
                                removed = original_count - len(folder['devices'])
                                if removed > 0:
                                    logger.warning(f"⚠️ set_config检测到文件夹 {folder.get('id')} 中有 {removed} 个本机ID（已清理）")
                
                resp = requests.put(
                    f"{self.api_url}/rest/config",
                    headers=self.headers,
                    json=config,
                    timeout=30  # 增加超时时间
                )
                resp.raise_for_status()
                logger.info("配置已更新")
                
                # 配置更新后，使缓存失效
                self.invalidate_cache()
                
                return True
            except Exception as e:
                logger.error(f"设置配置失败: {e}")
                return False
        
        if async_mode:
            # 异步执行，避免阻塞主程序
            thread = threading.Thread(target=_do_set_config, daemon=True)
            thread.start()
            logger.info("配置更新已提交到后台线程")
            return True
        else:
            return _do_set_config()
    
    def disable_discovery(self):
        """禁用 Syncthing 的本地/全局发现与中继，强制仅走配置地址"""
        try:
            config = self.get_config()
            if not config:
                logger.warning("无法获取配置，跳过禁用发现")
                return False
            
            options = config.get('options', {})
            original_local = options.get('localAnnounceEnabled', True)
            original_global = options.get('globalAnnounceEnabled', True)
            original_relay = options.get('relaysEnabled', True)
            
            options['localAnnounceEnabled'] = False
            options['globalAnnounceEnabled'] = False
            options['relaysEnabled'] = False
            options['natEnabled'] = False
            options['urAccepted'] = -1
            
            config['options'] = options
            result = self.set_config(config, async_mode=False)
            if result:
                logger.info(f"✅ 已禁用发现：local={original_local}→False, global={original_global}→False, relay={original_relay}→False")
            else:
                logger.warning("禁用发现失败")
            return result
        except Exception as e:
            logger.error(f"禁用发现失败: {e}")
            return False
    
    def enable_default_auto_accept(self):
        """启用默认的自动接受文件夹（GUI配置）"""
        try:
            config = self.get_config()
            if not config:
                return False
            
            defaults = config.get('defaults', {})
            device_defaults = defaults.get('device', {})
            
            if not device_defaults.get('autoAcceptFolders', False):
                device_defaults['autoAcceptFolders'] = True
                defaults['device'] = device_defaults
                config['defaults'] = defaults
                
                logger.info("✅ 已启用新设备的默认自动接受共享文件夹")
                return self.set_config(config, async_mode=False)
            
            return True
        except Exception as e:
            logger.error(f"启用默认自动接受失败: {e}")
            return False

    def configure_listen_address(self):
        """配置监听地址，确保监听所有网络接口（Syncthing v2.0+）"""
        try:
            config = self.get_config()
            if not config:
                logger.warning("无法获取配置，跳过配置监听地址")
                return False
            
            options = config.get('options', {})
            listen_addresses = options.get('listenAddresses', [])
            default_address = "tcp://0.0.0.0:22000"
            
            if default_address not in listen_addresses:
                if not listen_addresses:
                    listen_addresses = [default_address]
                elif listen_addresses[0] != default_address:
                    listen_addresses.insert(0, default_address)
                options['listenAddresses'] = listen_addresses
                config['options'] = options
                result = self.set_config(config, async_mode=False)
                if result:
                    logger.info(f"✅ 已配置监听地址: {default_address}")
                    return True
                else:
                    logger.warning("配置监听地址失败")
                    return False
            else:
                logger.info(f"✅ 监听地址已配置: {listen_addresses}")
                return True
        except Exception as e:
            logger.error(f"配置监听地址失败: {e}")
            return False
