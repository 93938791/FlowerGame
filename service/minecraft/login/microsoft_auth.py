"""
Microsoft身份认证模块
实现Minecraft Microsoft身份认证流程
参考: https://blog.goodboyboy.top/posts/2111486279.html
"""
import json
import requests
import webbrowser
import urllib.parse
from typing import Optional, Dict, Tuple
from utils.logger import Logger
from service.cache.config_cache import ConfigCache

logger = Logger().get_logger("MicrosoftAuth")


class MicrosoftAuth:
    """Microsoft身份认证类"""
    
    # 默认Microsoft OAuth配置
    DEFAULT_CLIENT_ID = "569b50db-d433-4261-9a40-d7e99c041ff1"  # 花韵喵城应用
    DEFAULT_REDIRECT_URI = "https://login.live.com/oauth20_desktop.srf"
    SCOPE = "service::user.auth.xboxlive.com::MBI_SSL"
    
    # API端点
    AUTHORIZE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
    TOKEN_URL = "https://login.live.com/oauth20_token.srf"
    DEVICE_CODE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
    DEVICE_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    XBOX_LIVE_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
    XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
    MINECRAFT_AUTH_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
    MINECRAFT_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"
    
    def __init__(self, client_id: str = '', redirect_uri: str = ''):
        """
        初始化认证类
        
        Args:
            client_id: Client ID，如果为空字符串则使用默认值
            redirect_uri: 重定向URI，如果为空字符串则使用默认值
        """
        # 使用自定义配置或默认配置
        self.client_id = client_id if client_id else self.DEFAULT_CLIENT_ID
        self.redirect_uri = redirect_uri if redirect_uri else self.DEFAULT_REDIRECT_URI
        
        self.access_token = None
        self.xbox_live_token = None
        self.xsts_token = None
        self.user_hash = None
        self.minecraft_token = None
        self.minecraft_profile = None
        self.offline_account = None  # 离线账号
        
        # 启动时从统一配置加载认证信息
        self._load_auth_config()
    
    def get_authorization_url(self) -> str:
        """
        获取Microsoft授权URL
        
        Returns:
            授权URL字符串
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": self.SCOPE
        }
        
        url = f"{self.AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
        logger.info(f"生成授权URL: {url[:100]}...")
        return url
    
    def get_device_code(self) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        获取设备代码（Device Code Flow）
        
        Returns:
            (success, error, device_code_data)
            device_code_data 包含:
            - user_code: 用户需要输入的代码
            - device_code: 设备代码（用于轮询）
            - verification_uri: 验证URL
            - expires_in: 过期时间（秒）
            - interval: 轮询间隔（秒）
        """
        try:
            data = {
                "client_id": self.client_id,
                "scope": "XboxLive.signin XboxLive.offline_access"
            }
            
            logger.info("正在获取设备代码...")
            response = requests.post(self.DEVICE_CODE_URL, data=data, timeout=30)
            
            # 记录详细错误信息
            if response.status_code != 200:
                logger.error(f"设备代码请求失败: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            
            device_code_data = {
                "user_code": result.get("user_code"),
                "device_code": result.get("device_code"),
                "verification_uri": result.get("verification_uri"),
                "expires_in": result.get("expires_in", 900),
                "interval": result.get("interval", 5),
                "message": result.get("message", "")
            }
            
            logger.info(f"✅ 成功获取设备代码: {device_code_data['user_code']}")
            return True, None, device_code_data
            
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"获取设备代码失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def poll_device_token(self, device_code: str, interval: int = 5) -> Tuple[bool, Optional[str]]:
        """
        轮询设备令牌（等待用户完成授权）
        
        Args:
            device_code: 设备代码
            interval: 轮询间隔（秒）
            
        Returns:
            (success, error)
        """
        try:
            data = {
                "client_id": self.client_id,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code
            }
            
            logger.info("正在轮询设备令牌...")
            response = requests.post(self.DEVICE_TOKEN_URL, data=data, timeout=30)
            
            # 检查响应
            if response.status_code == 400:
                result = response.json()
                error = result.get("error", "")
                
                if error == "authorization_pending":
                    # 用户还未完成授权
                    return False, "authorization_pending"
                elif error == "authorization_declined":
                    return False, "用户拒绝了授权"
                elif error == "expired_token":
                    return False, "设备代码已过期"
                elif error == "bad_verification_code":
                    return False, "无效的设备代码"
                else:
                    return False, f"授权错误: {error}"
            
            response.raise_for_status()
            result = response.json()
            
            self.access_token = result.get("access_token")
            
            if not self.access_token:
                error_msg = "响应中未找到access_token"
                logger.error(error_msg)
                return False, error_msg
            
            logger.info("✅ 成功获取Microsoft令牌")
            return True, None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"轮询设备令牌失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def authenticate_with_device_code(self, device_code: str, max_attempts: int = 180, interval: int = 5) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        使用设备代码执行完整的认证流程
        
        Args:
            device_code: 设备代码
            max_attempts: 最大轮询次数（默认180次，15分钟）
            interval: 轮询间隔（秒）
            
        Returns:
            (success, error, profile)
        """
        import time
        
        logger.info("开始设备代码认证流程...")
        
        # 步骤1: 轮询获取Microsoft令牌
        for attempt in range(max_attempts):
            success, error = self.poll_device_token(device_code, interval)
            
            if success:
                break
            elif error == "authorization_pending":
                # 等待用户授权
                time.sleep(interval)
                continue
            else:
                # 其他错误，直接返回
                return False, error, None
        else:
            return False, "超时：用户未在规定时间内完成授权", None
        
        # 步骤2: 获取Xbox Live令牌
        success, error = self.get_xbox_live_token()
        if not success:
            return False, error, None
        
        # 步骤3: 获取XSTS令牌
        success, error = self.get_xsts_token()
        if not success:
            return False, error, None
        
        # 步骤4: 获取Minecraft令牌
        success, error = self.get_minecraft_token()
        if not success:
            return False, error, None
        
        # 步骤5: 获取Minecraft用户资料
        success, error, profile = self.get_minecraft_profile()
        if not success:
            return False, error, None
        
        logger.info("✅ 设备代码认证流程完成")
        return True, None, profile
    
    def extract_code_from_url(self, url: str) -> Optional[str]:
        """
        从回调URL中提取授权代码
        
        Args:
            url: 回调URL
            
        Returns:
            授权代码，如果提取失败返回None
        """
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get('code', [None])[0]
            if code:
                logger.info("成功提取授权代码")
                return code
            else:
                logger.warning("URL中未找到授权代码")
                return None
        except Exception as e:
            logger.error(f"提取授权代码失败: {e}")
            return None
    
    def get_microsoft_token(self, auth_code: str) -> Tuple[bool, Optional[str]]:
        """
        使用授权代码获取Microsoft令牌
        
        Args:
            auth_code: Microsoft授权代码
            
        Returns:
            (成功标志, 错误信息或None)
        """
        try:
            data = {
                "client_id": self.client_id,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "scope": self.SCOPE
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            logger.info("正在获取Microsoft令牌...")
            response = requests.post(self.TOKEN_URL, data=data, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            self.access_token = result.get("access_token")
            
            if not self.access_token:
                error_msg = "响应中未找到access_token"
                logger.error(error_msg)
                return False, error_msg
            
            logger.info("✅ 成功获取Microsoft令牌")
            return True, None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"获取Microsoft令牌失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_xbox_live_token(self) -> Tuple[bool, Optional[str]]:
        """
        使用Microsoft令牌获取Xbox Live令牌
        
        Returns:
            (成功标志, 错误信息或None)
        """
        try:
            if not self.access_token:
                error_msg = "缺少Microsoft令牌"
                logger.error(error_msg)
                return False, error_msg
            
            # Xbox Live 需要带 d= 前缀的 RpsTicket
            rps_ticket = f"d={self.access_token}"
            
            payload = {
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": rps_ticket
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            logger.info("正在获取Xbox Live令牌...")
            response = requests.post(
                self.XBOX_LIVE_AUTH_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            # 记录详细错误信息
            if response.status_code != 200:
                logger.error(f"Xbox Live请求失败: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            self.xbox_live_token = result.get("Token")
            
            # 提取User Hash
            display_claims = result.get("DisplayClaims", {})
            xui = display_claims.get("xui", [])
            if xui and len(xui) > 0:
                self.user_hash = xui[0].get("uhs")
            
            if not self.xbox_live_token:
                error_msg = "响应中未找到Xbox Live令牌"
                logger.error(error_msg)
                return False, error_msg
            
            if not self.user_hash:
                error_msg = "响应中未找到User Hash"
                logger.error(error_msg)
                return False, error_msg
            
            logger.info("✅ 成功获取Xbox Live令牌")
            return True, None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"获取Xbox Live令牌失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_xsts_token(self) -> Tuple[bool, Optional[str]]:
        """
        使用Xbox Live令牌获取XSTS令牌
        
        Returns:
            (成功标志, 错误信息或None)
        """
        try:
            if not self.xbox_live_token:
                error_msg = "缺少Xbox Live令牌"
                logger.error(error_msg)
                return False, error_msg
            
            payload = {
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [self.xbox_live_token]
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            logger.info("正在获取XSTS令牌...")
            response = requests.post(
                self.XSTS_AUTH_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            self.xsts_token = result.get("Token")
            
            if not self.xsts_token:
                error_msg = "响应中未找到XSTS令牌"
                logger.error(error_msg)
                return False, error_msg
            
            logger.info("✅ 成功获取XSTS令牌")
            return True, None
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e}"
            logger.error(error_msg)
            # XSTS认证可能返回401，需要特殊处理
            response = e.response
            if response and response.status_code == 401:
                try:
                    error_data = response.json()
                    error_code = error_data.get("XErr", "")
                    if error_code == "2148916233":
                        error_msg = "此Microsoft账号未拥有Minecraft，请先购买游戏"
                    elif error_code == "2148916235":
                        error_msg = "此账号所在地区不支持Xbox Live服务"
                    elif error_code == "2148916236":
                        error_msg = "需要家长同意才能使用Xbox Live服务"
                    elif error_code == "2148916238":
                        error_msg = "此账号需要完成年龄验证"
                    else:
                        error_msg = f"XSTS认证失败 (错误代码: {error_code})"
                except:
                    pass
            return False, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"获取XSTS令牌失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_minecraft_token(self) -> Tuple[bool, Optional[str]]:
        """
        使用XSTS令牌获取Minecraft令牌
        
        Returns:
            (成功标志, 错误信息或None)
        """
        try:
            if not self.xsts_token or not self.user_hash:
                error_msg = "缺少XSTS令牌或User Hash"
                logger.error(error_msg)
                return False, error_msg
            
            identity_token = f"XBL3.0 x={self.user_hash};{self.xsts_token}"
            
            payload = {
                "identityToken": identity_token
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            logger.info("正在获取Minecraft令牌...")
            response = requests.post(
                self.MINECRAFT_AUTH_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            self.minecraft_token = result.get("access_token")
            
            if not self.minecraft_token:
                error_msg = "响应中未找到Minecraft令牌"
                logger.error(error_msg)
                return False, error_msg
            
            logger.info("✅ 成功获取Minecraft令牌")
            return True, None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"获取Minecraft令牌失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_minecraft_profile(self) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        获取Minecraft用户资料
        
        Returns:
            (成功标志, 错误信息或None, 用户资料或None)
        """
        try:
            if not self.minecraft_token:
                error_msg = "缺少Minecraft令牌"
                logger.error(error_msg)
                return False, error_msg, None
            
            headers = {
                "Authorization": f"Bearer {self.minecraft_token}",
                "Content-Type": "application/json"
            }
            
            logger.info("正在获取Minecraft用户资料...")
            response = requests.get(
                self.MINECRAFT_PROFILE_URL,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            self.minecraft_profile = result
            
            logger.info(f"✅ 成功获取Minecraft用户资料: {result.get('name', 'Unknown')}")
            return True, None, result
            
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"获取Minecraft用户资料失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def authenticate(self, auth_code: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        执行完整的认证流程
        
        Args:
            auth_code: Microsoft授权代码
            
        Returns:
            (成功标志, 错误信息或None, 用户资料或None)
        """
        logger.info("开始Microsoft身份认证流程...")
        
        # 步骤1: 获取Microsoft令牌
        success, error = self.get_microsoft_token(auth_code)
        if not success:
            return False, error, None
        
        # 步骤2: 获取Xbox Live令牌
        success, error = self.get_xbox_live_token()
        if not success:
            return False, error, None
        
        # 步骤3: 获取XSTS令牌
        success, error = self.get_xsts_token()
        if not success:
            return False, error, None
        
        # 步骤4: 获取Minecraft令牌
        success, error = self.get_minecraft_token()
        if not success:
            return False, error, None
        
        # 步骤5: 获取Minecraft用户资料
        success, error, profile = self.get_minecraft_profile()
        if not success:
            return False, error, None
        
        logger.info("✅ Microsoft身份认证流程完成")
        return True, None, profile
    
    def get_auth_info(self) -> Dict:
        """
        获取当前认证信息
        
        Returns:
            包含认证信息的字典
        """
        return {
            "ok": self.minecraft_profile is not None or self.offline_account is not None,
            "has_access_token": self.access_token is not None,
            "has_xbox_live_token": self.xbox_live_token is not None,
            "has_xsts_token": self.xsts_token is not None,
            "has_minecraft_token": self.minecraft_token is not None,
            "user_hash": self.user_hash,
            "profile": self.minecraft_profile,
            "offline_account": self.offline_account
        }
    
    def _load_auth_config(self):
        """从统一配置加载认证信息"""
        try:
            auth_info = ConfigCache.get_auth_info()
            self.minecraft_profile = auth_info.get('profile')
            self.offline_account = auth_info.get('offline_account')
            if self.minecraft_profile:
                logger.info(f"已从配置文件恢复正版账号: {self.minecraft_profile.get('name')}")
            if self.offline_account:
                logger.info(f"已从配置文件恢复离线账号: {self.offline_account}")
        except Exception as e:
            logger.error(f"加载认证配置失败: {e}")
    
    def save_profile(self, profile: Dict):
        """保存正版账号信息"""
        self.minecraft_profile = profile
        self.offline_account = None  # 清除离线账号
        ConfigCache.save_profile(profile)
    
    def save_offline_account(self, username: str):
        """保存离线账号信息"""
        self.offline_account = username
        self.minecraft_profile = None  # 清除正版账号
        ConfigCache.save_offline_account(username)
    
    def clear_profile(self):
        """清除正版账号信息"""
        self.minecraft_profile = None
        self.access_token = None
        self.xbox_live_token = None
        self.xsts_token = None
        self.user_hash = None
        self.minecraft_token = None
        ConfigCache.clear_profile()
    
    def clear_offline_account(self):
        """清除离线账号信息"""
        self.offline_account = None
        ConfigCache.clear_offline_account()
