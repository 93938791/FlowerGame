from pathlib import Path
import subprocess
import os
import platform
import winreg
from typing import List, Dict, Optional
from utils.logger import logger
from service.minecraft.download.http_downloader import HttpDownloader

class JavaManager:
    def __init__(self):
        self.downloader = HttpDownloader()
        # Adoptium Temurin 17 (LTS) - Windows x64 .msi (TUNA Mirror)
        self.java_download_url = "https://mirrors.tuna.tsinghua.edu.cn/Adoptium/17/jdk/x64/windows/OpenJDK17U-jdk_x64_windows_hotspot_17.0.17_10.msi"
        self.installer_name = "OpenJDK17U-jdk_x64_windows_hotspot_17.0.17_10.msi"

    def get_java_info(self) -> Dict:
        """
        获取 Java 环境信息
        """
        paths = self._find_java_paths()
        java_home = os.environ.get("JAVA_HOME", "")
        
        best_version = "未知"
        best_path = ""
        best_major_version = -1
        
        found_javas = []

        for path in paths:
            version = self._get_java_version(path)
            if version:
                major = self._parse_major_version(version)
                found_javas.append({
                    "path": path,
                    "version": version,
                    "major_version": major
                })
                
                if major > best_major_version:
                    best_major_version = major
                    best_version = version
                    best_path = path
        
        # 如果没有找到任何版本，状态为未安装
        installed = len(found_javas) > 0
        
        # 推荐标准：至少有一个 Java 17+
        recommended = any(j['major_version'] >= 17 for j in found_javas)

        return {
            "installed": installed,
            "paths": [j['path'] for j in found_javas],
            "details": found_javas,
            "java_home": java_home,
            "version": best_version, # 返回最高版本
            "current_path": best_path,
            "recommended_installed": recommended
        }

    def _get_java_version(self, java_path: str) -> Optional[str]:
        try:
            # 尝试获取版本
            # 优先尝试 -version (虽然某些版本支持 --version, 但 -version 更通用)
            # 某些发行版标准输出在 stderr，有些在 stdout
            
            # 使用 startupinfo 隐藏窗口
            startupinfo = None
            creationflags = 0
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                # 使用 CREATE_NO_WINDOW 标志
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [java_path, "-version"], 
                capture_output=True, 
                text=True, 
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            output = result.stderr + result.stdout # 混合输出
            
            import re
            # 匹配 "1.8.0_202" 或 "17.0.1" 或 "21.0.2"
            match = re.search(r'(?:java|openjdk) version "([^"]+)"', output)
            if match:
                return match.group(1)
            
            # 匹配不带引号的 (e.g. openjdk 17) 或 "java 21.0.7"
            match = re.search(r'(?:java|openjdk)\s+(\d+(?:\.\d+)*)', output)
            if match:
                return match.group(1)

            # 增加更宽泛的匹配，防止漏网
            # 匹配 "21.0.2" 这样的纯数字版本号出现在开头
            match = re.search(r'(\d+\.\d+\.\d+)', output)
            if match:
                return match.group(1)
                
            return None
        except Exception as e:
            logger.debug(f"获取 Java 版本失败 {java_path}: {e}")
            return None

    def _parse_major_version(self, version_str: str) -> int:
        try:
            # 移除可能的非数字前缀/后缀
            import re
            # 提取第一个数字部分
            match = re.search(r'^(\d+)(?:\.(\d+))?', version_str)
            if not match:
                return 0
                
            major = int(match.group(1))
            minor = int(match.group(2)) if match.group(2) else 0
            
            if major == 1: # 1.8.x -> 8
                return minor
            return major
        except:
            return 0

    def _find_java_paths(self) -> List[str]:
        """
        查找系统中所有的 java.exe 路径
        """
        java_paths = set()

        # 0. 检查当前进程的 PATH (可能需要重启才能生效，但还是查一下)
        try:
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            for d in path_dirs:
                java_exe = Path(d) / "java.exe"
                if java_exe.exists() and java_exe.is_file():
                    java_paths.add(str(java_exe))
        except Exception:
            pass

        # 2. 检查 JAVA_HOME
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            java_exe = Path(java_home) / "bin" / "java.exe"
            if java_exe.exists():
                java_paths.add(str(java_exe))

        # 3. 检查常见安装目录
        common_dirs = [
            Path("C:/Program Files/Java"),
            Path("C:/Program Files (x86)/Java"),
            Path("C:/Program Files/Eclipse Adoptium"),
            Path("C:/Program Files/Microsoft"), # Microsoft Build of OpenJDK
            Path("C:/Program Files/BellSoft"),  # Liberica JDK
            Path("C:/Program Files/Amazon Corretto"),
            Path("C:/Program Files/Zulu"),
            Path(os.environ.get("USERPROFILE", "")) / ".jdks", # IntelliJ IDEA
        ]
        
        # 尝试从 Config 获取 Minecraft 目录 (如果能导入)
        try:
            from config import Config
            if Config.MINECRAFT_DIR:
                common_dirs.append(Path(Config.MINECRAFT_DIR) / "runtime")
        except:
            pass

        # 去重
        common_dirs = list(set(common_dirs))
        
        for base_dir in common_dirs:
            if base_dir.exists():
                # 检查 base_dir 本身是否包含 bin/java.exe
                if (base_dir / "bin" / "java.exe").exists():
                    java_paths.add(str(base_dir / "bin" / "java.exe"))

                # 检查子目录
                try:
                    for child in base_dir.iterdir():
                        if child.is_dir():
                            # 检查 child/bin/java.exe
                            java_exe = child / "bin" / "java.exe"
                            if java_exe.exists():
                                java_paths.add(str(java_exe))
                            
                            # 针对 Minecraft runtime，可能还有一层 (runtime/java-runtime-alpha/windows-x64/java-runtime-alpha/bin/java.exe)
                            # 简单递归一层
                            try:
                                for subchild in child.iterdir():
                                    if subchild.is_dir():
                                        sub_java_exe = subchild / "bin" / "java.exe"
                                        if sub_java_exe.exists():
                                            java_paths.add(str(sub_java_exe))
                            except:
                                pass
                except Exception:
                    pass
        
        # 5. 注册表检查
        try:
            self._find_java_from_registry(java_paths)
        except Exception as e:
            logger.warning(f"注册表检测 Java 失败: {e}")

        return list(java_paths)

    def _find_java_from_registry(self, java_paths: set):
        """从注册表查找 Java"""
        import winreg
        
        search_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Runtime Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\JDK"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Development Kit"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\JDK"), # Microsoft OpenJDK
        ]
        
        for hkey, key_path in search_paths:
            try:
                with winreg.OpenKey(hkey, key_path) as key:
                    i = 0
                    while True:
                        try:
                            version = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, version) as subkey:
                                try:
                                    # 尝试读取 JavaHome
                                    java_home, _ = winreg.QueryValueEx(subkey, "JavaHome")
                                    java_exe = Path(java_home) / "bin" / "java.exe"
                                    if java_exe.exists():
                                        java_paths.add(str(java_exe))
                                except FileNotFoundError:
                                    pass
                            i += 1
                        except OSError:
                            break
            except FileNotFoundError:
                pass

    def _is_recommended_java_installed(self, java_paths: List[str]) -> bool:
        # 简单判断是否有 java
        return len(java_paths) > 0

    def download_java(self, save_dir: str) -> str:
        """
        下载 Java 安装包
        返回下载文件的路径
        """
        save_path = Path(save_dir) / self.installer_name
        
        logger.info(f"开始下载 Java: {self.java_download_url}")
        
        success = self.downloader.download_file(
            url=self.java_download_url,
            save_path=save_path,
            use_mirror=False # 直接源下载可能更稳定，或者考虑镜像
        )
        
        if success:
            return str(save_path)
        else:
            raise Exception("Java 下载失败")

    def install_java(self, installer_path: str):
        """
        静默安装 Java
        """
        installer_path = Path(installer_path)
        if not installer_path.exists():
            raise FileNotFoundError(f"安装包未找到: {installer_path}")
            
        logger.info(f"开始安装 Java: {installer_path}")
        
        # msiexec /i "path\to\jdk.msi" /quiet /norestart
        # 使用 start /wait 确保安装完成
        cmd = f'msiexec /i "{installer_path}" /quiet /norestart'
        
        try:
            subprocess.run(cmd, shell=True, check=True)
            logger.info("Java 安装命令执行完成")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Java 安装失败: {e}")
            raise e
