"""
联机房间管理器
管理房间的创建、状态和销毁
"""
import threading
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path
from utils.logger import Logger

logger = Logger().get_logger("RoomManager")


@dataclass
class Room:
    """联机房间数据类"""
    room_id: str                           # 房间唯一ID
    name: str                              # 房间名称
    save_name: str                         # 存档名称
    port: int                              # 开放端口
    password: Optional[str] = None         # 房间密码（可选）
    host_player: str = ""                  # 房主玩家名
    game_mode: str = "survival"            # 游戏模式
    status: str = "creating"               # 房间状态: creating, waiting, publishing, open, closed, error
    created_at: datetime = field(default_factory=datetime.now)
    players: List[str] = field(default_factory=list)  # 已加入玩家列表
    max_players: int = 8                   # 最大玩家数
    process_pid: Optional[int] = None      # 游戏进程PID
    error_message: str = ""                # 错误信息
    virtual_ip: str = ""                   # 虚拟IP地址
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'room_id': self.room_id,
            'name': self.name,
            'save_name': self.save_name,
            'port': self.port,
            'has_password': bool(self.password),
            'host_player': self.host_player,
            'game_mode': self.game_mode,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'players': self.players,
            'player_count': len(self.players),
            'max_players': self.max_players,
            'error_message': self.error_message,
            'virtual_ip': self.virtual_ip
        }
    
    def verify_password(self, password: str) -> bool:
        """验证密码"""
        if not self.password:
            return True
        return self.password == password


class RoomManager:
    """房间管理器单例"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.rooms: Dict[str, Room] = {}          # 本地房间
        self.remote_rooms: Dict[str, Room] = {}   # 远程房间
        self.current_room: Optional[Room] = None  # 当前本机创建的房间
        self._process_monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = False
        self._initialized = True
        logger.info("RoomManager 初始化完成")
    
    def add_remote_room(self, room_data: dict):
        """添加或更新远程房间"""
        try:
            room_id = room_data.get('room_id')
            if not room_id:
                return
            
            # 如果是本机房间，忽略
            if room_id in self.rooms:
                return
                
            # 解析时间字符串或使用当前时间
            created_at = datetime.now()
            
            room = Room(
                room_id=room_id,
                name=room_data.get('name', 'Unknown'),
                save_name=room_data.get('save_name', ''),
                port=room_data.get('port', 25565),
                password=room_data.get('password', None) if room_data.get('has_password') else None, # 注意：密码通常不传输，这里只标记是否有密码
                host_player=room_data.get('host_player', 'Unknown'),
                game_mode=room_data.get('game_mode', 'survival'),
                status=room_data.get('status', 'open'),
                created_at=created_at,
                max_players=room_data.get('max_players', 8),
                virtual_ip=room_data.get('virtual_ip', ''),
                players=room_data.get('players', []) # 远程房间可能带玩家列表
            )
            
            # 标记是否有密码（因为我们没有真实密码）
            if room_data.get('has_password'):
                room.password = "******" 
            
            self.remote_rooms[room_id] = room
            logger.info(f"🌐 发现远程房间: {room.name} ({room.host_player})")
            
        except Exception as e:
            logger.error(f"添加远程房间失败: {e}")

    def remove_remote_room(self, room_id: str):
        """移除远程房间"""
        if room_id in self.remote_rooms:
            del self.remote_rooms[room_id]
            logger.info(f"🌐 远程房间已移除: {room_id}")

    def cleanup_offline_rooms(self, active_peer_ips: List[str]):
        """
        清理离线节点的房间
        
        Args:
            active_peer_ips: 当前活跃的节点虚拟IP列表
        """
        if not active_peer_ips:
            # 如果没有活跃节点，清空所有远程房间
            if self.remote_rooms:
                logger.info(f"🌐 没有活跃节点，清空所有远程房间 ({len(self.remote_rooms)}个)")
                self.remote_rooms.clear()
            return

        # 找出需要移除的房间
        rooms_to_remove = []
        for room_id, room in self.remote_rooms.items():
            # 如果房间的虚拟IP不在活跃节点列表中，则标记为移除
            # 注意：只比较IP部分，忽略端口
            if room.virtual_ip not in active_peer_ips:
                rooms_to_remove.append(room_id)
        
        # 执行移除
        for room_id in rooms_to_remove:
            room = self.remote_rooms.get(room_id)
            logger.info(f"🌐 节点 {room.virtual_ip} 已离线，移除其房间: {room.name}")
            self.remove_remote_room(room_id)

    def start_process_monitor(self, room_id: str, pid: int):
        """
        启动进程监控，当游戏进程退出时自动关闭房间
        
        Args:
            room_id: 房间ID
            pid: 游戏进程PID
        """
        self._stop_monitor = False
        
        def monitor_thread():
            import psutil
            
            logger.info(f"🔍 开始监控游戏进程 PID: {pid}")
            
            while not self._stop_monitor:
                try:
                    # 检查进程是否存在
                    if not psutil.pid_exists(pid):
                        logger.info(f"🎮 游戏进程 {pid} 已退出")
                        self._on_game_exit(room_id)
                        break
                    
                    # 检查进程状态
                    try:
                        proc = psutil.Process(pid)
                        if proc.status() == psutil.STATUS_ZOMBIE:
                            logger.info(f"🎮 游戏进程 {pid} 已变为僵尸进程")
                            self._on_game_exit(room_id)
                            break
                    except psutil.NoSuchProcess:
                        logger.info(f"🎮 游戏进程 {pid} 已不存在")
                        self._on_game_exit(room_id)
                        break
                    
                except Exception as e:
                    logger.error(f"监控进程失败: {e}")
                
                time.sleep(2)  # 每 2 秒检查一次
            
            logger.info(f"🔍 进程监控结束")
        
        self._process_monitor_thread = threading.Thread(target=monitor_thread, daemon=True)
        self._process_monitor_thread.start()
    
    def stop_process_monitor(self):
        """停止进程监控"""
        self._stop_monitor = True
    
    def _on_game_exit(self, room_id: str):
        """游戏退出时的回调"""
        room = self.rooms.get(room_id)
        if room and room.status not in ['closed', 'error']:
            logger.info(f"🚪 游戏已退出，自动关闭房间: {room.name}")
            self.close_room(room_id)
    
    def _generate_room_id(self, name: str) -> str:
        """生成唯一房间ID"""
        timestamp = str(time.time())
        hash_input = f"{name}_{timestamp}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:8]
    
    def create_room(
        self,
        name: str,
        save_name: str,
        port: int,
        host_player: str,
        password: Optional[str] = None,
        game_mode: str = "survival",
        max_players: int = 8,
        virtual_ip: str = ""
    ) -> Room:
        """
        创建新房间
        
        Args:
            name: 房间名称
            save_name: 存档名称
            port: 开放端口
            host_player: 房主玩家名
            password: 房间密码（可选）
            game_mode: 游戏模式
            max_players: 最大玩家数
            virtual_ip: 虚拟IP
            
        Returns:
            创建的房间对象
        """
        # 清理所有已关闭的房间
        closed_room_ids = [rid for rid, r in self.rooms.items() if r.status in ['closed', 'error']]
        for rid in closed_room_ids:
            del self.rooms[rid]
            
        # 如果已有活跃房间，先关闭
        if self.current_room and self.current_room.status not in ['closed', 'error']:
            logger.warning(f"关闭现有房间: {self.current_room.name}")
            self.close_room(self.current_room.room_id)
        
        room_id = self._generate_room_id(name)
        
        room = Room(
            room_id=room_id,
            name=name,
            save_name=save_name,
            port=port,
            password=password,
            host_player=host_player,
            game_mode=game_mode,
            max_players=max_players,
            virtual_ip=virtual_ip
        )
        
        self.rooms[room_id] = room
        self.current_room = room
        
        logger.info(f"✅ 创建房间: {name} (ID: {room_id}), 存档: {save_name}, 端口: {port}")
        return room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """获取指定房间"""
        return self.rooms.get(room_id)
    
    def get_current_room(self) -> Optional[Room]:
        """获取当前房间"""
        return self.current_room
    
    def update_room_status(self, room_id: str, status: str, error_message: str = ""):
        """更新房间状态"""
        room = self.rooms.get(room_id)
        if room:
            old_status = room.status
            room.status = status
            if error_message:
                room.error_message = error_message
            logger.info(f"📝 房间 {room.name} 状态更新: {old_status} -> {status} {f'(错误: {error_message})' if error_message else ''}")
    
    def set_room_process(self, room_id: str, pid: int):
        """设置房间游戏进程PID"""
        room = self.rooms.get(room_id)
        if room:
            room.process_pid = pid
            logger.info(f"房间 {room.name} 绑定进程 PID: {pid}")
    
    def close_room(self, room_id: str):
        """关闭房间"""
        room = self.rooms.get(room_id)
        if room:
            room.status = 'closed'
            logger.info(f"房间 {room.name} 已关闭")

            # 不再立即删除，保留记录以便查看状态
            # if room_id in self.rooms:
            #    del self.rooms[room_id]

            # 更新当前房间指针 (如果它是当前房间)
            if self.current_room and self.current_room.room_id == room_id:
                # 即使关闭了，current_room 仍然指向它，直到创建新房间或手动清除
                # self.current_room = None
                pass
    
    def get_all_rooms(self) -> List[dict]:
        """获取所有房间（包括本地和远程）"""
        all_rooms = []
        for room in self.rooms.values():
            # 返回所有本地房间，包括 closed/error
            d = room.to_dict()
            d['is_local'] = True
            all_rooms.append(d)
                
        for room in self.remote_rooms.values():
            # 远程房间只返回活跃的
            if room.status not in ['closed', 'error']:
                d = room.to_dict()
                d['is_local'] = False
                all_rooms.append(d)
            
        return all_rooms
    
    def get_open_rooms(self) -> List[dict]:
        """获取所有开放的房间"""
        return [room.to_dict() for room in self.rooms.values() if room.status == 'open']
    
    def add_player(self, room_id: str, player_name: str) -> bool:
        """添加玩家到房间"""
        room = self.rooms.get(room_id)
        if not room:
            return False
        
        if len(room.players) >= room.max_players:
            return False
        
        if player_name not in room.players:
            room.players.append(player_name)
            logger.info(f"玩家 {player_name} 加入房间 {room.name}")
        
        return True
    
    def remove_player(self, room_id: str, player_name: str):
        """从房间移除玩家"""
        room = self.rooms.get(room_id)
        if room and player_name in room.players:
            room.players.remove(player_name)
            logger.info(f"玩家 {player_name} 离开房间 {room.name}")


# 全局房间管理器实例
room_manager = RoomManager()

