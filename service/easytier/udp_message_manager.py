"""
UDP消息管理模块
在Easytier虚拟网络中与用户通信
用于房间创建、关闭等事件的实时通知
"""
import json
import socket
import threading
import time
from typing import Dict, Optional
from utils.logger import Logger
from service.minecraft.online_lobby.room_manager import Room

logger = Logger().get_logger("UDPMessageManager")


class UDPMessageManager:
    """UDP消息管理器"""
    
    def __init__(self, virtual_ip: str, udp_port: int = 53642):
        """
        初始化UDP消息管理器
        
        Args:
            virtual_ip: Easytier虚拟IP地址
            udp_port: UDP端口，默认53642
        """
        self.virtual_ip = virtual_ip
        self.udp_port = udp_port
        self.udp_socket = None
        self._running = False
        self._receive_thread: Optional[threading.Thread] = None
        self._broadcast_thread: Optional[threading.Thread] = None
        self._current_broadcast_room: Optional[Room] = None
        
    def start(self):
        """启动UDP消息服务"""
        try:
            # 创建UDP socket
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # 绑定到虚拟IP以确保发送时的源IP正确
            # 这样接收方看到的源IP就是EasyTier的虚拟IP
            logger.info(f"尝试绑定UDP端口: {self.virtual_ip}:{self.udp_port}")
            self.udp_socket.bind((self.virtual_ip, self.udp_port))
            self._running = True
            
            # 启动接收线程
            self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receive_thread.start()
            
            logger.info(f"✅ UDP消息服务已启动，监听端口: {self.udp_port} (所有接口)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 启动UDP消息服务失败: {e}")
            return False
        
    def stop(self):
        """停止UDP消息服务"""
        self._running = False
        
        # 1. 先将 socket 设为 None，让接收线程能感知到状态变化
        # 但为了防止线程阻塞在 recvfrom，我们先不把 self.udp_socket 设为 None，而是先 close
        sock = self.udp_socket
        self.udp_socket = None
        
        if sock:
            try:
                # 关闭 socket 会导致 recvfrom 抛出异常，从而唤醒线程
                sock.close()
                logger.info("🔧 已关闭UDP socket")
            except Exception as e:
                logger.warning(f"⚠️ 关闭UDP socket时出错: {e}")
        
        if self._receive_thread and self._receive_thread.is_alive():
            try:
                # 等待线程结束，超时时间短一点
                self._receive_thread.join(timeout=0.5)
            except Exception:
                pass
            
            self._receive_thread = None
        
        logger.info("🔧 UDP消息服务已停止")
    
    def start_periodic_broadcast(self, room: Room):
        """
        开始周期性广播房间信息
        
        Args:
            room: 要广播的房间对象
        """
        self._current_broadcast_room = room
        if self._broadcast_thread and self._broadcast_thread.is_alive():
            return

        self._broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._broadcast_thread.start()
        logger.info(f"📡 开始周期性广播房间: {room.name}")

    def stop_periodic_broadcast(self):
        """停止周期性广播"""
        self._current_broadcast_room = None
        # 线程会检查 _current_broadcast_room 为 None 时自动退出
        logger.info("📡 停止周期性广播")

    def is_broadcasting(self) -> bool:
        """是否正在进行周期性广播"""
        return self._broadcast_thread is not None and self._broadcast_thread.is_alive() and self._current_broadcast_room is not None

    def _broadcast_loop(self):
        """周期性广播循环"""
        while self._running and self._current_broadcast_room:
            try:
                # 广播房间信息
                self.broadcast_quick_join_info(self._current_broadcast_room)
                # 每 3 秒广播一次
                time.sleep(3)
            except Exception as e:
                logger.error(f"周期性广播失败: {e}")
                time.sleep(5)

    def broadcast_room_created(self, room: Room, target_ips: list = None):
        """
        广播房间创建消息
        
        Args:
            room: Room对象
            target_ips: 目标IP列表（可选，如果提供则会额外向这些IP发送单播消息）
        """
        message = self._create_message(
            event="ROOM_CREATED",
            room=room,
            message=f"房间 {room.name} 已创建，虚拟IP: {room.virtual_ip}:{room.port}"
        )
        self._broadcast_message(message)
        
        if target_ips:
            for ip in target_ips:
                if ip and ip != self.virtual_ip:
                    self._send_message(message, ip)
    
    def broadcast_room_closed(self, room: Room, target_ips: list = None):
        """
        广播房间关闭消息
        
        Args:
            room: Room对象
            target_ips: 目标IP列表
        """
        message = self._create_message(
            event="ROOM_CLOSED",
            room=room,
            message=f"房间 {room.name} 已关闭"
        )
        self._broadcast_message(message)
        
        if target_ips:
            for ip in target_ips:
                if ip and ip != self.virtual_ip:
                    self._send_message(message, ip)
    
    def broadcast_quick_join_info(self, room: Room, target_ips: list = None):
        """
        广播快速加入信息
        
        Args:
            room: Room对象
            target_ips: 目标IP列表
        """
        message = self._create_message(
            event="QUICK_JOIN_INFO",
            room=room,
            message=f"房间 {room.name} 快速加入信息"
        )
        self._broadcast_message(message)
        
        if target_ips:
            for ip in target_ips:
                if ip and ip != self.virtual_ip:
                    self._send_message(message, ip)
    
    def _create_message(self, event: str, room: Room, message: str) -> Dict:
        """
        创建消息对象
        
        Args:
            event: 事件类型: ROOM_CREATED, ROOM_CLOSED, QUICK_JOIN_INFO
            room: Room对象
            message: 消息内容
        
        Returns:
            JSON消息字典
        """
        # 生成Minecraft快速加入命令
        quick_join_cmd = f"--quickPlayMultiplayer \"{room.virtual_ip}:{room.port}\""
        
        return {
            "event": event,
            "timestamp": int(time.time()),
            "message": message,
            "room": {
                "room_id": room.room_id,
                "name": room.name,
                "save_name": room.save_name,
                "port": room.port,
                "has_password": bool(room.password),
                "host_player": room.host_player,
                "game_mode": room.game_mode,
                "status": room.status,
                "player_count": len(room.players),
                "max_players": room.max_players,
                "virtual_ip": room.virtual_ip,
                "quick_join_cmd": quick_join_cmd
            }
        }
    
    def _broadcast_message(self, message: Dict):
        """
        在Easytier虚拟网络中广播消息
        
        Args:
            message: 消息字典
        """
        if not self.udp_socket or not self._running:
            logger.warning("⚠️ UDP服务未运行，无法发送消息")
            return
        
        try:
            # 将字典转换为JSON
            json_message = json.dumps(message, ensure_ascii=False)
            data = json_message.encode('utf-8')
            
            # 1. 尝试计算子网广播地址 (假设 /24)
            # Easytier 虚拟 IP 通常是 10.126.126.x
            # 所以广播地址应该是 10.126.126.255
            if '.' in self.virtual_ip:
                ip_parts = self.virtual_ip.split('.')
                if len(ip_parts) >= 4:
                    # 创建广播地址
                    broadcast_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
                    try:
                        logger.info(f"📡 向虚拟网络广播消息: {message['event']} 到 {broadcast_ip}:{self.udp_port}")
                        self.udp_socket.sendto(data, (broadcast_ip, self.udp_port))
                    except Exception as e:
                        logger.warning(f"向 {broadcast_ip} 广播失败: {e}")
            
            # 2. 尝试全局广播地址 (作为补充)
            try:
                self.udp_socket.sendto(data, ('255.255.255.255', self.udp_port))
            except Exception as e:
                pass
                
            # 3. 尝试向已知对等节点单独发送 (Reliable Broadcast)
            if 'peers' in message:
                 # 避免递归或循环依赖，这里我们依赖外部传入 target_ips
                 pass

                
        except Exception as e:
            logger.error(f"广播消息失败: {e}")
    
    def _send_message(self, message: Dict, target_ip: str):
        """
        发送消息到指定IP
        
        Args:
            message: 消息字典
            target_ip: 目标IP地址
        """
        if not self.udp_socket or not self._running:
            logger.warning("⚠️ UDP服务未运行，无法发送消息")
            return
        
        try:
            # 将字典转换为JSON
            json_message = json.dumps(message, ensure_ascii=False)
            data = json_message.encode('utf-8')
            
            logger.info(f"📡 发送消息到: {target_ip}:{self.udp_port}")
            self.udp_socket.sendto(data, (target_ip, self.udp_port))
                
        except Exception as e:
            logger.error(f"❌ 发送消息失败: {e}")
    
    def _receive_loop(self):
        """
        UDP消息接收循环
        """
        logger.info(f"🔍 开始监听UDP消息: {self.virtual_ip}:{self.udp_port}")
        
        while self._running and self.udp_socket:
            try:
                # 接收数据，设置超时
                self.udp_socket.settimeout(0.5)
                data, addr = self.udp_socket.recvfrom(4096)
                
                if data:
                    self._handle_received_message(data, addr)
                    
            except socket.timeout:
                # 超时是正常的，继续循环
                continue
            except OSError as e:
                if e.winerror == 10038: # WSAENOTSOCK
                    # 套接字已关闭或无效，退出循环
                    logger.info("UDP socket已关闭，停止接收循环")
                    break
                elif e.winerror == 10054: # WSAECONNRESET
                    # 远程主机强迫关闭了一个现有的连接 (ICMP Port Unreachable)
                    # 这在 UDP 中通常意味着之前的发包目标不可达，可以忽略
                    continue
                logger.error(f"❌ 接收UDP消息时发生 OSError: {e}")
                # 避免死循环报错，稍微休眠
                time.sleep(1)
            except Exception as e:
                logger.error(f"❌ 接收UDP消息失败: {e}")
                # 避免死循环报错，稍微休眠
                time.sleep(1)
        
        logger.info("🔍 UDP消息监听已停止")
    
    def _handle_received_message(self, data: bytes, addr: tuple):
        """
        处理接收到的UDP消息
        
        Args:
            data: 接收到的数据
            addr: (ip, port) 元组
        """
        try:
            message = data.decode('utf-8')
            json_message = json.loads(message)
            
            sender_ip, sender_port = addr
            
            # 忽略自己发送的消息
            if sender_ip == self.virtual_ip:
                # logger.debug(f"忽略来自自己的消息: {sender_ip}")
                return
            
            # 也可以通过 message 内容中的 virtual_ip 来判断（如果消息里带了）
            msg_room = json_message.get('room', {})
            if msg_room and msg_room.get('virtual_ip') == self.virtual_ip:
                 # logger.debug(f"忽略来自自己的房间消息: {msg_room.get('virtual_ip')}")
                 return

            logger.info(f"📥 从 {sender_ip}:{sender_port} 收到UDP消息: {json_message}")
            
            # 可以在这里添加消息处理逻辑
            # 例如：如果是查询房间信息的消息，可以返回当前房间列表
            
            # 目前暂时只打印日志，后续可以扩展
            event = json_message.get('event', '')
            if event:
                logger.info(f"📥 处理消息事件: {event}")
                
                # 获取房间管理器
                from service.minecraft.online_lobby.room_manager import room_manager
                
                if event == "ROOM_CREATED" or event == "QUICK_JOIN_INFO":
                    room_data = json_message.get('room')
                    if room_data:
                        room_manager.add_remote_room(room_data)
                elif event == "ROOM_CLOSED":
                    room_data = json_message.get('room')
                    if room_data:
                        room_id = room_data.get('room_id')
                        if room_id:
                            room_manager.remove_remote_room(room_id)
                elif event == "REQUEST_ROOM_INFO":
                    # 收到房间信息请求，回复当前房间信息
                    current_room = room_manager.get_current_room()
                    if current_room and current_room.status == 'open':
                        logger.info(f"📥 收到来自 {sender_ip} 的房间信息请求，正在回复...")
                        self.broadcast_quick_join_info(current_room, [sender_ip])
            
        except json.JSONDecodeError:
            logger.error(f"❌ 无法解析UDP消息: {data}")
        except Exception as e:
            logger.error(f"❌ 处理UDP消息失败: {e}")

    def broadcast_request_room_info(self):
        """
        广播房间信息请求（用于刚加入网络时发现房间）
        """
        message = {
            "event": "REQUEST_ROOM_INFO",
            "timestamp": int(time.time()),
            "message": "请求获取当前房间信息"
        }
        self._broadcast_message(message)
