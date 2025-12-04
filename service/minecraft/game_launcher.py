"""
Minecraft 游戏启动器
负责构建和执行 Minecraft 启动命令
"""
import json
import subprocess
import platform
import hashlib
import uuid as uuid_lib
from pathlib import Path
from typing import Dict, List, Optional
from utils.logger import logger
from utils.process_helper import ProcessHelper


class GameLauncher:
    """Minecraft 游戏启动器"""
    
    def __init__(self, minecraft_dir: Path):
        """
        初始化游戏启动器
        
        Args:
            minecraft_dir: Minecraft 根目录
        """
        self.minecraft_dir = Path(minecraft_dir)
        self.java_path = self._find_java_executable()
    
    def _find_java_executable(self) -> str:
        """
        查找 Java 可执行文件路径
        
        Returns:
            Java 可执行文件路径
        """
        # 首先检查系统 PATH 中的 java
        try:
            # 使用 startupinfo 隐藏窗口
            startupinfo = None
            creationflags = 0
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(["java", "-version"], 
                                  capture_output=True, text=True, timeout=10,
                                  startupinfo=startupinfo, creationflags=creationflags)
            if result.returncode == 0:
                return "java"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Windows 系统尝试常见路径
        if platform.system() == "Windows":
            common_paths = [
                "C:\\Program Files\\Java\\jdk-17\\bin\\java.exe",
                "C:\\Program Files\\Java\\jre-17\\bin\\java.exe",
                "C:\\Program Files\\Eclipse Adoptium\\jdk-17\\bin\\java.exe",
                "C:\\Program Files\\Eclipse Adoptium\\jre-17\\bin\\java.exe",
                "C:\\Program Files (x86)\\Java\\jdk-17\\bin\\java.exe",
                "C:\\Program Files (x86)\\Java\\jre-17\\bin\\java.exe"
            ]
            
            for path in common_paths:
                if Path(path).exists():
                    return path
                    
        # 默认返回 java（可能不在 PATH 中）
        return "java"
    
    def _ensure_chinese_language(self, version_id: str):
        """
        确保游戏语言设置为中文（简体）
        版本隔离模式下，options.txt 应该放在版本专属目录下
        
        Args:
            version_id: 版本 ID
        """
        try:
            # 版本隔离：options.txt 应该放在版本专属目录下
            version_game_dir = self.minecraft_dir / "versions" / version_id
            options_file = version_game_dir / "options.txt"
            
            logger.info(f"检查游戏选项文件: {options_file}")
            
            # 如果 options.txt 不存在，创建一个默认的中文配置
            if not options_file.exists():
                logger.info("创建默认的中文游戏设置...")
                default_options = [
                    "version:3465",
                    "autoJump:false",
                    "operatorItemsTab:false",
                    "autoSuggestions:true",
                    "chatColors:true",
                    "chatLinks:true",
                    "chatLinksPrompt:true",
                    "enableVsync:true",
                    "entityShadows:true",
                    "forceUnicodeFont:false",
                    "discrete_mouse_scroll:false",
                    "invertYMouse:false",
                    "realmsNotifications:false",  # 禁用 Realms 通知减少错误
                    "reducedDebugInfo:false",
                    "showSubtitles:false",
                    "directionalAudio:false",
                    "touchscreen:false",
                    "fullscreen:true",  # 默认开启全屏
                    "bobView:true",
                    "toggleCrouch:false",
                    "toggleSprint:false",
                    "darkMojangStudiosBackground:false",
                    "hideLightningFlashes:false",
                    "mouseSensitivity:0.5",
                    "fov:0.0",
                    "screenEffectScale:1.0",
                    "fovEffectScale:1.0",
                    "darknessEffectScale:1.0",
                    "glintSpeed:0.5",
                    "glintStrength:0.75",
                    "damageTiltStrength:1.0",
                    "highContrast:false",
                    "gamma:0.5",
                    "renderDistance:12",
                    "simulationDistance:12",
                    "entityDistanceScaling:1.0",
                    "guiScale:0",
                    "particles:0",
                    "maxFps:120",
                    "graphicsMode:1",
                    "ao:true",
                    "prioritizeChunkUpdates:0",
                    "biomeBlendDistance:2",
                    "renderClouds:\"true\"",
                    "resourcePacks:[]",
                    "incompatibleResourcePacks:[]",
                    "lastServer:",
                    "lang:zh_cn",  # 设置为中文（简体）
                    "soundDevice:\"\"",
                    "chatVisibility:0",
                    "chatOpacity:1.0",
                    "chatLineSpacing:0.0",
                    "textBackgroundOpacity:0.5",
                    "backgroundForChatOnly:true",
                    "hideServerAddress:false",
                    "advancedItemTooltips:false",
                    "pauseOnLostFocus:true",
                    "overrideWidth:0",
                    "overrideHeight:0",
                    "chatHeightFocused:1.0",
                    "chatDelay:0.0",
                    "chatHeightUnfocused:0.44366196",
                    "chatScale:1.0",
                    "chatWidth:1.0",
                    "notificationDisplayTime:1.0",
                    "mipmapLevels:4",
                    "useNativeTransport:true",
                    "mainHand:\"right\"",
                    "attackIndicator:1",
                    "narrator:0",
                    "tutorialStep:none",
                    "mouseWheelSensitivity:1.0",
                    "rawMouseInput:true",
                    "glDebugVerbosity:1",
                    "skipMultiplayerWarning:false",
                    "skipRealms32bitWarning:true",  # 跳过 Realms 32 位警告
                    "hideMatchedNames:true",
                    "joinedFirstServer:false",
                    "hideBundleTutorial:false",
                    "syncChunkWrites:true",
                    "showAutosaveIndicator:true",
                    "allowServerListing:true",
                    "chatPreview:1",
                    "chatColors:true",
                    "onlyShowSecureChat:false"
                ]
                
                # 写入文件
                with open(options_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(default_options))
                
                logger.info(f"✅ 已创建中文游戏设置: {options_file}")
            else:
                # 如果文件已存在，强制更新语言设置为中文
                logger.info("检查并更新游戏语言设置...")
                
                # 读取现有设置
                with open(options_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                # 检查是否已经设置为中文
                has_lang_setting = False
                is_chinese = False
                has_realms_setting = False
                has_realms_warning_setting = False
                updated = False
                
                for i, line in enumerate(lines):
                    # 检查语言设置
                    if line.startswith("lang:"):
                        has_lang_setting = True
                        current_lang = line.strip().split(":", 1)[1] if ":" in line else ""
                        if current_lang.lower() != "zh_cn":
                            # 强制更新为中文
                            lines[i] = "lang:zh_cn\n"
                            logger.info(f"🔄 已将游戏语言从 '{current_lang}' 更新为 'zh_cn'")
                            updated = True
                        else:
                            is_chinese = True
                            logger.info("✅ 游戏语言已设置为中文")
                    # 检查 Realms 通知设置
                    elif line.startswith("realmsNotifications:"):
                        has_realms_setting = True
                        if "false" not in line.lower():
                            lines[i] = "realmsNotifications:false\n"
                            logger.info("🔄 已禁用 Realms 通知")
                            updated = True
                    # 检查 Realms 32位警告设置
                    elif line.startswith("skipRealms32bitWarning:"):
                        has_realms_warning_setting = True
                        if "true" not in line.lower():
                            lines[i] = "skipRealms32bitWarning:true\n"
                            logger.info("🔄 已跳过 Realms 32位警告")
                            updated = True
                
                # 如果没有语言设置，添加一个
                if not has_lang_setting:
                    lines.append("lang:zh_cn\n")
                    logger.info("➕ 已添加中文语言设置")
                    updated = True
                
                # 如果没有 Realms 设置，添加一个
                if not has_realms_setting:
                    lines.append("realmsNotifications:false\n")
                    logger.info("➕ 已添加禁用 Realms 通知设置")
                    updated = True
                
                # 如果没有 Realms 警告设置，添加一个
                if not has_realms_warning_setting:
                    lines.append("skipRealms32bitWarning:true\n")
                    logger.info("➕ 已添加跳过 Realms 32位警告设置")
                    updated = True
                
                # 如果有更改，写回文件
                if updated:
                    with open(options_file, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    logger.info(f"✅ 已更新游戏设置: {options_file}")
                    
        except Exception as e:
            logger.warning(f"设置游戏语言时发生错误: {e}")
            # 不影响游戏启动，只是记录警告
    
    def launch_game(
        self,
        version_id: str,
        username: str = "Player",
        uuid: str = "",
        access_token: str = "",
        jvm_args: Optional[List[str]] = None,
        extra_game_args: Optional[List[str]] = None
    ) -> Optional[subprocess.Popen]:
        """
        启动 Minecraft 游戏（版本隔离模式）
        
        Args:
            version_id: 版本 ID（如 "1.21.10"）
            username: 玩家用户名
            uuid: 玩家 UUID（正版账户需要）
            access_token: 访问令牌（正版账户需要）
            jvm_args: JVM 参数列表
            extra_game_args: 额外的游戏参数
            
        Returns:
            subprocess.Popen: 启动的进程对象，失败返回 None
        """
        try:
            logger.info(f"🚀 开始启动 Minecraft {version_id} (版本隔离模式)")
            
            # 版本隔离：创建版本专属的游戏目录
            version_game_dir = self.minecraft_dir / "versions" / version_id
            version_game_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 版本游戏目录: {version_game_dir}")
            
            # 确保游戏选项文件存在并设置为中文（版本隔离）
            self._ensure_chinese_language(version_id)
            
            # 获取版本 JSON 文件路径
            # 优先使用与版本ID同名的JSON（如 3123.json），否则使用第一个找到的
            version_dir = self.minecraft_dir / "versions" / version_id
            
            # 首先尝试精确匹配版本ID的JSON文件
            version_json_path = version_dir / f"{version_id}.json"
            
            if not version_json_path.exists():
                # 如果没有精确匹配，查找目录中的所有JSON文件
                json_files = list(version_dir.glob("*.json"))
                
                if not json_files:
                    logger.error(f"版本配置文件不存在: {version_dir}")
                    return None
                
                # 使用第一个找到的JSON（兼容旧逻辑）
                version_json_path = json_files[0]
            
            logger.info(f"📄 使用JSON文件: {version_json_path.name}")
            
            # 读取版本配置
            with open(version_json_path, "r", encoding="utf-8") as f:
                version_data = json.load(f)
            
            # 构建启动命令（传递版本游戏目录）
            command = self._build_launch_command(
                version_data, version_id, username, uuid, access_token,
                jvm_args or [], extra_game_args or [], version_game_dir
            )
            
            if not command:
                logger.error("构建启动命令失败")
                return None
            
            logger.info(f"启动命令: {' '.join(command)}")
            
            # 设置工作目录为版本目录（版本隔离）
            working_dir = self.minecraft_dir / "versions" / version_id
            
            # 设置日志文件路径 - 用于自动化检测游戏状态
            log_dir = self.minecraft_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "latest.log"
            
            # 启动游戏进程，将输出重定向到日志文件
            process = ProcessHelper.start_process(
                executable=command[0],
                args=command[1:],
                working_dir=working_dir,
                log_file=str(log_file)
            )
            
            if process:
                logger.info(f"✅ Minecraft 启动成功，PID: {process.pid}")
                return process
            else:
                logger.error("❌ Minecraft 启动失败")
                return None
                
        except Exception as e:
            logger.error(f"启动游戏时发生异常: {e}", exc_info=True)
            return None
    
    def _get_offline_uuid(self, username: str) -> str:
        """
        生成离线模式 UUID (基于用户名)
        算法: md5("OfflinePlayer:" + username)
        """
        string = "OfflinePlayer:" + username
        hash = hashlib.md5(string.encode('utf-8')).digest()
        
        # 设置 UUID 版本为 3
        # byte 6: version 3 (0011xxxx) -> (b & 0x0f) | 0x30
        # byte 8: variant 1 (10xxxxxx) -> (b & 0x3f) | 0x80
        
        byte_list = list(hash)
        byte_list[6] = (byte_list[6] & 0x0f) | 0x30
        byte_list[8] = (byte_list[8] & 0x3f) | 0x80
        
        return str(uuid_lib.UUID(bytes=bytes(byte_list)))

    def _build_launch_command(
        self,
        version_data: Dict,
        version_id: str,
        username: str,
        uuid: str,
        access_token: str,
        jvm_args: List[str],
        extra_game_args: List[str],
        version_game_dir: Path
    ) -> Optional[List[str]]:
        """
        构建启动命令（版本隔离模式）
        
        Args:
            version_data: 版本 JSON 数据
            version_id: 版本 ID
            username: 用户名
            uuid: UUID
            access_token: 访问令牌
            jvm_args: JVM 参数
            extra_game_args: 额外游戏参数
            version_game_dir: 版本专属游戏目录
            
        Returns:
            启动命令列表
        """
        # 如果没有 UUID，生成离线 UUID
        if not uuid:
            uuid = self._get_offline_uuid(username)
            
        try:
            # 基础命令
            command = [self.java_path]
            
            # 添加默认 JVM 参数
            default_jvm_args = [
                "-Xmx4G",  # 最大内存 4GB
                "-Xms2G",  # 初始内存 2GB
                "-XX:+UnlockExperimentalVMOptions",
                "-XX:+UseG1GC",
                "-XX:G1NewSizePercent=20",
                "-XX:G1ReservePercent=20",
                "-XX:MaxGCPauseMillis=50",
                "-XX:G1HeapRegionSize=32M",
                "-Dlog4j2.formatMsgNoLookups=true",  # 安全配置
            ]
            
            # 合并 JVM 参数
            command.extend(default_jvm_args)
            command.extend(jvm_args)
            
            # 添加从 version.json 获取的 JVM 参数
            if "arguments" in version_data and "jvm" in version_data["arguments"]:
                jvm_arguments = version_data["arguments"]["jvm"]
                for arg in jvm_arguments:
                    if isinstance(arg, str):
                        # 处理占位符（版本隔离）
                        arg = arg.replace("${version_name}", version_id)
                        arg = arg.replace("${library_directory}", str(self.minecraft_dir / "libraries"))
                        arg = arg.replace("${natives_directory}", str(version_game_dir / "natives"))
                        arg = arg.replace("${classpath_separator}", ";" if platform.system() == "Windows" else ":" )
                        arg = arg.replace("${version_type}", version_data.get("type", "release"))
                        arg = arg.replace("${launcher_name}", "FlowerGame")
                        arg = arg.replace("${launcher_version}", "1.0.0")
                        command.append(arg)
                    elif isinstance(arg, dict) and "value" in arg:
                        # 处理带有规则的参数
                        if self._evaluate_rules(arg.get("rules", [])):
                            value = arg["value"]
                            if isinstance(value, list):
                                # 处理列表值，替换占位符
                                processed_values = []
                                for v in value:
                                    v = v.replace("${auth_player_name}", username)
                                    v = v.replace("${version_name}", version_id)
                                    v = v.replace("${game_directory}", str(version_game_dir))  # 版本隔离
                                    v = v.replace("${assets_root}", str(self.minecraft_dir / "assets"))
                                    v = v.replace("${assets_index_name}", version_data.get("assetIndex", {}).get("id", version_id))
                                    v = v.replace("${auth_uuid}", uuid)
                                    # PCL2/HMCL 离线登录策略：
                                    # 1. accessToken: 传递非空字符串（如 "000000" 或 "0"）
                                    # 2. userType: 传递 "legacy" 或 "mojang" (HMCL使用mojang)
                                    # 3. versionType: 保持原样 ("release")
                                    # 4. userProperties: 传递 "{}"
                                    # 5. uuid: 离线 UUID
                                    
                                    if not access_token:
                                        # 离线模式
                                        v = v.replace("${auth_access_token}", "000000")
                                        v = v.replace("${user_type}", "mojang") # HMCL/PCL 使用 mojang 类型以兼容
                                        v = v.replace("${user_properties}", "{}")
                                    else:
                                        # 正版模式
                                        v = v.replace("${auth_access_token}", access_token)
                                        v = v.replace("${user_type}", "msa")
                                        v = v.replace("${user_properties}", "{}") # 通常为空
                                    
                                    v = v.replace("${version_type}", version_data.get("type", "release"))
                                    v = v.replace("${clientid}", "FlowerGame")
                                    v = v.replace("${auth_xuid}", "")
                                    # 跳过包含未替换占位符的参数
                                    if "${" in v:
                                        logger.debug(f"跳过包含未替换占位符的参数列表项: {v}")
                                        continue
                                    # 跳过空参数
                                    if not v or v.isspace():
                                        logger.debug(f"跳过空参数列表项")
                                        continue
                                    # 跳过可能导致冲突的快速游戏参数
                                    if v in ["--demo", "--width", "--height", "--quickPlayPath", "--quickPlaySingleplayer", "--quickPlayMultiplayer", "--quickPlayRealms"]:
                                        logger.debug(f"跳过可能导致冲突的参数列表项: {v}")
                                        continue
                                    processed_values.append(v)
                                    logger.debug(f"添加游戏参数列表项: {v}")
                                command.extend(processed_values)
                            else:
                                # 处理单个值，替换占位符（版本隔离）
                                value = value.replace("${auth_player_name}", username)
                                value = value.replace("${version_name}", version_id)
                                value = value.replace("${game_directory}", str(version_game_dir))  # 版本隔离
                                value = value.replace("${assets_root}", str(self.minecraft_dir / "assets"))
                                value = value.replace("${assets_index_name}", version_data.get("assetIndex", {}).get("id", version_id))
                                value = value.replace("${auth_uuid}", uuid)
                                if not access_token:
                                    # 离线模式
                                    value = value.replace("${auth_access_token}", "000000")
                                    value = value.replace("${user_type}", "mojang")
                                    value = value.replace("${user_properties}", "{}")
                                else:
                                    # 正版模式
                                    value = value.replace("${auth_access_token}", access_token)
                                    value = value.replace("${user_type}", "msa")
                                    value = value.replace("${user_properties}", "{}")
                                    
                                value = value.replace("${version_type}", version_data.get("type", "release"))
                                value = value.replace("${clientid}", "FlowerGame")
                                value = value.replace("${auth_xuid}", "")
                                command.append(str(value))
            
            # 构建类路径
            classpath = self._build_classpath(version_data, version_id)
            if classpath:
                # 替换 classpath 占位符
                for i, arg in enumerate(command):
                    if isinstance(arg, str) and "${classpath}" in arg:
                        command[i] = arg.replace("${classpath}", classpath)
            
            # 添加主类
            main_class = version_data.get("mainClass")
            if not main_class:
                logger.error("未找到主类")
                return None
            command.append(main_class)
            
            # 添加从 version.json 获取的游戏参数
            game_args = []
            if "arguments" in version_data and "game" in version_data["arguments"]:
                game_arguments = version_data["arguments"]["game"]
                for arg in game_arguments:
                    if isinstance(arg, str):
                        # 处理占位符（版本隔离）
                        arg = arg.replace("${auth_player_name}", username)
                        arg = arg.replace("${version_name}", version_id)
                        arg = arg.replace("${game_directory}", str(version_game_dir))  # 版本隔离
                        arg = arg.replace("${assets_root}", str(self.minecraft_dir / "assets"))
                        arg = arg.replace("${assets_index_name}", version_data.get("assetIndex", {}).get("id", version_id))
                        arg = arg.replace("${auth_uuid}", uuid)
                        if not access_token:
                            # 离线模式
                            arg = arg.replace("${auth_access_token}", "000000")
                            arg = arg.replace("${user_type}", "mojang")
                            arg = arg.replace("${user_properties}", "{}")
                        else:
                            # 正版模式
                            arg = arg.replace("${auth_access_token}", access_token)
                            arg = arg.replace("${user_type}", "msa")
                            arg = arg.replace("${user_properties}", "{}")
                            
                        arg = arg.replace("${version_type}", version_data.get("type", "release"))
                        arg = arg.replace("${clientid}", "FlowerGame")
                        arg = arg.replace("${auth_xuid}", "")
                        # 跳过包含未替换占位符的参数
                        if "${" in arg:
                            logger.debug(f"跳过包含未替换占位符的参数: {arg}")
                            continue
                        # 跳过空参数
                        if not arg or arg.isspace():
                            logger.debug(f"跳过空参数")
                            continue
                        # 跳过可能导致冲突的快速游戏参数
                        if arg in ["--demo", "--width", "--height", "--quickPlayPath", "--quickPlaySingleplayer", "--quickPlayMultiplayer", "--quickPlayRealms"]:
                            logger.debug(f"跳过可能导致冲突的参数: {arg}")
                            continue
                        game_args.append(arg)
                        logger.debug(f"添加游戏参数: {arg}")
                    elif isinstance(arg, dict) and "value" in arg:
                        # 处理带有规则的参数
                        if self._evaluate_rules(arg.get("rules", [])):
                            value = arg["value"]
                            if isinstance(value, list):
                                # 处理列表值，替换占位符
                                processed_values = []
                                for v in value:
                                    v = v.replace("${auth_player_name}", username)
                                    v = v.replace("${version_name}", version_id)
                                    v = v.replace("${game_directory}", str(version_game_dir))  # 版本隔离
                                    v = v.replace("${assets_root}", str(self.minecraft_dir / "assets"))
                                    v = v.replace("${assets_index_name}", version_data.get("assetIndex", {}).get("id", version_id))
                                    v = v.replace("${auth_uuid}", uuid)
                                    if not access_token:
                                        # 离线模式
                                        v = v.replace("${auth_access_token}", "000000")
                                        v = v.replace("${user_type}", "mojang") # HMCL/PCL 使用 mojang 类型以兼容
                                        v = v.replace("${user_properties}", "{}")
                                    else:
                                        # 正版模式
                                        v = v.replace("${auth_access_token}", access_token)
                                        v = v.replace("${user_type}", "msa")
                                        v = v.replace("${user_properties}", "{}") # 通常为空
                                    
                                    v = v.replace("${version_type}", version_data.get("type", "release"))
                                    v = v.replace("${clientid}", "FlowerGame")
                                    v = v.replace("${auth_xuid}", "")
                                    # 跳过包含未替换占位符的参数
                                    if "${" in v:
                                        logger.debug(f"跳过包含未替换占位符的参数列表项: {v}")
                                        continue
                                    # 跳过空参数
                                    if not v or v.isspace():
                                        logger.debug(f"跳过空参数列表项")
                                        continue
                                    # 跳过可能导致冲突的快速游戏参数
                                    if v in ["--demo", "--width", "--height", "--quickPlayPath", "--quickPlaySingleplayer", "--quickPlayMultiplayer", "--quickPlayRealms"]:
                                        logger.debug(f"跳过可能导致冲突的参数列表项: {v}")
                                        continue
                                    processed_values.append(v)
                                    logger.debug(f"添加游戏参数列表项: {v}")
                                game_args.extend(processed_values)
                            else:
                                # 处理单个值，替换占位符（版本隔离）
                                value = value.replace("${auth_player_name}", username)
                                value = value.replace("${version_name}", version_id)
                                value = value.replace("${game_directory}", str(version_game_dir))  # 版本隔离
                                value = value.replace("${assets_root}", str(self.minecraft_dir / "assets"))
                                value = value.replace("${assets_index_name}", version_data.get("assetIndex", {}).get("id", version_id))
                                value = value.replace("${auth_uuid}", uuid)
                                if not access_token:
                                    # 离线模式
                                    value = value.replace("${auth_access_token}", "000000")
                                    value = value.replace("${user_type}", "mojang")
                                    value = value.replace("${user_properties}", "{}")
                                else:
                                    # 正版模式
                                    value = value.replace("${auth_access_token}", access_token)
                                    value = value.replace("${user_type}", "msa")
                                    value = value.replace("${user_properties}", "{}")
                                    
                                value = value.replace("${version_type}", version_data.get("type", "release"))
                                value = value.replace("${clientid}", "FlowerGame")
                                value = value.replace("${auth_xuid}", "")
                                # 跳过包含未替换占位符的参数
                                if "${" in value:
                                    logger.debug(f"跳过包含未替换占位符的参数值: {value}")
                                    continue
                                # 跳过可能导致冲突的快速游戏参数
                                if value in ["--demo", "--width", "--height", "--quickPlayPath", "--quickPlaySingleplayer", "--quickPlayMultiplayer", "--quickPlayRealms"]:
                                    logger.debug(f"跳过可能导致冲突的参数值: {value}")
                                    continue
                                # 跳过空参数
                                if not value or (isinstance(value, str) and value.isspace()):
                                    logger.debug(f"跳过空参数值")
                                    continue
                                game_args.append(str(value))
                                logger.debug(f"添加游戏参数值: {value}")
            
            # 添加额外的游戏参数
            for arg in extra_game_args:
                game_args.append(arg)
                logger.debug(f"添加额外游戏参数: {arg}")
            
            # 注意: Minecraft 1.21+ 不再支持 --lang 命令行参数
            # 语言设置只能通过 options.txt 文件来配置
            # 我们已经在 _ensure_chinese_language() 方法中处理了这个问题
            
            # 合并所有命令
            command.extend(game_args)
            
            # 确保所有参数都是字符串
            command = [str(arg) for arg in command]
            
            logger.info(f"完整启动命令: {' '.join(command)}")
            
            return command
            
        except Exception as e:
            logger.error(f"构建启动命令时发生异常: {e}", exc_info=True)
            return None

    def _evaluate_rules(self, rules: List[Dict]) -> bool:
        """
        评估规则列表，判断是否应该应用参数
        Minecraft 参数规则逻辑：
        - 只要有一条规则匹配（action=allow），则允许
        - 如果所有规则都不匹配，且没有明确的 allow 规则，则不允许
        - 或者，默认允许，除非被禁止？
        
        实际上，Mojang 的逻辑是：
        1. 默认 is_allowed = False (如果 rules 不为空)
        2. 遍历每条 rule
        3. 如果 rule 匹配当前环境
           - 如果 action == "allow"，则 is_allowed = True
           - 如果 action == "disallow"，则 is_allowed = False
        4. 返回 is_allowed
        """
        if not rules:
            return True
            
        is_allowed = False # 只要有规则，默认就是不允许，必须显式 allow
        
        for rule in rules:
            action = rule.get("action", "allow")
            
            match = True # 假设这条规则匹配
            
            if "os" in rule:
                os_rule = rule["os"]
                os_name = os_rule.get("name")
                os_version = os_rule.get("version")
                os_arch = os_rule.get("arch")
                
                if os_name:
                    current_os = "windows" if platform.system() == "Windows" else "linux" if platform.system() == "Linux" else "osx"
                    if os_name == "osx" and platform.system() == "Darwin":
                        pass # 匹配
                    elif os_name != current_os:
                        match = False
                        
                if os_arch:
                    current_arch = platform.machine().lower()
                    if os_arch == "x86" and current_arch in ["i386", "i686", "x86"]:
                        pass # 匹配
                    elif os_arch != current_arch:
                        match = False
            
            elif "features" in rule:
                # 特性规则，暂不支持特性，视为不匹配
                match = False
                
            if match:
                if action == "allow":
                    is_allowed = True
                elif action == "disallow":
                    is_allowed = False
                    
        return is_allowed
    
    def _build_classpath(self, version_data: Dict, version_id: str) -> str:
        """
        构建类路径（支持 inheritsFrom 继承）
        
        Args:
            version_data: 版本 JSON 数据
            version_id: 版本 ID
            
        Returns:
            类路径字符串
        """
        try:
            classpath_entries = []
            
            # 如果有 inheritsFrom，先加载父版本的 libraries
            inherits_from = version_data.get("inheritsFrom")
            if inherits_from:
                logger.info(f"🔗 检测到 inheritsFrom: {inherits_from}，加载父版本配置...")
                parent_json_path = self.minecraft_dir / "versions" / inherits_from / f"{inherits_from}.json"
                
                if parent_json_path.exists():
                    try:
                        with open(parent_json_path, "r", encoding="utf-8") as f:
                            parent_data = json.load(f)
                        
                        # 添加父版本的 JAR
                        parent_jar = self.minecraft_dir / "versions" / inherits_from / f"{inherits_from}.jar"
                        if parent_jar.exists():
                            classpath_entries.append(str(parent_jar))
                            logger.info(f"✅ 已添加父版本 JAR: {parent_jar.name}")
                        
                        # 添加父版本的 libraries
                        parent_libraries = parent_data.get("libraries", [])
                        logger.info(f"📦 父版本有 {len(parent_libraries)} 个依赖库")
                        self._add_libraries_to_classpath(parent_libraries, classpath_entries)
                        
                    except Exception as e:
                        logger.error(f"读取父版本 JSON 失败: {e}")
                else:
                    logger.warning(f"父版本 JSON 不存在: {parent_json_path}")
            else:
                # 没有 inheritsFrom，添加当前版本的 JAR
                version_dir = self.minecraft_dir / "versions" / version_id
                jar_files = list(version_dir.glob("*.jar"))
                
                if jar_files:
                    classpath_entries.append(str(jar_files[0]))
                    logger.info(f"✅ 已添加当前版本 JAR: {jar_files[0].name}")
                else:
                    logger.warning(f"⚠️ 未找到JAR文件: {version_dir}")
            
            # 添加当前版本的 libraries
            current_libraries = version_data.get("libraries", [])
            logger.info(f"📦 当前版本有 {len(current_libraries)} 个依赖库")
            self._add_libraries_to_classpath(current_libraries, classpath_entries)
            
            # 根据操作系统选择分隔符
            separator = ";" if platform.system() == "Windows" else ":"
            classpath = separator.join(classpath_entries)
            logger.info(f"✅ Classpath 共 {len(classpath_entries)} 个条目")
            return classpath
            
        except Exception as e:
            logger.error(f"构建类路径时发生异常: {e}", exc_info=True)
            return ""
    
    def _add_libraries_to_classpath(self, libraries: List[Dict], classpath_entries: List[str]):
        """
        将 libraries 添加到 classpath（带去重，同一库只保留最新版本）
        
        Args:
            libraries: 依赖库列表
            classpath_entries: classpath 条目列表
        """
        # 记录已添加的库（key: groupId:artifactId, value: 库路径）
        added_libs = {}
        
        for lib in libraries:
            # 检查规则
            if not self._evaluate_rules(lib.get("rules", [])):
                continue
            
            # 获取下载信息
            downloads = lib.get("downloads", {})
            artifact = downloads.get("artifact", {})
            name = lib.get("name", "")
            
            lib_path = None
            
            # 处理标准格式（MC原版库）
            if artifact and "path" in artifact:
                path = artifact.get("path")
                if path:
                    lib_path = self.minecraft_dir / "libraries" / path
            # 处理Fabric格式（只有name字段）
            elif name:
                # 解析Maven名称获取路径
                lib_path = self._get_library_path_from_name(name)
            
            if not lib_path or not lib_path.exists():
                if lib_path:
                    logger.warning(f"库文件不存在: {lib_path}")
                continue
            
            # 智能去重：
            # 1. 对于natives变体（如natives-windows）：不去重，全部保留
            # 2. 对于相同库不同版本（如asm:9.6 vs asm:9.9）：去重，保留新版本
            if name:
                parts = name.split(":")
                if len(parts) >= 3:
                    groupId = parts[0]
                    artifactId = parts[1]
                    version = parts[2]
                    classifier = parts[3] if len(parts) >= 4 else None
                    
                    # 如果有classifier（如natives-windows），使用完整name作为key（不去重）
                    if classifier:
                        base_name = name
                    else:
                        # 没有classifier，使用 groupId:artifactId 作为key（去重同名库的不同版本）
                        base_name = f"{groupId}:{artifactId}"
                    
                    # 检查是否已有同名库
                    if base_name in added_libs:
                        old_path = added_libs[base_name]
                        # 比较版本，保留较新的（后面的覆盖前面的）
                        if str(old_path) in classpath_entries:
                            classpath_entries.remove(str(old_path))
                            logger.info(f"⚠️ 库冲突，替换: {old_path.name} -> {lib_path.name}")
                    
                    added_libs[base_name] = lib_path
            
            # 添加到classpath
            if str(lib_path) not in classpath_entries:
                classpath_entries.append(str(lib_path))
    
    def _get_library_path_from_name(self, name: str) -> Optional[Path]:
        """
        从 Maven 名称解析库文件路径
        格式: groupId:artifactId:version[:classifier]
        例如: net.fabricmc:fabric-loader:0.16.10
        
        Args:
            name: Maven 名称
            
        Returns:
            库文件路径
        """
        try:
            parts = name.split(":")
            if len(parts) < 3:
                return None
            
            group = parts[0]
            artifact = parts[1]
            version = parts[2]
            classifier = parts[3] if len(parts) > 3 else None
            
            # 构建路径
            group_path = group.replace(".", "/")
            
            if classifier:
                file_name = f"{artifact}-{version}-{classifier}.jar"
            else:
                file_name = f"{artifact}-{version}.jar"
            
            lib_path = self.minecraft_dir / "libraries" / group_path / artifact / version / file_name
            return lib_path
            
        except Exception as e:
            logger.error(f"解析库名称时发生异常: {e}")
            return None
