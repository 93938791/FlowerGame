"""
进程管理工具模块
"""
import subprocess
import sys
import time
import psutil
from utils.logger import Logger

logger = Logger().get_logger("ProcessHelper")

class ProcessHelper:
    """进程管理工具类"""
    
    @staticmethod
    def start_process(executable, args=None, env=None, hide_window=False, require_admin=False, working_dir=None):
        """
        启动进程
        
        Args:
            executable: 可执行文件路径
            args: 命令行参数列表
            env: 环境变量字典
            hide_window: 是否隐藏窗口
            require_admin: 是否需要管理员权限
            working_dir: 工作目录
        
        Returns:
            subprocess.Popen: 进程对象，如果启动失败返回None
        """
        try:
            if args is None:
                args = []
            
            # 构建完整的命令行
            cmd = [executable] + args
            
            # 设置启动信息
            startupinfo = None
            creationflags = 0
            
            if sys.platform == 'win32':
                # Windows平台特定设置
                startupinfo = subprocess.STARTUPINFO()
                if hide_window:
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    # 隐藏窗口时使用 CREATE_NO_WINDOW，避免创建新的控制台
                    creationflags |= 0x08000000  # CREATE_NO_WINDOW
                
                # 注意：require_admin 参数只是一个提示，实际上需要整个 Python 程序以管理员权限运行
                # subprocess.Popen 无法单独提升进程权限，必须父进程已经是管理员
            
            # 启动进程
            # 对于长期运行的进程，不捕获 stdout/stderr，避免缓冲区满导致进程阻塞
            # 注意：即使 hide_window=True，也不要重定向到 DEVNULL，因为有些程序需要输出日志才能正常运行
            process = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                creationflags=creationflags,
                env=env,  # 使用传入的环境变量
                cwd=working_dir,  # 设置工作目录
                # 让输出流继承父进程，不要捕获或重定向
                stdout=None,
                stderr=None,
                stdin=subprocess.DEVNULL
            )
            
            logger.info(f"进程启动成功: {executable}，PID: {process.pid}")
            return process
        except Exception as e:
            logger.error(f"启动进程失败: {e}")
            return None
    
    @staticmethod
    def is_process_running(process):
        """
        检查进程是否在运行
        
        Args:
            process: subprocess.Popen对象或进程ID
        
        Returns:
            bool: 进程是否在运行
        """
        try:
            if isinstance(process, subprocess.Popen):
                # 检查Popen对象的返回码
                returncode = process.poll()
                return returncode is None
            elif isinstance(process, int):
                # 检查进程ID是否存在
                return psutil.pid_exists(process)
            return False
        except Exception as e:
            logger.error(f"检查进程状态失败: {e}")
            return False
    
    @staticmethod
    def wait_for_port(port, timeout=30):
        """
        等待端口可用
        
        Args:
            port: 端口号
            timeout: 超时时间（秒）
        
        Returns:
            bool: 端口是否在超时前可用
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 尝试连接到端口
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    s.connect(('127.0.0.1', port))
                return True
            except (ConnectionRefusedError, socket.timeout):
                # 端口不可用，继续等待
                time.sleep(1)
        
        return False
    
    @staticmethod
    def kill_process(process, timeout=5):
        """
        杀死进程
        
        Args:
            process: subprocess.Popen对象或进程ID
            timeout: 超时时间（秒）
        """
        try:
            if isinstance(process, subprocess.Popen):
                # 杀死Popen对象
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # 超时后强制杀死
                    process.kill()
                    process.wait(timeout=3)
                logger.info(f"进程已终止: PID {process.pid}")
            elif isinstance(process, int):
                # 杀死进程ID
                proc = psutil.Process(process)
                proc.terminate()
                try:
                    proc.wait(timeout=timeout)
                except psutil.TimeoutExpired:
                    # 超时后强制杀死
                    proc.kill()
                    proc.wait(timeout=3)
                logger.info(f"进程已终止: PID {process}")
        except Exception as e:
            logger.error(f"杀死进程失败: {e}")
    
    @staticmethod
    def get_process_by_name(name):
        """
        根据进程名获取进程列表
        
        Args:
            name: 进程名
        
        Returns:
            list: 进程对象列表
        """
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and name.lower() in proc.info['name'].lower():
                    processes.append(proc)
        except Exception as e:
            logger.error(f"获取进程列表失败: {e}")
        return processes
    
    @staticmethod
    def get_process_by_port(port):
        """
        根据端口获取进程
        
        Args:
            port: 端口号
        
        Returns:
            psutil.Process: 进程对象，如果没有找到返回None
        """
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr and conn.laddr.port == port:
                    return psutil.Process(conn.pid)
        except Exception as e:
            logger.error(f"根据端口获取进程失败: {e}")
        return None
    
    @staticmethod
    def kill_by_port(port):
        """
        杀死占用指定端口的进程
        
        Args:
            port: 端口号
        """
        try:
            killed_count = 0
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr and conn.laddr.port == port:
                    try:
                        proc = psutil.Process(conn.pid)
                        proc_name = proc.name()
                        logger.info(f"杀死占用端口{port}的进程: {proc_name} (PID: {conn.pid})")
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=1)
                        killed_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            if killed_count > 0:
                logger.info(f"已清理{killed_count}个占用端口{port}的进程")
        except Exception as e:
            logger.error(f"清理端口{port}占用失败: {e}")
