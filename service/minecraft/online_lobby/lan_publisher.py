"""
局域网发布器
负责启动游戏、自动输入 /publish 命令开放局域网
"""
import subprocess
import threading
import time
import os
import re
import ctypes
from pathlib import Path
from typing import Optional, Callable, Tuple
from dataclasses import dataclass
from utils.logger import Logger

logger = Logger().get_logger("LANPublisher")


@dataclass
class PublishConfig:
    """发布配置"""
    port: int = 25565
    game_mode: str = "survival"  # survival, creative, adventure, spectator
    allow_commands: bool = False  # 是否允许其他玩家使用作弊


class LANPublisher:
    """局域网发布器"""
    
    def __init__(self, minecraft_dir: Path, version_id: str):
        """
        初始化发布器
        
        Args:
            minecraft_dir: Minecraft 根目录
            version_id: 游戏版本ID
        """
        self.minecraft_dir = Path(minecraft_dir)
        self.version_id = version_id
        self.version_dir = self.minecraft_dir / "versions" / version_id
        # Minecraft 日志在 .minecraft/logs 目录下，而不是版本目录
        self.log_file = self.minecraft_dir / "logs" / "latest.log"
        
        self.process: Optional[subprocess.Popen] = None
        self.hwnd = None  # 游戏窗口句柄
        self._monitoring = False
        self._published = False
        self._error = None
        self._publish_callback: Optional[Callable] = None
    
    def _find_game_window(self, timeout: int = 60) -> bool:
        """
        查找游戏窗口
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否找到窗口
        """
        if os.name != 'nt':
            logger.warning("仅支持 Windows 系统")
            return False
        
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        
        # 定义回调函数类型
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        
        candidates = []
        
        def enum_windows_callback(hwnd, lparam):
            # 只检查可见窗口
            if not user32.IsWindowVisible(hwnd):
                return True
            
            # 获取窗口标题
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value
                
                # 获取窗口类名
                class_buffer = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_buffer, 256)
                class_name = class_buffer.value
                
                # 检查是否是 Minecraft 窗口
                # 可能的标题格式：
                # - "Minecraft 1.21.10"
                # - "Minecraft* 1.21.10"
                # - "Minecraft 1.21.10 - Singleplayer"
                # - 包含版本号的标题
                title_lower = title.lower()
                is_minecraft = (
                    "minecraft" in title_lower or
                    # LWJGL 窗口（Minecraft 使用 LWJGL）
                    class_name == "LWJGL" or
                    class_name.startswith("GLFW") or
                    # 包含版本号格式 (1.xx.xx)
                    (re.search(r'1\.\d+\.\d+', title) and user32.IsWindowVisible(hwnd))
                )
                
                if is_minecraft:
                    # 获取窗口大小，过滤掉太小的窗口
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    width = rect.right - rect.left
                    height = rect.bottom - rect.top
                    
                    if width > 200 and height > 200:  # 过滤太小的窗口
                        candidates.append({
                            'hwnd': hwnd,
                            'title': title,
                            'class': class_name,
                            'size': (width, height)
                        })
            
            return True
        
        callback = EnumWindowsProc(enum_windows_callback)
        
        logger.info(f"🔍 开始查找 Minecraft 窗口 (超时: {timeout}秒)...")
        start_time = time.time()
        attempt = 0
        
        while time.time() - start_time < timeout:
            attempt += 1
            candidates.clear()
            
            user32.EnumWindows(callback, 0)
            
            if candidates:
                # 优先选择标题包含 "Minecraft" 的窗口
                best = None
                for c in candidates:
                    if "minecraft" in c['title'].lower():
                        best = c
                        break
                
                if not best:
                    best = candidates[0]
                
                self.hwnd = best['hwnd']
                logger.info(f"✅ 找到游戏窗口:")
                logger.info(f"   标题: {best['title']}")
                logger.info(f"   类名: {best['class']}")
                logger.info(f"   句柄: {best['hwnd']}")
                logger.info(f"   大小: {best['size']}")
                return True
            
            if attempt % 5 == 0:
                logger.debug(f"🔄 已尝试 {attempt} 次，未找到窗口...")
            
            time.sleep(1)
        
        logger.error(f"❌ 超时 ({timeout}秒)：未找到 Minecraft 窗口")
        return False
    
    def _check_player_joined(self) -> bool:
        """
        快速检测玩家是否已加入游戏（不阻塞）
        
        Returns:
            是否检测到玩家加入
        """
        if not self.log_file.exists():
            return False
        
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            join_patterns = [
                r"加入了游戏",
                r"joined the game",
                r"logged in with entity id",
            ]
            
            for pattern in join_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True
        except:
            pass
        
        return False
    
    def _wait_for_game_started(self, timeout: int = 180) -> bool:
        """
        等待游戏启动（监控日志）
        
        检测日志中的启动标志，如 "Setting user:" 或 "LWJGL Version"
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否检测到游戏启动
        """
        logger.info(f"⏳ 等待游戏启动... (监控日志，超时 {timeout} 秒)")
        
        start_time = time.time()
        
        # 游戏启动的标志
        start_patterns = [
            r"Setting user:",
            r"LWJGL Version",
            r"Minecraft main window",
            r"Backend library:",
            r"Loaded \d+ languages",
            r"OpenAL initialized",
            r"Created: \d+x\d+",
            r"Environment: authHost",
        ]
        
        # 等待日志文件出现
        wait_count = 0
        while not self.log_file.exists() and time.time() - start_time < 60:
            wait_count += 1
            if wait_count % 10 == 0:
                logger.info(f"   等待日志文件出现... ({wait_count}秒)")
            time.sleep(1)
        
        if not self.log_file.exists():
            logger.warning(f"⚠️ 日志文件不存在，等待 30 秒后继续...")
            time.sleep(30)
            return True
        
        logger.info(f"✅ 日志文件已出现: {self.log_file}")
        
        # 监控日志内容
        last_check_time = 0
        while time.time() - start_time < timeout:
            try:
                with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检查启动标志
                for pattern in start_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        logger.info(f"✅ 检测到游戏启动! (匹配: {pattern})")
                        return True
                
                # 每 10 秒输出一次状态
                elapsed = int(time.time() - start_time)
                if elapsed - last_check_time >= 10:
                    last_check_time = elapsed
                    logger.info(f"   监控中... 日志大小: {len(content)} 字节, 已等待 {elapsed} 秒")
                
            except Exception as e:
                logger.debug(f"读取日志失败: {e}")
            
            time.sleep(0.5)
        
        logger.warning(f"⚠️ 等待超时 ({timeout}秒)，假设游戏已启动")
        return True
    
    def _wait_for_game_loaded(self, timeout: int = 120) -> bool:
        """
        等待游戏加载完成（进入存档）
        
        通过监控日志文件检测玩家是否进入世界
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否检测到玩家进入世界
        """
        logger.info(f"⏳ 等待玩家进入世界... (监控日志文件，超时 {timeout} 秒)")
        
        start_time = time.time()
        
        # 检测玩家进入世界的标志
        join_patterns = [
            r"加入了游戏",  # 中文：xxx加入了游戏
            r"joined the game",  # 英文
            r"logged in with entity id",  # xxx logged in with entity id
            r"Saving chunks for level",  # 保存区块，通常意味着已经进入
            r"Loaded \d+ advancements",  # 加载成就
            r"Time elapsed:",  # 统计信息
        ]
        
        # 等待日志文件出现
        wait_count = 0
        while not self.log_file.exists() and time.time() - start_time < 30:
            wait_count += 1
            if wait_count % 5 == 0:
                logger.info(f"   等待日志文件出现... ({wait_count}秒)")
            time.sleep(1)
        
        if not self.log_file.exists():
            logger.warning(f"⚠️ 日志文件 {self.log_file} 不存在，等待 15 秒后继续...")
            time.sleep(15)
            return True
        
        logger.info(f"✅ 日志文件已出现: {self.log_file}")
        
        # 监控日志内容
        last_check_time = 0
        while time.time() - start_time < timeout:
            try:
                with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检查整个日志内容（不仅仅是新增部分）
                for pattern in join_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        logger.info(f"✅ 检测到玩家进入世界! (匹配: {pattern})")
                        time.sleep(1)  # 短暂等待界面稳定
                        return True
                
                # 每 5 秒输出一次状态
                elapsed = int(time.time() - start_time)
                if elapsed - last_check_time >= 5:
                    last_check_time = elapsed
                    logger.info(f"   监控中... 日志大小: {len(content)} 字节, 已等待 {elapsed} 秒")
                
            except Exception as e:
                logger.debug(f"读取日志失败: {e}")
            
            time.sleep(0.3)  # 更频繁检查
        
        logger.warning(f"⚠️ 等待超时 ({timeout}秒)，假设游戏已进入")
        return True
    
    def _send_command_once(self, cmd_content: str):
        """
        发送一次命令（使用 pyautogui + pygetwindow）
        
        Args:
            cmd_content: 命令内容（不含 /）
        """
        try:
            import pyautogui
            import pygetwindow as gw
            import pyperclip
        except ImportError as e:
            logger.error(f"缺少依赖: {e}")
            return
        
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05
        
        logger.info(f"   📨 发送命令: {cmd_content}")
        
        # 查找 Minecraft 窗口
        mc_windows = [w for w in gw.getAllWindows() if "minecraft" in w.title.lower()]
        if not mc_windows:
            logger.error("   ❌ 未找到 Minecraft 窗口")
            return
        
        mc_win = mc_windows[0]
        logger.info(f"   🎮 窗口: {mc_win.title}")
        
        # 激活窗口
        try:
            mc_win.activate()
        except:
            pass
        time.sleep(0.1)
        
        # 点击窗口中心
        cx = mc_win.left + mc_win.width // 2
        cy = mc_win.top + mc_win.height // 2
        pyautogui.click(cx, cy)
        time.sleep(0.1)
        
        # 按 / 打开命令框
        pyautogui.press('/')
        time.sleep(0.2)
        
        # 复制并粘贴命令
        pyperclip.copy(cmd_content)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        
        # 按回车发送
        pyautogui.press('enter')
        
        logger.info("   ✅ 命令已发送")
    
    def _monitor_publish_success(self, timeout: int = 30) -> bool:
        """
        监控日志，检测是否成功开放局域网
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否成功开放
        """
        start_time = time.time()
        
        # 成功开放的标志
        success_patterns = [
            r"Local game hosted on port (\d+)",
            r"Started serving on (\d+)",
            r"Hosting on port (\d+)",
            r"本地游戏已开放，端口",  # 中文版本
        ]
        
        while time.time() - start_time < timeout:
            try:
                if not self.log_file.exists():
                    time.sleep(0.3)
                    continue
                
                with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检查整个日志内容
                for pattern in success_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        try:
                            port = match.group(1)
                            logger.info(f"✅ 检测到局域网已开放，端口: {port}")
                        except:
                            logger.info(f"✅ 检测到局域网已开放!")
                        return True
                
            except Exception as e:
                logger.debug(f"读取日志失败: {e}")
            
            time.sleep(0.3)
        
        return False
    
    def _block_input(self, block: bool):
        """
        阻止/恢复鼠标键盘输入
        
        Args:
            block: True 阻止，False 恢复
        """
        if os.name != 'nt':
            return
        
        try:
            ctypes.windll.user32.BlockInput(block)
            logger.info(f"{'🔒 已阻止' if block else '🔓 已恢复'}鼠标键盘输入")
        except Exception as e:
            logger.warning(f"设置输入阻止状态失败: {e}")
    
    def _set_fullscreen(self, fullscreen: bool):
        """
        设置窗口全屏/退出全屏
        
        Args:
            fullscreen: True 全屏，False 退出全屏
        """
        if os.name != 'nt' or not self.hwnd:
            return
        
        try:
            user32 = ctypes.windll.user32
            
            if fullscreen:
                # 最大化窗口
                SW_MAXIMIZE = 3
                user32.ShowWindow(self.hwnd, SW_MAXIMIZE)
            else:
                # 恢复窗口
                SW_RESTORE = 9
                user32.ShowWindow(self.hwnd, SW_RESTORE)
            
            logger.info(f"{'🖥️ 已设置全屏' if fullscreen else '🗗 已退出全屏'}")
        except Exception as e:
            logger.warning(f"设置窗口状态失败: {e}")
    
    def publish_lan(
        self,
        config: PublishConfig,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        发布局域网（需要游戏已启动并加载存档）
        
        Args:
            config: 发布配置
            on_success: 成功回调
            on_error: 错误回调
            
        Returns:
            是否成功启动发布流程
        """
        self._publish_callback = on_success
        
        def publish_thread():
            try:
                import pyautogui
                import pygetwindow as gw
                import pyperclip
                
                pyautogui.FAILSAFE = False
                pyautogui.PAUSE = 0.1  # 每次操作后自动等待 0.1 秒
                
                logger.info("🚀 开始自动化局域网发布流程...")
                
                # 1. 监听日志，等待 MC 启动成功
                logger.info("📍 步骤1: 监听日志，等待游戏启动...")
                if not self._wait_for_game_started(timeout=180):
                    error_msg = "等待游戏启动超时"
                    self._error = error_msg
                    if on_error:
                        on_error(error_msg)
                    return
                
                # 2. 游戏启动了，查找窗口
                logger.info("📍 步骤2: 查找游戏窗口...")
                mc_win = None
                for _ in range(30):
                    mc_windows = [w for w in gw.getAllWindows() if "minecraft" in w.title.lower()]
                    if mc_windows:
                        mc_win = mc_windows[0]
                        logger.info(f"   ✅ 找到窗口: {mc_win.title}")
                        break
                    time.sleep(1)
                
                if not mc_win:
                    error_msg = "无法找到 Minecraft 窗口"
                    self._error = error_msg
                    if on_error:
                        on_error(error_msg)
                    return
                
                # 3. 游戏已全屏启动，跳过手动 F11
                logger.info("📍 步骤3: 游戏已配置为全屏启动，跳过手动切换...")
                
                # 4. 监听日志，等待玩家加入游戏，同时循环键入
                logger.info("📍 步骤4: 等待玩家加入并循环键入命令...")
                
                allow_cmd = "false"
                cmd_content = f"publish {allow_cmd} {config.game_mode} {config.port}"
                
                # 如果需要关闭正版验证，尝试发送 /set-online-mode false 命令（部分 mod 或插件支持）
                # 但原版并没有这个命令，所以最好的办法还是在启动前修改配置
                # 这里我们添加一个备用方案：如果安装了 Carpet 模组或其他管理模组，可能支持类似命令
                # 不过对于纯原版，我们只能依赖于启动参数或存档修改
                
                # 这里我们尝试一个 Trick：如果是在服务器环境下，可以直接修改 server.properties
                # 但对于单人游戏局域网开放，正版验证是在开放瞬间决定的
                # 在 1.16+ 版本中，如果使用微软账号登录，默认会开启正版验证
                
                pyperclip.copy(cmd_content)
                
                try:
                    max_retries = 30
                    success = False
                    player_joined = False
                    
                    for attempt in range(1, max_retries + 1):
                        # 检测是否已经成功开放
                        if self._monitor_publish_success(timeout=0.5):
                            logger.info(f"   ✅ 检测到局域网已开放！")
                            success = True
                            break
                        
                        # 检测玩家是否已加入（只检测一次就够了）
                        if not player_joined:
                            if self._check_player_joined():
                                logger.info(f"   ✅ 检测到玩家已加入游戏！")
                                player_joined = True
                        
                        # 玩家加入后开始键入
                        if player_joined:
                            mc_windows = [w for w in gw.getAllWindows() if "minecraft" in w.title.lower()]
                            if mc_windows:
                                # 优先选择包含"单人游戏"的窗口
                                mc_win = next((w for w in mc_windows if "单人游戏" in w.title or "singleplayer" in w.title.lower()), mc_windows[0])
                                
                                # 激活并点击
                                try:
                                    mc_win.activate()
                                except:
                                    pass
                                time.sleep(0.15)
                                pyautogui.click(mc_win.left + mc_win.width // 2, mc_win.top + mc_win.height // 2)
                                time.sleep(0.15)
                                
                                # CapsLock + 键入命令 + CapsLock
                                pyautogui.press('capslock')
                                time.sleep(0.08)
                                pyautogui.press('/')
                                time.sleep(0.12)
                                pyautogui.hotkey('ctrl', 'v')
                                time.sleep(0.08)
                                pyautogui.press('enter')
                                time.sleep(0.08)
                                pyautogui.press('capslock')
                                
                                logger.info(f"   ✅ 第 {attempt} 次命令已发送")
                        else:
                            # 玩家还没加入，等待
                            if attempt % 5 == 0:
                                logger.info(f"   ⏳ 等待玩家加入... ({attempt})")
                        
                        time.sleep(0.5)
                    
                    # 5. F11 退出全屏
                    logger.info("📍 步骤5: F11 退出全屏...")
                    for retry in range(3):
                        try:
                            mc_windows = [w for w in gw.getAllWindows() if "minecraft" in w.title.lower()]
                            if mc_windows:
                                mc_win = mc_windows[0]
                                if mc_win.isMinimized:
                                    mc_win.restore()
                                mc_win.activate()
                                time.sleep(0.2)
                                pyautogui.click(mc_win.left + mc_win.width // 2, mc_win.top + mc_win.height // 2)
                                time.sleep(0.1)
                                pyautogui.press('f11')
                                logger.info("   ✅ 已退出全屏")
                                break
                        except Exception as e:
                            logger.warning(f"   ⚠️ 退出全屏尝试 {retry+1} 失败: {e}")
                            time.sleep(1)
                    
                    if success:
                        self._published = True
                        logger.info("🎉 局域网发布成功！")
                        logger.info("✅ 自动化流程完成！玩家可以正常游戏了")
                        if on_success:
                            on_success()
                    else:
                        logger.warning(f"⚠️ 已尝试 {max_retries} 次，均未检测到成功")
                        error_msg = "局域网发布可能失败，请手动检查游戏内是否已开放"
                        self._error = error_msg
                        if on_error:
                            on_error(error_msg)
                
                except Exception as e:
                    # 发生异常时确保恢复状态
                    logger.error(f"发送命令时发生错误: {e}")
                    try:
                        pyautogui.press('f11')  # 尝试退出全屏
                    except:
                        pass
                    raise
                
            except Exception as e:
                logger.error(f"发布局域网时发生错误: {e}", exc_info=True)
                self._error = str(e)
                if on_error:
                    on_error(str(e))
        
        # 在后台线程执行
        thread = threading.Thread(target=publish_thread, daemon=True)
        thread.start()
        
        return True
    
    def is_published(self) -> bool:
        """是否已成功发布"""
        return self._published
    
    def get_error(self) -> Optional[str]:
        """获取错误信息"""
        return self._error


class LANPublishService:
    """
    局域网发布服务
    整合启动游戏和发布局域网的完整流程
    """
    
    def __init__(self, minecraft_dir: Path):
        """
        初始化服务
        
        Args:
            minecraft_dir: Minecraft 根目录
        """
        self.minecraft_dir = Path(minecraft_dir)
        self.current_publisher: Optional[LANPublisher] = None
    
    def start_and_publish(
        self,
        version_id: str,
        save_name: str,
        username: str,
        port: int = 25565,
        game_mode: str = "survival",
        uuid: str = "",
        access_token: str = "",
        jvm_args: list = None,
        on_game_started: Optional[Callable[[int], None]] = None,
        on_publish_success: Optional[Callable] = None,
        on_error: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        启动游戏并发布局域网
        
        Args:
            version_id: 游戏版本ID
            save_name: 存档名称
            username: 玩家用户名
            port: 端口
            game_mode: 游戏模式
            uuid: 玩家UUID
            access_token: 访问令牌
            jvm_args: JVM参数
            on_game_started: 游戏启动回调，参数为PID
            on_publish_success: 发布成功回调
            on_error: 错误回调
            
        Returns:
            是否成功启动流程
        """
        from service.minecraft.game_launcher import GameLauncher
        
        def launch_thread():
            try:
                logger.info(f"🎮 开始启动游戏: {version_id}, 存档: {save_name}")
                
                # 1. 创建启动器
                launcher = GameLauncher(minecraft_dir=self.minecraft_dir)
                
                # 2. 构建额外的游戏参数（直接进入存档）
                # Minecraft 1.20+ 使用 --quickPlaySingleplayer 参数自动加载存档
                # 参数值是存档文件夹名称
                extra_game_args = ['--quickPlaySingleplayer', save_name]
                logger.info(f"📂 将自动加载存档: {save_name} (使用 quickPlaySingleplayer)")
                
                # 如果是离线模式，强制不传递 accessToken 和 UUID（或使用离线 UUID）
                # 注意：在 1.16+ 版本中，如果使用微软账号登录，默认会开启正版验证
                # 所以对于离线用户，我们需要确保游戏认为是"离线"状态
                if not access_token:
                     logger.info("⚡ 离线模式启动，将尝试规避正版验证...")
                     # 在 GameLauncher 中我们已经处理了参数，这里不需要额外处理
                
                # 3. 启动游戏
                process = launcher.launch_game(
                    version_id=version_id,
                    username=username,
                    uuid=uuid,
                    access_token=access_token,
                    jvm_args=jvm_args or [],
                    extra_game_args=extra_game_args
                )
                
                if not process:
                    if on_error:
                        on_error("游戏启动失败")
                    return
                
                logger.info(f"✅ 游戏已启动，PID: {process.pid}")
                
                if on_game_started:
                    on_game_started(process.pid)
                
                # 4. 创建发布器并开始发布流程
                self.current_publisher = LANPublisher(
                    minecraft_dir=self.minecraft_dir,
                    version_id=version_id
                )
                
                config = PublishConfig(
                    port=port,
                    game_mode=game_mode,
                    allow_commands=False
                )
                
                # 5. 开始发布
                self.current_publisher.publish_lan(
                    config=config,
                    on_success=on_publish_success,
                    on_error=on_error
                )
                
            except Exception as e:
                logger.error(f"启动并发布时发生错误: {e}", exc_info=True)
                if on_error:
                    on_error(str(e))
        
        # 在后台线程执行
        thread = threading.Thread(target=launch_thread, daemon=True)
        thread.start()
        
        return True

