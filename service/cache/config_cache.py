"""
配置缓存管理
保存和加载用户配置
"""
import json
import time
import threading
from pathlib import Path
from utils.logger import Logger
from config import Config

logger = Logger().get_logger("ConfigCache")

class ConfigCache:
    """配置缓存管理器"""
    
    CACHE_FILE = Config.CONFIG_DIR / "user_config.json"
    
    @classmethod
    def save(cls, config_data):
        """
        保存配置
        
        Args:
            config_data: 配置字典
        """
        try:
            Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            with open(cls.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    @classmethod
    def load(cls):
        """
        加载配置
        
        Returns:
            dict: 配置字典，如果不存在返回默认值
        """
        try:
            if cls.CACHE_FILE.exists():
                with open(cls.CACHE_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 兼容旧版本配置：如果没有network字段，但有顶层的room_name/password
                if 'network' not in config and ('room_name' in config or 'password' in config):
                    config['network'] = {
                        'room_name': config.pop('room_name', ''),
                        'password': config.pop('password', '')
                    }
                    # 保存迁移后的配置
                    cls.save(config)
                    logger.info("已迁移旧版本配置到network字段")
                
                # 确保network字段存在
                if 'network' not in config:
                    config['network'] = {
                        'room_name': '',
                        'password': ''
                    }
                
                # 确保easytier_nodes字段存在
                if 'easytier_nodes' not in config:
                    config['easytier_nodes'] = []
                
                logger.info("配置已加载")
                return config
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
        
        # 返回默认配置
        return {
            "room_name": "langamesync-network",
            "password": "langamesync-2025",
            "last_folders": [],
            "easytier_nodes": []
        }

    @classmethod
    def get_easytier_nodes(cls):
        """
        获取Easytier节点列表
        
        Returns:
            list: 节点列表
        """
        config = cls.load()
        return config.get('easytier_nodes', [])
    
    @classmethod
    def save_easytier_nodes(cls, nodes):
        """
        保存Easytier节点列表
        
        Args:
            nodes: 节点列表
        """
        config = cls.load()
        config['easytier_nodes'] = nodes
        cls.save(config)
        logger.info(f"已保存 {len(nodes)} 个Easytier节点")
    
    @classmethod
    def add_easytier_node(cls, node):
        """
        添加Easytier节点
        
        Args:
            node: 节点地址
        """
        nodes = cls.get_easytier_nodes()
        if node not in nodes:
            nodes.append(node)
            cls.save_easytier_nodes(nodes)
            logger.info(f"已添加节点: {node}")
            return True
        else:
            logger.warning(f"节点已存在: {node}")
            return False
    
    @classmethod
    def remove_easytier_node(cls, node):
        """
        删除Easytier节点
        
        Args:
            node: 节点地址
        """
        nodes = cls.get_easytier_nodes()
        if node in nodes:
            nodes.remove(node)
            cls.save_easytier_nodes(nodes)
            logger.info(f"已删除节点: {node}")
            return True
        else:
            logger.warning(f"节点不存在: {node}")
            return False
    
    @classmethod
    def get_selected_node(cls):
        """
        获取当前选中的节点
        
        Returns:
            str: 节点地址，如果没有选中返回None
        """
        config = cls.load()
        return config.get('selected_node', None)
    
    @classmethod
    def set_selected_node(cls, node):
        """
        设置当前选中的节点
        
        Args:
            node: 节点地址，如果为None则清除选择
        """
        config = cls.load()
        if node is None:
            config.pop('selected_node', None)
        else:
            config['selected_node'] = node
        cls.save(config)
        logger.info(f"已设置选中节点: {node}")

class CacheManager:
    """通用缓存管理器"""
    
    def __init__(self, cache_dir=None, default_ttl=3600):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
            default_ttl: 默认缓存有效期（秒）
        """
        self.cache_dir = cache_dir or Config.CACHE_DIR
        self.default_ttl = default_ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._in_memory_cache = {}
        self._cache_locks = {}
        logger.info(f"缓存管理器初始化完成: 缓存目录={self.cache_dir}, 默认TTL={default_ttl}秒")
    
    def get_cache_file_path(self, cache_key):
        """
        获取缓存文件路径
        
        Args:
            cache_key: 缓存键
            
        Returns:
            Path: 缓存文件路径
        """
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, cache_key, ttl=None):
        """
        获取缓存数据
        
        Args:
            cache_key: 缓存键
            ttl: 缓存有效期（秒），如果为None则使用默认值
            
        Returns:
            缓存数据，如果缓存不存在或已过期返回None
        """
        ttl = ttl or self.default_ttl
        
        # 先检查内存缓存
        if cache_key in self._in_memory_cache:
            cache_data = self._in_memory_cache[cache_key]
            if time.time() - cache_data['timestamp'] < ttl:
                logger.debug(f"从内存缓存获取: {cache_key}")
                return cache_data['data']
            else:
                logger.debug(f"内存缓存已过期: {cache_key}")
                del self._in_memory_cache[cache_key]
        
        # 检查文件缓存
        cache_file = self.get_cache_file_path(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                if time.time() - cache_data['timestamp'] < ttl:
                    logger.debug(f"从文件缓存获取: {cache_key}")
                    # 更新内存缓存
                    self._in_memory_cache[cache_key] = cache_data
                    return cache_data['data']
                else:
                    logger.debug(f"文件缓存已过期: {cache_key}")
                    # 删除过期缓存文件
                    cache_file.unlink()
            except Exception as e:
                logger.error(f"读取缓存文件失败: {e}")
        
        return None
    
    def set(self, cache_key, data, ttl=None):
        """
        设置缓存数据
        
        Args:
            cache_key: 缓存键
            data: 缓存数据
            ttl: 缓存有效期（秒），如果为None则使用默认值
        """
        ttl = ttl or self.default_ttl
        cache_data = {
            'timestamp': time.time(),
            'ttl': ttl,
            'data': data
        }
        
        # 更新内存缓存
        self._in_memory_cache[cache_key] = cache_data
        
        # 保存到文件缓存
        cache_file = self.get_cache_file_path(cache_key)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"缓存已保存: {cache_key}")
        except Exception as e:
            logger.error(f"保存缓存文件失败: {e}")
    
    def delete(self, cache_key):
        """
        删除缓存数据
        
        Args:
            cache_key: 缓存键
        """
        # 删除内存缓存
        if cache_key in self._in_memory_cache:
            del self._in_memory_cache[cache_key]
            logger.debug(f"内存缓存已删除: {cache_key}")
        
        # 删除文件缓存
        cache_file = self.get_cache_file_path(cache_key)
        if cache_file.exists():
            cache_file.unlink()
            logger.debug(f"文件缓存已删除: {cache_key}")
    
    def clear(self):
        """
        清除所有缓存
        """
        # 清除内存缓存
        self._in_memory_cache.clear()
        logger.info("内存缓存已清除")
        
        # 清除文件缓存
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        logger.info("文件缓存已清除")
    
    def get_lock(self, lock_key):
        """
        获取缓存锁
        
        Args:
            lock_key: 锁键
            
        Returns:
            threading.Lock: 锁对象
        """
        if lock_key not in self._cache_locks:
            self._cache_locks[lock_key] = threading.Lock()
        return self._cache_locks[lock_key]

# 全局缓存管理器实例
cache_manager = CacheManager()