"""
Easytier管理模块
负责Easytier的启动和设备发现
"""
import json
import time
import subprocess
import sys
import os
from pathlib import Path
from utils.logger import Logger
from utils.process_helper import ProcessHelper
from config import Config, RESOURCE_DIR

logger = Logger().get_logger("EasytierManager")

class EasytierManager:
    """Easytier管理器"""
    
    def __init__(self):
        self.process = None
        self.virtual_ip = None
        self.peer_ips = []
        # 流量统计数据
        self.last_tx_bytes = 0
        self.last_rx_bytes = 0
        self.last_update_time = 0
    
    def start(self, custom_peers=None, network_name=None, network_secret=None):
        """启动Easytier虚拟网络
        
        Args:
            custom_peers: 自定义节点列表，如果为None则使用默认公共节点，如果为[]则不使用任何节点
            network_name: 网络名称，如果为None则使用配置文件中的名称
            network_secret: 网络密码，如果为None则使用配置文件中的密码
        """
        if not Config.EASYTIER_BIN.exists():
            raise FileNotFoundError(f"Easytier程序不存在: {Config.EASYTIER_BIN}")
        
        # 启动前先清理可能残留的进程
        logger.info("清理可能残留的 easytier 进程...")
        self.stop()  # 这会清理所有 easytier-core.exe 进程
        
        # 清理可能占用端口的进程（端口 11010 是 easytier 默认监听端口）
        # 注意：这只会清理 easytier 相关的进程，不会清理其他程序的进程
        logger.info("检查端口占用情况...")
        import psutil
        ports_to_check = [11010, 11011, 11012, 15888]  # easytier 常用的端口
        for port in ports_to_check:
            try:
                for conn in psutil.net_connections(kind='inet'):
                    try:
                        if conn.laddr and conn.laddr.port == port:
                            proc = psutil.Process(conn.pid)
                            proc_name = proc.name().lower()
                            # 只清理 easytier 相关的进程
                            if 'easytier' in proc_name:
                                logger.info(f"发现占用端口 {port} 的 easytier 进程: {proc_name} (PID: {conn.pid})，正在清理...")
                                proc.kill()
                                proc.wait(timeout=3)
                                logger.info(f"已清理占用端口 {port} 的进程")
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                    except Exception as e:
                        logger.debug(f"检查端口 {port} 时出错: {e}")
            except Exception as e:
                logger.debug(f"扫描端口 {port} 失败: {e}")
        
        time.sleep(1)  # 等待端口释放
        
        # 使用传入的参数或默认配置
        net_name = network_name if network_name else Config.EASYTIER_NETWORK_NAME
        net_secret = network_secret if network_secret else Config.EASYTIER_NETWORK_SECRET
        
        # 处理节点列表
        if custom_peers is None:
            # None 表示使用默认公共节点
            peers_to_use = Config.EASYTIER_PUBLIC_PEERS
        elif custom_peers == []:
            # 空列表表示不使用任何节点
            peers_to_use = []
        else:
            peers_to_use = custom_peers
        
        # 清理节点地址（移除末尾的分号、逗号等）
        if isinstance(peers_to_use, list):
            cleaned_peers = []
            for peer in peers_to_use:
                if isinstance(peer, str):
                    # 只移除末尾的分号和空格，保留中间的分号（因为可能是 tcp://...;udp://... 格式）
                    cleaned = peer.strip().rstrip(';').strip()
                    if cleaned:
                        cleaned_peers.append(cleaned)
            peers_to_use = cleaned_peers
            logger.info(f"清理后的节点列表: {peers_to_use}")
        
        # 使用固定的TUN设备名称（基于主机名，避免每次创建新设备）
        tun_device_name = f"easytier-{Config.HOSTNAME}"
        
        args = [
            "--rpc-portal", "127.0.0.1:15888",  # 显式指定 RPC 端口，供 easytier-cli 连接
            "--no-listener",  # 不监听任何端口，只连接到对等节点（客户端模式，避免端口占用问题）
            "-d",  # daemon 模式，后台运行
            "--network-name", net_name,
            "--network-secret", net_secret,
            "--dev-name", tun_device_name  # 固定TUN设备名称
        ]
        
        # 添加节点
        if isinstance(peers_to_use, str):
            # 如果是单个字符串，支持分号和逗号分割（先按分号分割，再按逗号分割）
            peers_list = []
            # 先按分号分割
            for part in peers_to_use.split(';'):
                part = part.strip()
                if part:
                    # 再按逗号分割
                    peers_list.extend([p.strip() for p in part.split(',') if p.strip()])
        else:
            # 如果是列表，也需要处理每个元素中可能包含的分号
            peers_list = []
            for peer in (peers_to_use if peers_to_use else []):
                if isinstance(peer, str):
                    # 按分号分割每个节点地址
                    for part in peer.split(';'):
                        part = part.strip()
                        if part:
                            # 再按逗号分割
                            peers_list.extend([p.strip() for p in part.split(',') if p.strip()])
                else:
                    peers_list.append(peer)
        
        # 确保每个节点都是独立的参数（避免在PowerShell中被误解析）
        for peer in peers_list:
            if peer.strip():  # 跳过空字符串
                args.extend(["-p", peer.strip()])
        
        if peers_list:
            logger.info(f"启动Easytier虚拟网络（客户端模式，使用节点：{len(peers_list)}个，TUN设备：{tun_device_name}）...")
            logger.info(f"节点列表: {peers_list}")  # 使用 INFO 级别，确保显示
        else:
            logger.info(f"启动Easytier虚拟网络（客户端模式，不使用节点，局域网模式，TUN设备：{tun_device_name}）...")
        
        # 输出完整的启动命令（用于调试）
        full_cmd = f"{Config.EASYTIER_BIN} {' '.join(args)}"
        logger.info(f"完整启动命令: {full_cmd}")
        logger.debug(f"完整启动参数: {' '.join(args)}")
        
        # 配置 DLL 搜索路径并检查依赖
        dll_dir = RESOURCE_DIR / "easytier"
        try:
            if dll_dir.exists():
                if sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
                    os.add_dll_directory(str(dll_dir))
                    logger.info(f"添加 DLL 搜索目录: {dll_dir}")
                else:
                    os.environ['PATH'] = f"{str(dll_dir)};" + os.environ.get('PATH', '')
                    logger.info(f"将 DLL 目录加入 PATH: {dll_dir}")
            missing = []
            for name in ["wintun.dll", "Packet.dll"]:
                p = dll_dir / name
                if not p.exists():
                    missing.append(str(p))
            if missing:
                raise FileNotFoundError(f"缺少依赖 DLL: {', '.join(missing)}")
        except Exception as e:
            raise FileNotFoundError(f"配置 DLL 依赖失败: {e}")
        
        # 启动进程（TUN模式需要管理员权限）
        logger.info("ℹ️ TUN模式需要管理员权限来创建虚拟网卡...")
        logger.info("ℹ️ 使用客户端模式（--no-listener），不会监听端口，避免端口占用问题...")
        
        # 设置工作目录为 easytier 所在目录
        working_dir = str(dll_dir)
        logger.info(f"设置工作目录: {working_dir}")
        
        self.process = ProcessHelper.start_process(
            Config.EASYTIER_BIN,
            args=args,
            hide_window=False,  # 不隐藏窗口，让输出显示在控制台，方便调试
            require_admin=True,  # TUN模式需要管理员权限
            working_dir=working_dir  # 设置工作目录
        )
        
        # 检查进程是否成功启动
        if self.process is None:
            logger.error("无法启动 easytier-core.exe 进程，请检查是否已授予管理员权限")
            return False
        
        # 验证进程是否在运行
        if not ProcessHelper.is_process_running(self.process):
            logger.error("easytier-core.exe 进程启动后立即退出")
            logger.error("可能的原因：")
            logger.error("  1. 端口被占用（如 11010、11011、11012）- 请检查是否有其他程序占用这些端口")
            logger.error("  2. 权限不足 - 请确保以管理员权限运行")
            logger.error("  3. 缺少依赖文件（如 wintun.dll）- 请检查 resources 目录")
            logger.error("  4. 配置错误 - 请检查网络名称和密码")
            logger.error("  5. 节点地址无效或无法连接 - 请检查节点地址格式")
            logger.error("  6. 参数格式错误 - 请检查启动命令")
            
            # 检查端口占用情况
            ports_to_check = [11010, 11011, 11012]
            import psutil
            for port in ports_to_check:
                try:
                    for conn in psutil.net_connections(kind='inet'):
                        try:
                            if conn.laddr and conn.laddr.port == port:
                                proc = psutil.Process(conn.pid)
                                proc_name = proc.name()
                                logger.error(f"  端口 {port} 被进程占用: {proc_name} (PID: {conn.pid})")
                        except:
                            pass
                except:
                    pass
            
            self.process = None
            return False
        
        logger.info(f"easytier-core.exe 进程已启动 (PID: {self.process.pid})")
        
        # 等待RPC服务就绪（使用默认端口 15888）
        logger.info("等待 RPC 服务就绪...")
        rpc_port = 15888  # easytier 默认 RPC 端口
        rpc_ready = ProcessHelper.wait_for_port(rpc_port, timeout=20)  # 增加超时时间
        
        if not rpc_ready:
            logger.error(f"RPC 服务启动失败，无法连接到端口 {rpc_port}")
            # 检查进程是否仍在运行
            if ProcessHelper.is_process_running(self.process):
                logger.warning("进程仍在运行，但 RPC 服务未就绪，可能是配置问题")
            else:
                logger.error("进程已退出，请检查错误信息")
            self.stop()
            return False
        
        logger.info("RPC 服务已就绪，等待虚拟IP分配...")
        
        # 等待虚拟网络初始化并分配IP
        max_retries = 10
        for i in range(max_retries):
            # 每次检查前先验证进程是否还在运行
            if not ProcessHelper.is_process_running(self.process):
                logger.error(f"easytier-core.exe 进程意外退出（在第{i+1}次检查时）")
                self.process = None
                return False
            
            time.sleep(2)
            self.virtual_ip = self._get_virtual_ip()
            if self.virtual_ip and self.virtual_ip not in ["waiting...", "unknown"]:
                logger.info(f"虚拟IP分配成功: {self.virtual_ip}")
                break
            logger.info(f"第{i+1}/{max_retries}次尝试，当前状态: {self.virtual_ip}")
        
        # 检查虚拟IP是否分配成功
        if self.virtual_ip in ["waiting...", "unknown", None]:
            logger.error(f"虚拟IP分配失败，当前状态: {self.virtual_ip}")
            # 停止进程
            self.stop()
            return False
        
        logger.info(f"Easytier启动成功，虚拟IP: {self.virtual_ip}")
        
        return True
    
    def stop(self):
        """停止Easytier服务"""
        import psutil
        
        # 先尝试正常停止进程
        if self.process:
            ProcessHelper.kill_process(self.process)
            self.process = None
        
        # 强制清理所有 easytier-core.exe 进程（防止残留）
        killed_count = 0
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and 'easytier-core' in proc.info['name'].lower():
                        logger.info(f"清理残留进程: {proc.info['name']} (PID: {proc.info['pid']})")
                        proc.kill()
                        proc.wait(timeout=3)
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning(f"清理进程失败: {e}")
        
        if killed_count > 0:
            logger.info(f"Easytier已停止，清理了 {killed_count} 个残留进程")
        else:
            logger.info("Easytier已停止")
    
    def _get_virtual_ip(self):
        """获取本机虚拟IP（通过easytier-cli查询）"""
        try:
            # 通过 easytier-cli peer 命令查看本机信息
            if not Config.EASYTIER_CLI.exists():
                logger.warning(f"easytier-cli 不存在: {Config.EASYTIER_CLI}")
                return "unknown"
            
            # 需要隐藏窗口的startupinfo
            startupinfo = None
            creationflags = 0
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = 0x08000000  # CREATE_NO_WINDOW
            
            result = subprocess.run(
                [str(Config.EASYTIER_CLI), "peer"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            if result.returncode != 0:
                logger.warning(f"easytier-cli peer 执行失败: {result.stderr}")
                logger.debug(f"stderr 内容: {result.stderr}")
                return "unknown"
            
            # 输出原始数据用于调试
            logger.debug(f"peer 命令输出:\n{result.stdout}")
            
            # 解析输出，找到标记为 Local 的行，其中有本机IP
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                logger.debug(f"第{i+1}行: {line}")
                if 'Local' in line and '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    logger.info(f"Local行分割结果 ({len(parts)}列): {parts}")
                    
                    # 尝试从所有列中查找IPv4地址（排除IPv6）
                    for idx, part in enumerate(parts):
                        # IPv4特征：包含点、包含斜杠、不包含冒号、有3个点
                        if (part and 
                            '.' in part and 
                            '/' in part and 
                            ':' not in part and  # 排除IPv6
                            part.count('.') == 3):  # IPv4必须有3个点
                            # 找到了IPv4地址
                            clean_ip = part.split('/')[0]
                            logger.info(f"在第{idx+1}列找到虚拟IP: {clean_ip}")
                            return clean_ip
            
            # 如果没有找到，说明还没分配IP
            logger.info("尚未分配虚拟IP，等待DHCP...")
            return "waiting..."
            
        except Exception as e:
            logger.warning(f"获取虚拟IP失败: {e}")
            return "unknown"
    
    def discover_peers(self, timeout=10):
        """
        发现局域网内的对等设备（通过 easytier-cli peer 命令）
        
        Returns:
            list: 对等设备信息列表
        """
        try:
            # 调用 easytier-cli peer 获取peer列表
            if not Config.EASYTIER_CLI.exists():
                logger.warning(f"easytier-cli 不存在: {Config.EASYTIER_CLI}")
                return []
            
            # 需要隐藏窗口的startupinfo
            startupinfo = None
            creationflags = 0
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = 0x08000000  # CREATE_NO_WINDOW
            
            result = subprocess.run(
                [str(Config.EASYTIER_CLI), "peer"],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            if result.returncode != 0:
                logger.warning(f"easytier-cli peer 执行失败: {result.stderr}")
                return []
            
            # 解析输出
            peers = self._parse_peer_output(result.stdout)
            
            self.peer_ips = [peer['ipv4'] for peer in peers if 'ipv4' in peer]
            
            return peers
            
        except subprocess.TimeoutExpired:
            logger.warning("获取peer信息超时")
            return []
        except Exception as e:
            logger.error(f"发现设备失败: {e}")
            return []
    
    def _parse_peer_output(self, output):
        """
        解析 easytier-cli peer 的输出
        
        Args:
            output: 命令输出文本
        
        Returns:
            list: peer信息列表
        """
        peers = []
        lines = output.strip().split('\n')
        
        # 查找表格数据行（跳过表头和分隔符）
        in_data = False
        for i, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            # 跳过空行
            if not line:
                continue
            
            # 识别表头
            if 'ipv4' in line.lower() and 'hostname' in line.lower():
                in_data = True
                continue
            
            # 跳过分隔符行
            if line.startswith('---') or line.startswith('===') or set(line.replace('|', '').strip()) == {'-'}:
                continue
            
            # 解析数据行（必须包含 | 分隔符）
            if in_data and '|' in line:
                parts = [p.strip() for p in original_line.split('|')]
                
                # 至少要有足够的列
                if len(parts) >= 3:
                    ipv4 = parts[1].strip() if len(parts) > 1 else ''  # 第2列是ipv4
                    hostname = parts[2].strip() if len(parts) > 2 else ''  # 第3列是hostname
                    cost = parts[3].strip() if len(parts) > 3 else ''  # 第4列是cost(Local/p2p)
                    latency = parts[4].strip() if len(parts) > 4 else '0'  # 第5列是latency
                    
                    # 只显示有虚拟 IP 的设备：
                    # 1. 必须有虚拟 IP（ipv4 不为空且包含点）
                    # 2. 排除中转节点（中转节点没有虚拟 IP）
                    # 3. 包含本机（显示自己的虚拟 IP）
                    if (ipv4 and 
                        '.' in ipv4 and 
                        hostname):
                        # 去掉子网掩码
                        ipv4_clean = ipv4.split('/')[0] if '/' in ipv4 else ipv4
                        
                        peer_info = {
                            'ipv4': ipv4_clean,
                            'hostname': hostname,
                            'latency': latency if cost != 'Local' else '-',  # 本机延迟显示为 -
                            'connected': True,
                            'is_local': cost == 'Local'  # 标记是否是本机
                        }
                        peers.append(peer_info)
                        logger.debug(f"解析到设备: {peer_info}")
        
        return peers
    
    def get_traffic_stats(self):
        """
        获取流量统计信息（通过 easytier-cli stats 命令）
        
        Returns:
            dict: 流量统计信息
                {
                    'tx_bytes': 上传字节数,
                    'rx_bytes': 下载字节数,
                    'tx_speed': 上传速度(bytes/s),
                    'rx_speed': 下载速度(bytes/s)
                }
        """
        try:
            # 调用 easytier-cli stats 获取流量统计
            if not Config.EASYTIER_CLI.exists():
                logger.warning(f"easytier-cli 不存在: {Config.EASYTIER_CLI}")
                return {
                    'tx_bytes': 0,
                    'rx_bytes': 0,
                    'tx_speed': 0,
                    'rx_speed': 0
                }
            
            # 需要隐藏窗口的startupinfo
            startupinfo = None
            creationflags = 0
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = 0x08000000  # CREATE_NO_WINDOW
            
            result = subprocess.run(
                [str(Config.EASYTIER_CLI), "stats"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            if result.returncode != 0:
                logger.warning(f"easytier-cli stats 执行失败: {result.stderr}")
                return {
                    'tx_bytes': 0,
                    'rx_bytes': 0,
                    'tx_speed': 0,
                    'rx_speed': 0
                }
            
            # 解析输出
            stats = self._parse_traffic_stats(result.stdout)
            
            # 计算速度
            current_time = time.time()
            
            tx_speed = 0
            rx_speed = 0
            
            if self.last_update_time > 0:
                time_delta = current_time - self.last_update_time
                if time_delta > 0:
                    tx_speed = (stats['tx_bytes'] - self.last_tx_bytes) / time_delta
                    rx_speed = (stats['rx_bytes'] - self.last_rx_bytes) / time_delta
                else:
                    # 时间差为0，使用上次的速度
                    tx_speed = 0
                    rx_speed = 0
            else:
                # 第一次调用，初始化数据
                logger.debug(f"首次获取流量统计: tx_bytes={stats['tx_bytes']}, rx_bytes={stats['rx_bytes']}")
            
            # 更新历史数据
            self.last_tx_bytes = stats['tx_bytes']
            self.last_rx_bytes = stats['rx_bytes']
            self.last_update_time = current_time
            
            stats['tx_speed'] = max(0, tx_speed)  # 确保速度非负
            stats['rx_speed'] = max(0, rx_speed)
            
            logger.debug(f"流量统计: tx_bytes={stats['tx_bytes']}, rx_bytes={stats['rx_bytes']}, tx_speed={stats['tx_speed']:.2f} B/s, rx_speed={stats['rx_speed']:.2f} B/s")
            
            return stats
            
        except subprocess.TimeoutExpired:
            logger.warning("获取流量统计超时")
            return {
                'tx_bytes': 0,
                'rx_bytes': 0,
                'tx_speed': 0,
                'rx_speed': 0
            }
        except Exception as e:
            logger.error(f"获取流量统计失败: {e}")
            return {
                'tx_bytes': 0,
                'rx_bytes': 0,
                'tx_speed': 0,
                'rx_speed': 0
            }
    
    def _parse_traffic_stats(self, output):
        """
        解析 easytier-cli stats 的输出，提取流量统计信息
        
        Args:
            output: 命令输出文本
        
        Returns:
            dict: {'tx_bytes': int, 'rx_bytes': int}
        """
        tx_bytes = 0
        rx_bytes = 0
        
        try:
            # 输出完整的原始数据用于调试
            logger.debug(f"easytier-cli stats 原始输出:\n{output}")
            
            lines = output.strip().split('\n')
            
            # 查找 traffic_bytes_self_tx 和 traffic_bytes_self_rx
            for line in lines:
                line = line.strip()
                
                # 跳过空行
                if not line or '|' not in line:
                    continue
                
                # 解析数据行
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    metric_name = parts[1] if len(parts) > 1 else ''
                    value_str = parts[2] if len(parts) > 2 else ''
                    
                    # 查找 traffic_bytes_self_tx（上传）
                    if 'traffic_bytes_self_tx' in metric_name:
                        # 解析值，如 "36.66 KiB" → 字节数
                        tx_bytes = self._parse_size_value(value_str)
                        logger.debug(f"找到上传流量: {value_str} -> {tx_bytes} bytes")
                    
                    # 查找 traffic_bytes_self_rx（下载）
                    elif 'traffic_bytes_self_rx' in metric_name:
                        rx_bytes = self._parse_size_value(value_str)
                        logger.debug(f"找到下载流量: {value_str} -> {rx_bytes} bytes")
            
            # 只在流量大于0时才打印INFO日志，避免频繁输出0流量
            # if tx_bytes > 0 or rx_bytes > 0:
            #     logger.info(f"解析流量统计: TX={tx_bytes} bytes ({self._format_bytes(tx_bytes)}), RX={rx_bytes} bytes ({self._format_bytes(rx_bytes)})")
            # else:
            #     logger.debug(f"解析流量统计: TX={tx_bytes} bytes, RX={rx_bytes} bytes")
            pass  # 已禁用流量统计日志
            
        except Exception as e:
            logger.warning(f"解析流量统计失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return {
            'tx_bytes': tx_bytes,
            'rx_bytes': rx_bytes
        }
    
    def _parse_size_value(self, value_str):
        """
        解析大小值字符串（如 "36.66 KiB"）为字节数
        """
        try:
            value_str = value_str.strip()
            if not value_str or value_str == '-':
                return 0
            
            # 分离数字和单位
            parts = value_str.split()
            if len(parts) < 2:
                # 没有单位，尝试直接转换为数字
                return int(float(value_str))
            
            number = float(parts[0])
            unit = parts[1].upper()
            
            # 转换为字节
            if 'KIB' in unit or 'KB' in unit:
                return int(number * 1024)
            elif 'MIB' in unit or 'MB' in unit:
                return int(number * 1024 * 1024)
            elif 'GIB' in unit or 'GB' in unit:
                return int(number * 1024 * 1024 * 1024)
            elif 'B' in unit:
                return int(number)
            else:
                return int(number)
        except Exception as e:
            logger.debug(f"解析大小值失败 '{value_str}': {e}")
            return 0
    
    def _format_bytes(self, bytes_value):
        """格式化字节数为可读格式"""
        if bytes_value < 1024:
            return f"{bytes_value} B"
        elif bytes_value < 1024 * 1024:
            return f"{bytes_value / 1024:.2f} KB"
        elif bytes_value < 1024 * 1024 * 1024:
            return f"{bytes_value / 1024 / 1024:.2f} MB"
        else:
            return f"{bytes_value / 1024 / 1024 / 1024:.2f} GB"