import threading
import webbrowser
import time
import os
import sys
import asyncio
from typing import Dict, Set
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from utils.logger import Logger
from utils.process_helper import ProcessHelper
from config import Config

# 业务模块
from service.minecraft.login.microsoft_auth import MicrosoftAuth
from service.minecraft.download import MinecraftDownloadManager, LoaderType, DownloadProgress
from service.minecraft.game_launcher import GameLauncher
from service.syncthing.syncthing_manager import SyncthingManager
from service.easytier.easytier_manager import EasytierManager
from service.cache.config_cache import ConfigCache

logger = Logger().get_logger("Main")

# Token 自动刷新工作线程
def token_refresh_worker():
    """后台线程：程序启动时检查并刷新 token"""
    logger.info("🔄 Token 刷新线程已启动")
    
    # 等待 5 秒，让程序完全启动
    time.sleep(5)
    
    try:
        # 检查并刷新 token
        success, error = _auth.check_and_refresh_token()
        if not success and error:
            logger.warning(f"⚠️ {error}")
    except Exception as e:
        logger.error(f"检查 token 失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())

# 单例服务实例
_auth = MicrosoftAuth()
_syncthing = SyncthingManager()
_easytier = EasytierManager()
# 注意：不在这里创建 _minecraft_downloader，因为需要等待用户配置目录

# 下载进度管理
_download_progress: Dict[str, DownloadProgress] = {}  # 按版本ID存储进度
_download_executor = None  # 全局下载线程池
_minecraft_dir = None  # 用户配置的 Minecraft 目录

def get_download_executor():
    """获取下载线程池（延迟初始化）"""
    global _download_executor
    if _download_executor is None:
        import concurrent.futures
        import os
        # 根据 CPU 核心数计算线程数（CPU核心数 + 2，最大不超过 16）
        cpu_count = os.cpu_count() or 4
        thread_count = min(cpu_count + 2, 16)
        logger.info(f"🔧 CPU 核心数: {cpu_count}, 下载线程数: {thread_count}")
        _download_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=thread_count,
            thread_name_prefix="MinecraftDownload"
        )
    return _download_executor

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：启动后台推送任务
    task = asyncio.create_task(broadcast_network_status())
    logger.info("后台 WebSocket 推送任务已启动")
    
    # 启动 token 自动刷新线程
    token_refresh_thread = threading.Thread(target=token_refresh_worker, daemon=True)
    token_refresh_thread.start()
    logger.info("后台 Token 刷新线程已启动")
    
    yield
    # 关闭时：取消任务
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title=Config.APP_NAME, version=Config.APP_VERSION, lifespan=lifespan)

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket 客户端已连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket 客户端已断开，当前连接数: {len(self.active_connections)}")
    
    async def broadcast(self, data: dict):
        """广播消息给所有连接的客户端"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                disconnected.add(connection)
        
        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

# 后台任务：定期推送网络状态
async def broadcast_network_status():
    """后台任务：定期推送网络状态给所有 WebSocket 客户端"""
    import concurrent.futures
    
    # 创建线程池用于执行同步操作
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    
    while True:
        try:
            if len(manager.active_connections) > 0:
                # 获取最新的网络状态
                status = {
                    "type": "status_update",
                    "data": {
                        "running": _easytier.process is not None,
                        "connected": _easytier.process is not None and ProcessHelper.is_process_running(_easytier.process),
                        "virtual_ip": _easytier.virtual_ip or "未连接"
                    }
                }
                
                # 在线程池中执行同步操作
                loop = asyncio.get_event_loop()
                
                # 获取设备列表（增加超时时间到10秒）
                peers = await loop.run_in_executor(executor, _easytier.discover_peers, 10)
                peers_data = {
                    "type": "peers_update",
                    "data": peers
                }
                # logger.info(f"获取到 {len(peers)} 个设备: {peers}")  # 已禁用日志
                
                # 获取流量统计
                traffic = await loop.run_in_executor(executor, _easytier.get_traffic_stats)
                traffic_data = {
                    "type": "traffic_update",
                    "data": traffic
                }
                
                # 广播所有数据
                await manager.broadcast(status)
                await manager.broadcast(peers_data)
                await manager.broadcast(traffic_data)
        except Exception as e:
            logger.error(f"广播网络状态失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        # 每5秒推送一次
        await asyncio.sleep(5)

def _resolve_web_dir():
    base_candidates = []
    # PyInstaller 打包后的临时目录
    if hasattr(sys, "_MEIPASS"):
        base_candidates.append(os.path.join(sys._MEIPASS, "web"))
    # 开发环境 Nuxt 构建产物
    base_candidates.append(os.path.join(os.getcwd(), "web", "app", ".output", "public"))
    # 纯HTML占位目录
    base_candidates.append(os.path.join(os.getcwd(), "web"))
    for p in base_candidates:
        if os.path.isdir(p):
            return p
    return os.path.join(os.getcwd(), "web")

web_dir = _resolve_web_dir()
app.mount("/web", StaticFiles(directory=web_dir, html=True), name="web")

@app.get("/web", response_class=HTMLResponse)
@app.get("/web/", response_class=HTMLResponse)
def web_spa_entry():
    index_path = os.path.join(web_dir, "index.html")
    fallback_path = os.path.join(os.getcwd(), "web", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    elif os.path.exists(fallback_path):
        return FileResponse(fallback_path)
    return HTMLResponse("<h3>前端资源未找到</h3>")

# 简易首页（Web UI 占位）
# 删除占位首页，改用 /web 提供的 Nuxt SPA

# 认证 API
@app.get("/api/auth/authorize-url")
def api_auth_authorize_url():
    url = _auth.get_authorization_url()
    return {"url": url}

@app.get("/api/auth/device-code")
def api_auth_device_code():
    """获取设备代码（Device Code Flow）"""
    ok, err, data = _auth.get_device_code()
    return {"ok": ok, "error": err, "data": data}

@app.post("/api/auth/device-auth")
async def api_auth_device_auth(payload: Dict):
    """使用设备代码认证（单次检查，不轮询）"""
    device_code = payload.get("device_code", "")
    if not device_code:
        return {"ok": False, "error": "缺少device_code参数", "profile": None}
    
    # 单次检查，不轮询
    ok, err = _auth.poll_device_token(device_code)
    
    if ok:
        # 获取到了token，继续完成剩余流程
        # 步骤2: 获取Xbox Live令牌
        success, error = _auth.get_xbox_live_token()
        if not success:
            return {"ok": False, "error": error, "profile": None}
        
        # 步骤3: 获取XSTS令牌
        success, error = _auth.get_xsts_token()
        if not success:
            return {"ok": False, "error": error, "profile": None}
        
        # 步骤4: 获取Minecraft令牌
        success, error = _auth.get_minecraft_token()
        if not success:
            return {"ok": False, "error": error, "profile": None}
        
        # 步骤5: 获取Minecraft用户资料
        success, error, profile = _auth.get_minecraft_profile()
        if not success:
            return {"ok": False, "error": error, "profile": None}
        
        # 自动保存账号信息
        _auth.save_profile(profile, _auth.minecraft_token, _auth.access_token, _auth.refresh_token)
        
        # 返回 profile 和 tokens
        return {
            "ok": True, 
            "authenticated": True,
            "error": None, 
            "profile": profile,
            "minecraft_token": _auth.minecraft_token,  # Minecraft token
            "access_token": _auth.access_token,  # Microsoft OAuth token
            "refresh_token": _auth.refresh_token  # Refresh token
        }
    else:
        # 返回错误（包括authorization_pending）
        return {"ok": False, "authenticated": False, "error": err, "profile": None}

@app.post("/api/auth/poll-device-token")
async def api_auth_poll_device_token(payload: Dict):
    """轮询设备令牌（前端使用的接口名称）"""
    return await api_auth_device_auth(payload)

@app.post("/api/auth/authenticate")
def api_auth_authenticate(payload: Dict):
    code = payload.get("auth_code", "")
    ok, err, profile = _auth.authenticate(code)
    # 返回 profile 和 tokens
    return {
        "ok": ok, 
        "error": err, 
        "profile": profile,
        "minecraft_token": _auth.minecraft_token if ok else None,  # Minecraft token
        "access_token": _auth.access_token if ok else None,  # Microsoft OAuth token
        "refresh_token": _auth.refresh_token if ok else None  # Refresh token
    }

@app.get("/api/auth/status")
def api_auth_status():
    return _auth.get_auth_info()

@app.get("/api/auth/profile-cache")
def api_auth_profile_cache():
    """读取正版账号缓存"""
    if _auth.minecraft_profile:
        return {
            "ok": True,
            "profile": _auth.minecraft_profile
        }
    return {"ok": False, "profile": None}

@app.get("/api/auth/offline-cache")
def api_auth_offline_cache():
    """读取离线账号缓存"""
    if _auth.offline_account:
        return {
            "ok": True,
            "username": _auth.offline_account
        }
    return {"ok": False, "username": None}

@app.post("/api/auth/save-profile")
def api_auth_save_profile(payload: Dict):
    """保存正版账号信息到配置文件"""
    profile = payload.get("profile")
    minecraft_token = payload.get("minecraft_token")
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if profile:
        _auth.save_profile(profile, minecraft_token, access_token, refresh_token)
        return {"ok": True, "message": "账号信息已保存"}
    return {"ok": False, "error": "缺profile参数"}

@app.post("/api/auth/save-offline")
def api_auth_save_offline(payload: Dict):
    """保存离线账号信息到配置文件"""
    username = payload.get("username")
    if username:
        _auth.save_offline_account(username)
        return {"ok": True, "message": "离线账号已保存"}
    return {"ok": False, "error": "缺少username参数"}

@app.post("/api/auth/clear-profile")
def api_auth_clear_profile():
    """清除正版账号信息"""
    _auth.clear_profile()
    return {"ok": True, "message": "账号信息已清除"}

@app.post("/api/auth/clear-offline")
def api_auth_clear_offline():
    """清除离线账号信息"""
    _auth.clear_offline_account()
    return {"ok": True, "message": "离线账号已清除"}

# Minecraft 下载 API
# Minecraft下载相关API已删除，等待重新规划

# Syncthing API
@app.post("/api/syncthing/start")
def api_syn_start():
    try:
        from config import Config
        if not Config.SYNCTHING_BIN.exists():
            return JSONResponse({
                "ok": False,
                "error": "Syncthing程序不存在",
                "expected_path": str(Config.SYNCTHING_BIN)
            }, status_code=400)
        _syncthing.start()
        return JSONResponse({"ok": True, "message": "Syncthing 启动完成"})
    except FileNotFoundError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"启动失败: {e}"}, status_code=500)

@app.post("/api/syncthing/stop")
def api_syn_stop():
    _syncthing.stop()
    return JSONResponse("Syncthing 已停止")

@app.get("/api/syncthing/device-id")
def api_syn_device_id():
    return {"device_id": _syncthing.get_device_id()}

@app.get("/api/syncthing/traffic")
def api_syn_traffic():
    return _syncthing.get_traffic_stats()

# Easytier API
@app.post("/api/easytier/start")
def api_et_start(request: Dict = Body(None)):
    try:
        from config import Config
        if not Config.EASYTIER_BIN.exists():
            return JSONResponse({
                "ok": False,
                "error": "Easytier程序不存在",
                "expected_path": str(Config.EASYTIER_BIN),
                "cli_expected_path": str(Config.EASYTIER_CLI)
            }, status_code=400)
        if not Config.EASYTIER_CLI.exists():
            return JSONResponse({
                "ok": False,
                "error": "easytier-cli 程序不存在",
                "expected_path": str(Config.EASYTIER_CLI)
            }, status_code=400)
        
        # 从请求中获取配置参数
        custom_peers = None
        network_name = None
        network_secret = None
        
        if request:
            custom_peers = request.get('peers')
            network_name = request.get('network_name')
            network_secret = request.get('network_secret')
        
        logger.info(f"收到启动请求 - 网络名称: {network_name}, 节点: {custom_peers}")
        
        ok = _easytier.start(
            custom_peers=custom_peers,
            network_name=network_name,
            network_secret=network_secret
        )
        
        if not ok:
            error_msg = "Easytier 启动失败。可能的原因：\n"
            error_msg += "1. 未以管理员权限运行（TUN模式需要管理员权限）\n"
            error_msg += "2. DLL依赖问题（wintun.dll、Packet.dll）\n"
            error_msg += "3. 端口被占用（11010、15888等）\n"
            error_msg += "4. 节点地址无效或无法连接\n"
            error_msg += "\n请查看后端控制台获取详细错误信息。"
            
            logger.error("Easytier 启动失败，详细错误信息已输出到控制台")
            return JSONResponse({"ok": False, "error": error_msg}, status_code=500)
        
        # 获取虚拟IP
        virtual_ip = _easytier.virtual_ip or "未分配"
        
        logger.info(f"Easytier 启动成功 - 虚拟IP: {virtual_ip}")
        
        return JSONResponse({
            "ok": True,
            "message": "Easytier 启动完成",
            "virtual_ip": virtual_ip
        })
    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": f"启动失败: {e}"}, status_code=500)

@app.post("/api/easytier/stop")
def api_et_stop():
    _easytier.stop()
    return JSONResponse({"ok": True, "message": "Easytier 已停止"})

@app.get("/api/easytier/status")
def api_et_status():
    """获取Easytier连接状态"""
    is_running = _easytier.process is not None
    virtual_ip = _easytier.virtual_ip or "未连接"
    
    return JSONResponse({
        "running": is_running,
        "virtual_ip": virtual_ip,
        "connected": is_running and virtual_ip not in ["未连接", "waiting...", "unknown"]
    })

@app.get("/api/easytier/peers")
def api_et_peers():
    """获取对等设备列表"""
    peers = _easytier.discover_peers()
    return JSONResponse(peers)

@app.get("/api/easytier/traffic")
def api_et_traffic():
    """获取流量统计"""
    return JSONResponse(_easytier.get_traffic_stats())

@app.get("/api/easytier/config")
def api_et_get_config():
    """获取当前配置（优先使用缓存配置）"""
    try:
        from config import Config
        
        # 从缓存读取用户自定义节点
        cached_nodes = ConfigCache.get_easytier_nodes()
        
        return JSONResponse({
            "network_name": Config.EASYTIER_NETWORK_NAME,
            "network_secret": Config.EASYTIER_NETWORK_SECRET,
            "peers": cached_nodes  # 只返回缓存的节点
        })
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return JSONResponse({
            "network_name": "",
            "network_secret": "",
            "peers": []
        })

@app.get("/api/easytier/nodes")
def api_et_get_nodes():
    """获取节点列表（从缓存读取）"""
    try:
        cached_nodes = ConfigCache.get_easytier_nodes()
        
        return JSONResponse({
            "nodes": cached_nodes,
            "is_custom": len(cached_nodes) > 0
        })
    except Exception as e:
        logger.error(f"获取节点列表失败: {e}")
        return JSONResponse({
            "nodes": [],
            "is_custom": False
        })

@app.post("/api/easytier/nodes/add")
def api_et_add_node(request: Dict = Body(...)):
    """添加节点"""
    try:
        node = request.get('node', '').strip()
        
        if not node:
            return JSONResponse({"ok": False, "error": "节点地址不能为空"}, status_code=400)
        
        # 验证节点格式
        if not node.startswith('tcp://') and not node.startswith('udp://') and not node.startswith('wg://'):
            return JSONResponse({"ok": False, "error": "节点地址必须以 tcp://, udp:// 或 wg:// 开头"}, status_code=400)
        
        success = ConfigCache.add_easytier_node(node)
        
        if success:
            return JSONResponse({"ok": True, "message": "节点添加成功"})
        else:
            return JSONResponse({"ok": False, "error": "节点已存在"}, status_code=400)
    except Exception as e:
        logger.error(f"添加节点失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/easytier/nodes/remove")
def api_et_remove_node(request: Dict = Body(...)):
    """删除节点"""
    try:
        node = request.get('node', '').strip()
        
        if not node:
            return JSONResponse({"ok": False, "error": "节点地址不能为空"}, status_code=400)
        
        success = ConfigCache.remove_easytier_node(node)
        
        if success:
            return JSONResponse({"ok": True, "message": "节点删除成功"})
        else:
            return JSONResponse({"ok": False, "error": "节点不存在"}, status_code=400)
    except Exception as e:
        logger.error(f"删除节点失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/easytier/nodes/reset")
def api_et_reset_nodes():
    """清空所有节点"""
    try:
        ConfigCache.save_easytier_nodes([])
        return JSONResponse({"ok": True, "message": "已清空所有节点"})
    except Exception as e:
        logger.error(f"清空节点失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/easytier/nodes/selected")
def api_et_get_selected_node():
    """获取当前选中的节点"""
    try:
        selected = ConfigCache.get_selected_node()
        return JSONResponse({"selected_node": selected})
    except Exception as e:
        logger.error(f"获取选中节点失败: {e}")
        return JSONResponse({"selected_node": None})

@app.post("/api/easytier/nodes/select")
def api_et_select_node(request: Dict = Body(...)):
    """选择当前使用的节点"""
    try:
        node = request.get('node')
        ConfigCache.set_selected_node(node)
        return JSONResponse({"ok": True, "message": "已选择节点"})
    except Exception as e:
        logger.error(f"选择节点失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/easytier/config")
def api_et_save_config(config: Dict):
    """保存配置（临时，仅本次运行有效）"""
    # 注意：这里只是临时保存，不持久化到文件
    return JSONResponse({"ok": True, "message": "配置已保存"})

# ==================== Minecraft 下载 API ====================

@app.get("/api/minecraft/config")
def api_mc_get_config():
    """获取 Minecraft 配置"""
    try:
        global _minecraft_dir
        # 如果没有配置，使用默认值
        if _minecraft_dir is None:
            from config import Config
            if not Config.is_configured():
                return JSONResponse({"ok": False, "error": "未配置 FlowerGame 目录"}, status_code=400)
            Config.init_dirs()
            _minecraft_dir = Config.MINECRAFT_DIR
        
        return JSONResponse({
            "ok": True,
            "minecraft_dir": str(_minecraft_dir)
        })
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/minecraft/config")
def api_mc_save_config(request: Dict = Body(...)):
    """保存 Minecraft 配置"""
    try:
        global _minecraft_dir
        
        minecraft_dir = request.get('minecraft_dir', '').strip()
        create_if_not_exists = request.get('create_if_not_exists', True)
        
        if not minecraft_dir:
            return JSONResponse({"ok": False, "error": "目录路径不能为空"}, status_code=400)
        
        from pathlib import Path
        mc_path = Path(minecraft_dir)
        
        # 如果目录不存在且允许创建，则创建它
        if not mc_path.exists() and create_if_not_exists:
            mc_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建 Minecraft 目录: {mc_path}")
        elif not mc_path.exists():
            return JSONResponse({"ok": False, "error": "目录不存在"}, status_code=400)
        
        # 保存到全局变量
        _minecraft_dir = mc_path
        logger.info(f"✅ Minecraft 目录已配置: {_minecraft_dir}")
        
        return JSONResponse({
            "ok": True,
            "message": "配置保存成功",
            "minecraft_dir": str(mc_path)
        })
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/minecraft/select-dir")
def api_mc_select_dir():
    """选择 Minecraft 目录（使用文件对话框）"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # 创建隐藏的 Tk 窗口
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        # 打开文件夹选择对话框
        selected_path = filedialog.askdirectory(
            title="选择 Minecraft 安装目录",
            initialdir=os.path.expanduser("~")
        )
        
        root.destroy()
        
        if not selected_path:
            return JSONResponse({"ok": False, "error": "用户取消选择"})
        
        return JSONResponse({
            "ok": True,
            "path": selected_path
        })
    except Exception as e:
        logger.error(f"选择目录失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/minecraft/versions")
def api_mc_list_versions(version_type: str = None):
    """列出所有可用的 Minecraft 版本"""
    try:
        # 使用临时下载管理器加载版本列表（不需要目录）
        temp_manager = MinecraftDownloadManager()
        try:
            versions = temp_manager.list_versions(version_type)
            return JSONResponse({
                "ok": True,
                "versions": versions,
                "total": len(versions)
            })
        finally:
            temp_manager.close()
    except Exception as e:
        logger.error(f"获取版本列表失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/minecraft/installed-versions")
def api_mc_list_installed_versions():
    """列出本地已安装的 Minecraft 版本"""
    try:
        # 获取用户配置的目录
        global _minecraft_dir
        mc_dir = _minecraft_dir
        
        if mc_dir is None:
            # 如果没有配置，使用默认目录
            from config import Config
            if not Config.is_configured():
                return JSONResponse({"ok": False, "error": "未配置 FlowerGame 目录"}, status_code=400)
            Config.init_dirs()
            mc_dir = Config.MINECRAFT_DIR
            logger.warning(f"⚠️ 未配置目录，使用默认: {mc_dir}")
        
        # 创建下载管理器实例
        manager = MinecraftDownloadManager(minecraft_dir=mc_dir)
        try:
            versions = manager.list_installed_versions()
            return JSONResponse({
                "ok": True,
                "versions": versions,
                "total": len(versions)
            })
        finally:
            manager.close()
    except Exception as e:
        logger.error(f"获取已安装版本列表失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/minecraft/loader-versions")
def api_mc_get_loader_versions(loader_type: str, mc_version: str):
    """获取加载器版本列表"""
    try:
        # 转换加载器类型
        loader_type_map = {
            "fabric": LoaderType.FABRIC,
            "forge": LoaderType.FORGE,
            "neoforge": LoaderType.NEOFORGE,
            "optifine": LoaderType.OPTIFINE
        }
        
        loader = loader_type_map.get(loader_type.lower())
        if not loader:
            return JSONResponse({"ok": False, "error": "不支持的加载器类型"}, status_code=400)
        
        # 创建临时下载管理器实例来获取加载器版本
        temp_manager = MinecraftDownloadManager()
        try:
            versions = temp_manager.get_loader_versions(loader, mc_version)
            
            if versions is None:
                return JSONResponse({"ok": False, "error": "获取加载器版本失败"}, status_code=500)
            
            return JSONResponse({
                "ok": True,
                "versions": versions,
                "total": len(versions)
            })
        finally:
            temp_manager.close()
    except Exception as e:
        logger.error(f"获取加载器版本失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/minecraft/download")
async def api_mc_download_vanilla(request: Dict = Body(...)):
    """下载原版 Minecraft"""
    try:
        version_id = request.get('version_id') or ''
        custom_name = request.get('custom_name') or ''
        
        # 安全地处理字符串
        version_id = version_id.strip() if version_id else ''
        custom_name = custom_name.strip() if custom_name else ''
        
        if not version_id:
            return JSONResponse({"ok": False, "error": "版本ID不能为空"}, status_code=400)
        
        if not custom_name:
            return JSONResponse({"ok": False, "error": "自定义名称不能为空"}, status_code=400)
        
        logger.info(f"📥 开始下载 Minecraft {version_id} -> {custom_name}")
        
        # 初始化进度（使用自定义名称作为key）
        _download_progress[custom_name] = DownloadProgress()
        
        def progress_callback(progress: DownloadProgress):
            _download_progress[custom_name] = progress
            logger.debug(f"[{progress.stage}] {progress.message}")
        
        def do_download():
            logger.info(f"🔄 下载线程已启动: {version_id} -> {custom_name}")
            
            # 获取用户配置的目录
            global _minecraft_dir
            mc_dir = _minecraft_dir
            
            if mc_dir is None:
                # 如果没有配置，返回错误
                from config import Config
                if not Config.is_configured():
                    return JSONResponse({"ok": False, "error": "未配置 FlowerGame 目录"}, status_code=400)
                Config.init_dirs()
                mc_dir = Config.MINECRAFT_DIR
                logger.warning(f"⚠️  未配置目录，使用默认: {mc_dir}")
            
            logger.info(f"📂 下载目录: {mc_dir}")
            
            # 创建新的下载管理器实例（使用用户配置的目录）
            manager = MinecraftDownloadManager(
                minecraft_dir=mc_dir,
                max_connections=50,
                progress_callback=progress_callback
            )
            try:
                success = manager.download_vanilla(version_id, custom_name)
                if success:
                    logger.info(f"✅ {custom_name} 下载成功")
                else:
                    logger.error(f"❌ {custom_name} 下载失败")
                return success
            except Exception as e:
                logger.error(f"❌ 下载异常: {e}", exc_info=True)
                return False
            finally:
                manager.close()
        
        # 提交到全局线程池
        executor = get_download_executor()
        future = executor.submit(do_download)
        logger.info(f"✓ 下载任务已提交到线程池")
        
        # 立即返回，不等待下载完成
        return JSONResponse({
            "ok": True,
            "message": f"开始下载 {version_id} -> {custom_name}",
            "version_id": custom_name  # 返回自定义名称作为 task_id
        })
    except Exception as e:
        logger.error(f"下载失败: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/minecraft/download-with-loader")
async def api_mc_download_with_loader(request: Dict = Body(...)):
    """下载带加载器的 Minecraft 版本"""
    try:
        mc_version = request.get('mc_version') or ''
        loader_type = request.get('loader_type') or ''
        loader_version = request.get('loader_version') or ''
        custom_name = request.get('custom_name')
        
        # 安全地处理字符串
        mc_version = mc_version.strip() if mc_version else ''
        loader_type = loader_type.strip() if loader_type else ''
        loader_version = loader_version.strip() if loader_version else ''
        custom_name = custom_name.strip() if custom_name else None
        
        if not all([mc_version, loader_type, loader_version]):
            return JSONResponse({"ok": False, "error": "参数不完整"}, status_code=400)
        
        # 转换加载器类型
        loader_type_map = {
            "fabric": LoaderType.FABRIC,
            "forge": LoaderType.FORGE,
            "neoforge": LoaderType.NEOFORGE,
            "optifine": LoaderType.OPTIFINE
        }
        
        loader = loader_type_map.get(loader_type.lower())
        if not loader:
            return JSONResponse({"ok": False, "error": "不支持的加载器类型"}, status_code=400)
        
        # 初始化进度
        task_id = f"{mc_version}-{loader_type}-{loader_version}"
        _download_progress[task_id] = DownloadProgress()
        
        def progress_callback(progress: DownloadProgress):
            _download_progress[task_id] = progress
        
        # 在后台线程中执行下载
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        
        def do_download():
            manager = MinecraftDownloadManager(
                max_connections=50,
                progress_callback=progress_callback
            )
            try:
                success = manager.download_with_loader(
                    mc_version, loader, loader_version, custom_name
                )
                return success
            finally:
                manager.close()
        
        future = executor.submit(do_download)
        
        return JSONResponse({
            "ok": True,
            "message": f"开始下载 {mc_version} + {loader_type} {loader_version}",
            "task_id": task_id
        })
    except Exception as e:
        logger.error(f"下载失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/minecraft/download-progress")
def api_mc_get_download_progress(task_id: str):
    """获取下载进度"""
    try:
        if task_id not in _download_progress:
            return JSONResponse({"ok": False, "error": "任务不存在"}, status_code=404)
        
        progress = _download_progress[task_id]
        
        return JSONResponse({
            "ok": True,
            "progress": {
                "stage": progress.stage,
                "current": progress.current,
                "total": progress.total,
                "message": progress.message,
                "percentage": round(progress.current / progress.total * 100, 1) if progress.total > 0 else 0,
                "libraries_progress": getattr(progress, 'libraries_progress', {}),
                "assets_progress": getattr(progress, 'assets_progress', {})
            }
        })
    except Exception as e:
        logger.error(f"获取下载进度失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/minecraft/launch")
def api_mc_launch_game(request: Dict = Body(...)):
    """启动 Minecraft 游戏"""
    try:
        version_id = request.get('version_id', '').strip()
        username = request.get('username', 'Player')
        uuid = request.get('uuid', '')
        access_token = request.get('access_token', '')
        jvm_args = request.get('jvm_args', [])
        extra_game_args = request.get('extra_game_args', [])
        
        # 调试日志：打印认证信息
        logger.info(f"🔑 认证信息: username={username}, uuid={uuid[:8] if uuid else '<空>'}..., has_token={bool(access_token)}")
        if access_token:
            logger.debug(f"access_token 预览: {access_token[:50]}...")
        else:
            logger.warning("⚠️ access_token 为空！")
        
        if not version_id:
            return JSONResponse({"ok": False, "error": "版本ID不能为空"}, status_code=400)
        
        # 获取用户配置的目录
        global _minecraft_dir
        mc_dir = _minecraft_dir
        
        if mc_dir is None:
            # 如果没有配置，使用默认目录
            from config import Config
            if not Config.is_configured():
                return JSONResponse({"ok": False, "error": "未配置 FlowerGame 目录"}, status_code=400)
            Config.init_dirs()
            mc_dir = Config.MINECRAFT_DIR
            logger.warning(f"⚠️ 未配置目录，使用默认: {mc_dir}")
        
        logger.info(f"🎮 开始启动 Minecraft {version_id}，目录: {mc_dir}")
        
        # 创建游戏启动器
        launcher = GameLauncher(minecraft_dir=mc_dir)
        
        # 启动游戏
        process = launcher.launch_game(
            version_id=version_id,
            username=username,
            uuid=uuid,
            access_token=access_token,
            jvm_args=jvm_args,
            extra_game_args=extra_game_args
        )
        
        if process:
            return JSONResponse({
                "ok": True,
                "message": f"Minecraft {version_id} 启动成功",
                "pid": process.pid
            })
        else:
            return JSONResponse({
                "ok": False,
                "error": "游戏启动失败，请查看日志了解详情"
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"启动游戏失败: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/system/info")
def api_get_system_info():
    """获取系统信息"""
    try:
        import psutil
        
        # 获取系统内存信息（字节）
        memory = psutil.virtual_memory()
        total_memory_gb = memory.total / (1024 ** 3)  # 转换为 GB
        available_memory_gb = memory.available / (1024 ** 3)
        
        # 获取 CPU 信息
        cpu_count = psutil.cpu_count(logical=True)
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        return JSONResponse({
            "ok": True,
            "memory": {
                "total_gb": round(total_memory_gb, 2),
                "available_gb": round(available_memory_gb, 2),
                "used_percent": memory.percent
            },
            "cpu": {
                "count": cpu_count,
                "usage_percent": cpu_percent
            }
        })
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# WebSocket 端点
@app.websocket("/ws/easytier")
async def websocket_easytier(websocket: WebSocket):
    """
WebSocket 连接端点，用于实时推送网络状态、设备列表和流量统计
    """
    await manager.connect(websocket)
    try:
        # 立即发送当前状态
        initial_status = {
            "type": "status_update",
            "data": {
                "running": _easytier.process is not None,
                "connected": _easytier.process is not None and ProcessHelper.is_process_running(_easytier.process),
                "virtual_ip": _easytier.virtual_ip or "未连接"
            }
        }
        await websocket.send_json(initial_status)
        
        # 保持连接，等待客户端断开
        while True:
            # 接收客户端消息（如果有）
            data = await websocket.receive_text()
            # 可以处理客户端发送的消息
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(websocket)


# 删除 GUI/浏览器打开逻辑，保留命令行启动



def run_web_server():
    ProcessHelper.kill_by_port(Config.WEB_PORT)
    uvicorn.run(app, host=Config.WEB_HOST, port=Config.WEB_PORT, log_level="info")


def open_browser():
    url = f"http://{Config.WEB_HOST}:{Config.WEB_PORT}/web"
    try:
        webbrowser.open(url)
    except Exception:
        logger.warning(f"无法自动打开浏览器，请手动访问 {url}")


def start_gui():
    import tkinter as tk
    root = tk.Tk()
    root.title(f"{Config.APP_NAME} 控制面板")
    label = tk.Label(root, text="Web 服务已启动，点击按钮在浏览器中配置")
    label.pack(padx=16, pady=12)
    btn = tk.Button(root, text="打开浏览器", command=open_browser)
    btn.pack(padx=16, pady=8)
    root.mainloop()


if __name__ == "__main__":
    # ==================== 首次启动检查 ====================
    from config import Config
    
    if not Config.is_configured():
        # 首次启动，弹窗让用户选择目录
        import tkinter as tk
        from tkinter import filedialog, messagebox
        
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        # 显示欢迎消息
        messagebox.showinfo(
            "FlowerGame - 首次启动",
            "欢迎使用 FlowerGame\uff01\n\n"
            "请选择一个目录来存储游戏文件。\n"
            "程序将在该目录下创建 'FlowerGame' 文件夹。\n\n"
            "建议选择空间充足的位置，如 D:\\ 或桌面。"
        )
        
        # 让用户选择目录
        selected_dir = filedialog.askdirectory(
            title="选择 FlowerGame 安装目录",
            initialdir=str(Path.home() / "Desktop")  # 默认打开桌面
        )
        
        if not selected_dir:
            messagebox.showerror(
                "错误",
                "未选择目录，程序将退出。"
            )
            sys.exit(1)
        
        # 创建 FlowerGame 目录
        main_dir = Path(selected_dir) / "FlowerGame"
        main_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存配置
        if Config.set_main_dir(main_dir):
            messagebox.showinfo(
                "成功",
                f"配置成功！\n\n"
                f"游戏文件将存储在：\n{main_dir}\n\n"
                f"现在将启动 FlowerGame..."
            )
        else:
            messagebox.showerror(
                "错误",
                "配置保存失败，请检查权限后重试。"
            )
            sys.exit(1)
        
        root.destroy()
    
    # ==================== 初始化目录 ====================
    if not Config.init_dirs():
        logger.error("初始化目录失败！")
        sys.exit(1)
    
    logger.info(f"📁 FlowerGame 主目录: {Config.get_main_dir()}")
    logger.info(f"🎮 Minecraft 目录: {Config.MINECRAFT_DIR}")
    
    # ==================== 启动 Web 服务 ====================
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()
    ProcessHelper.wait_for_port(Config.WEB_PORT, timeout=30)
    start_gui()
