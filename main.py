import threading
import webbrowser
import time
import os
import sys
import asyncio
import uuid as uuid_lib
import hashlib
from typing import Dict, Set
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from utils.logger import Logger
from utils.process_helper import ProcessHelper
from config import Config, RESOURCE_DIR

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

# 单例服务实例 (延迟初始化)
_auth = None
_syncthing = None
_easytier = None
_java_manager = None
_lan_service = None

# 注意：不在这里创建 _minecraft_downloader，因为需要等待用户配置目录

# 下载进度管理
_download_progress: Dict[str, DownloadProgress] = {}  # 按版本ID存储进度
_download_executor = None  # 全局下载线程池
_minecraft_dir = None  # 用户配置的 Minecraft 目录

# API 缓存（避免重复请求，加快加载速度）
_loader_versions_cache: Dict[str, Dict] = {}  # key: "loader_type:mc_version"
_fabric_api_cache: Dict[str, Dict] = {}  # key: mc_version

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
# 全局 httpx 客户端
_http_client = None

def get_http_client():
    """获取全局 httpx 客户端（单例）"""
    global _http_client
    import httpx
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0, limits=httpx.Limits(max_keepalive_connections=20, max_connections=100))
    return _http_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化全局服务
    global _auth, _syncthing, _easytier, _java_manager
    
    logger.info("正在初始化后台服务...")
    
    # 1. 认证服务
    if _auth is None:
        _auth = MicrosoftAuth()
        logger.info("MicrosoftAuth 服务已初始化")
        
    # 2. Syncthing 服务
    if _syncthing is None:
        _syncthing = SyncthingManager()
        logger.info("Syncthing 服务已初始化")
        
    # 3. Easytier 服务
    if _easytier is None:
        _easytier = EasytierManager()
        logger.info("Easytier 服务已初始化")
        # 启动 NAT 检测 (在后台线程中运行)
        try:
            _easytier.nat_detector.start_detection()
        except Exception as e:
            logger.warning(f"启动 NAT 检测失败: {e}")
        
    # 4. Java 环境管理器
    if _java_manager is None:
        from service.java_environment import JavaManager
        _java_manager = JavaManager()
        logger.info("JavaManager 服务已初始化")

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
    
    # 关闭 HTTP 客户端
    global _http_client
    if _http_client:
        await _http_client.aclose()
        
    # 停止 Syncthing
    try:
        logger.info("正在停止 Syncthing 服务...")
        _syncthing.stop()
    except Exception as e:
        logger.error(f"停止 Syncthing 失败: {e}")

app = FastAPI(title=Config.APP_NAME, version=Config.APP_VERSION, lifespan=lifespan)

# 配置 CORS - 允许来自所有域名的请求
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境建议替换为具体域名，如 ["http://yourdomain.com", "https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有 HTTP 头
)

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
        # 使用副本进行迭代，防止在迭代过程中集合被修改
        connections = list(self.active_connections)
        disconnected = []
        
        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                disconnected.append(connection)
        
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
                import json

                # 获取最新的网络状态
                nat_status = _easytier.nat_detector.get_status()
                status = {
                    "type": "status_update",
                    "data": {
                        "running": _easytier.process is not None,
                        "connected": _easytier.process is not None and ProcessHelper.is_process_running(_easytier.process),
                        "virtual_ip": _easytier.virtual_ip or "未连接",
                        "nat_type": nat_status.get("nat_type", "未知"),
                        "external_ip": nat_status.get("external_ip", None)
                    }
                }

                # 在线程池中执行同步操作
                loop = asyncio.get_event_loop()

                # 获取设备列表（增加超时时间到10秒）
                peers = await loop.run_in_executor(executor, _easytier.discover_peers, 10)
                
                # 清理离线节点的房间
                try:
                    # 提取虚拟IP列表 (排除 ipv4 为空的情况)
                    peer_ips = [p.get('ipv4') for p in peers if p.get('ipv4')]
                    # 只有当获取到 peer 列表或者明确返回空列表时才清理
                    # 注意：discover_peers 出错也会返回空列表，这会导致房间被清空
                    # 考虑到如果无法获取 peer 列表，确实也无法连接房间，所以清空是合理的
                    room_manager.cleanup_offline_rooms(peer_ips)
                except Exception as e:
                    logger.error(f"清理离线房间失败: {e}")

                peers_data = {
                    "type": "peers_update",
                    "data": peers
                }

                # 获取流量统计
                traffic = await loop.run_in_executor(executor, _easytier.get_traffic_stats)
                traffic_data = {
                    "type": "traffic_update",
                    "data": traffic
                }

                # 确保所有数据都可以JSON序列化
                try:
                    json.dumps(status)
                    json.dumps(peers_data)
                    json.dumps(traffic_data)
                except json.JSONDecodeError as json_e:
                    logger.error(f"数据无法JSON序列化: {json_e}")
                    # 只保留状态信息，放弃其他复杂数据
                    peers_data = {"type": "peers_update", "data": []}
                    traffic_data = {"type": "traffic_update", "data": {}}
                
                # 广播所有数据
                try:
                    await manager.broadcast(status)
                    await manager.broadcast(peers_data)
                    await manager.broadcast(traffic_data)
                    
                    # 广播房间列表
                    try:
                        current_rooms = room_manager.get_all_rooms()
                        rooms_data = {
                            "type": "rooms_update",
                            "data": current_rooms
                        }
                        await manager.broadcast(rooms_data)
                    except Exception as room_e:
                        logger.error(f"广播房间列表失败: {room_e}")
                        
                except Exception as broadcast_e:
                    logger.error(f"广播消息时发生JSON序列化或传输错误: {broadcast_e}")
                    # 过滤掉可能导致序列化失败的数据字段
                    try:
                        # 简化数据结构后再次尝试广播
                        nat_status_simple = _easytier.nat_detector.get_status()
                        simplified_status = {
                            "type": "status_update",
                            "data": {
                                "running": _easytier.process is not None,
                                "connected": _easytier.process is not None and ProcessHelper.is_process_running(_easytier.process),
                                "virtual_ip": _easytier.virtual_ip or "未连接",
                                "nat_type": nat_status_simple.get("nat_type", "未知")
                            }
                        }
                        await manager.broadcast(simplified_status)
                    except Exception as simple_e:
                        logger.error(f"简化数据后广播仍然失败: {simple_e}")
            
            # 检查是否需要开启/关闭周期性广播
            current_room = room_manager.get_current_room()
            if current_room and current_room.status == 'open':
                # 我是房主，应该开启周期性广播
                if _easytier.udp_manager and not _easytier.udp_manager.is_broadcasting():
                    _easytier.udp_manager.start_periodic_broadcast(current_room)
            else:
                # 我不是房主或房间未开放，应该停止周期性广播
                if _easytier.udp_manager and _easytier.udp_manager.is_broadcasting():
                    _easytier.udp_manager.stop_periodic_broadcast()

            # 如果我不是房主，且当前没有发现任何远程房间，定期发送房间请求
            if not current_room or current_room.status != 'open':
                if not room_manager.remote_rooms and _easytier.process and ProcessHelper.is_process_running(_easytier.process):
                    if int(time.time()) % 3 == 0: # 每3秒请求一次，加快发现速度
                        try:
                            if _easytier.udp_manager:
                                _easytier.udp_manager.broadcast_request_room_info()
                        except Exception as e:
                            logger.debug(f"请求房间信息失败: {e}")
                        
        except Exception as e:
            logger.error(f"广播网络状态失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        # 每5秒推送一次
        await asyncio.sleep(5)

# 简易首页（Web UI 占位）
# 前端页面部署在公共Web控制台，此处仅提供API

@app.get("/api/health")
def api_health():
    """健康检查"""
    return JSONResponse({"status": "ok", "message": "FlowerGame Backend is running"})

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
    nat_status = _easytier.nat_detector.get_status()
    
    return JSONResponse({
        "running": is_running,
        "virtual_ip": virtual_ip,
        "connected": is_running and virtual_ip not in ["未连接", "waiting...", "unknown"],
        "nat_type": nat_status.get("nat_type", "未知"),
        "external_ip": nat_status.get("external_ip", None)
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

# 资源搜索代理 API
@app.get("/api/resources/search")
async def api_resources_search(query: str = "", facets: str = "", limit: str = "20", offset: str = "0", index: str = ""):
    """Modrinth 搜索代理"""
    target_url = "https://mod.mcimirror.top/modrinth/v2/search"
    params = {
        "limit": limit,
        "offset": offset
    }
    if query:
        params["query"] = query
    if facets:
        params["facets"] = facets
    if index:
        params["index"] = index
        
    try:
        client = get_http_client()
        response = await client.get(target_url, params=params)
        return JSONResponse(response.json())
    except Exception as e:
        logger.error(f"资源搜索失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/resources/versions/{slug}")
async def api_resources_versions(slug: str):
    """Modrinth 版本列表代理"""
    target_url = f"https://mod.mcimirror.top/modrinth/v2/project/{slug}/version"
    
    try:
        client = get_http_client()
        response = await client.get(target_url)
        return JSONResponse(response.json())
    except Exception as e:
        logger.error(f"获取版本列表失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/resources/translate/modrinth")
async def api_translate_modrinth(project_id: str):
    """Modrinth 翻译代理"""
    target_url = "https://mod.mcimirror.top/translate/modrinth"
    params = {"project_id": project_id}
    
    try:
        client = get_http_client()
        response = await client.get(target_url, params=params)
        if response.status_code == 200:
            return JSONResponse(response.json())
        return JSONResponse({"error": "Translation not found"}, status_code=404)
    except Exception as e:
        logger.error(f"获取翻译失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# ... (existing imports)

# 通用文件下载 API
@app.post("/api/resources/download")
async def api_resource_download(request: Dict = Body(...)):
    """通用资源下载接口"""
    import aiofiles
    import os
    from pathlib import Path
    
    url = request.get("url")
    target_path = request.get("path")
    filename = request.get("filename")
    
    if not url or not target_path:
        return JSONResponse({"ok": False, "error": "缺少参数"}, status_code=400)
    
    try:
        # 确保目录存在
        save_path = Path(target_path)
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 如果没有提供文件名，尝试从 URL 获取或使用默认值
        if not filename:
            filename = url.split("/")[-1].split("?")[0] or "downloaded_file"
            
        full_path = save_path / filename
        
        # 启动后台下载任务
        # 如果是 modpack，下载完成后自动安装
        type = request.get("type", "")
        is_modpack = type == "modpack" or filename.endswith(".mrpack")
        
        asyncio.create_task(background_download(url, full_path, is_modpack))
        
        return JSONResponse({"ok": True, "message": "下载已开始", "filename": filename})
    except Exception as e:
        logger.error(f"下载请求失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

async def background_download(url: str, full_path: Path, is_modpack: bool = False):
    """后台下载任务"""
    import httpx
    import aiofiles  # Import aiofiles here to ensure it's available
    try:
        logger.info(f"开始下载资源: {url} -> {full_path}")
        
        client = get_http_client()
        async with client.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0
            
            async with aiofiles.open(full_path, "wb") as f:
                last_progress_time = 0
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # 发送进度（限制频率：每 0.5 秒发送一次）
                    import time
                    current_time = time.time()
                    if total_size > 0 and (current_time - last_progress_time > 0.5 or downloaded_size == total_size):
                        percent = int((downloaded_size / total_size) * 100)
                        await manager.broadcast({
                            "type": "download_progress", 
                            "data": {
                                "filename": full_path.name, 
                                "percent": percent,
                                "total": total_size,
                                "current": downloaded_size
                            }
                        })
                        last_progress_time = current_time
        
        logger.info(f"资源下载完成: {full_path}")
        
        if is_modpack and full_path.name.endswith(".mrpack"):
            # 自动开始安装整合包
            logger.info(f"检测到整合包，开始自动安装: {full_path}")
            
            # 发送通知
            await manager.broadcast({
                "type": "notification", 
                "data": {
                    "type": "info",
                    "title": "下载完成",
                    "message": f"{full_path.name} 下载完成，正在准备安装..."
                }
            })
            
            try:
                from service.minecraft.mrpack_installer import MrPackInstaller
                from config import Config
                
                instance_name = full_path.stem # 使用文件名作为实例名
                installer = MrPackInstaller(Config.MINECRAFT_DIR)
                
                # 定义进度回调
                def progress_callback(stage, current, total, message):
                    percent = 0
                    if total > 0:
                        percent = int((current / total) * 100)
                    elif stage == "done":
                        percent = 100
                    
                    # 记录日志
                    # logger.info(f"进度: {message} {percent}%")
                        
                    # 发送进度 (需要在事件循环中执行)
                    try:
                        # 尝试获取当前运行的事件循环，如果没有则使用 manager 所在的循环（如果有记录的话）或者忽略
                        try:
                             loop = asyncio.get_running_loop()
                        except RuntimeError:
                             loop = None
                        
                        if loop and loop.is_running():
                             loop.create_task(manager.broadcast({
                                "type": "download_progress", 
                                "data": {
                                    "filename": f"安装整合包: {instance_name}", 
                                    "percent": percent,
                                    "total": total,
                                    "current": current,
                                    "message": message
                                }
                            }))
                    except Exception as e:
                         logger.error(f"发送进度失败: {e}")

                installer.set_progress_callback(progress_callback)
                await installer.install(str(full_path), instance_name)
                
                # 发送成功通知
                await manager.broadcast({
                    "type": "notification", 
                    "data": {
                        "type": "success",
                        "title": "安装完成",
                        "message": f"整合包 {instance_name} 已安装成功"
                    }
                })
                
                # 安装成功后删除 .mrpack 文件
                try:
                    if full_path.exists():
                        full_path.unlink()
                        logger.info(f"已清理安装包: {full_path}")
                except Exception as cleanup_error:
                    logger.warning(f"清理安装包失败: {cleanup_error}")
                
            except Exception as e:
                logger.error(f"自动安装整合包失败: {e}")
                await manager.broadcast({
                    "type": "notification", 
                    "data": {
                        "type": "error",
                        "title": "安装失败",
                        "message": f"整合包安装失败: {str(e)}"
                    }
                })
        else:
            # 普通文件下载完成通知
            await manager.broadcast({
                "type": "notification", 
                "data": {
                    "type": "success",
                    "title": "下载完成",
                    "message": f"{full_path.name} 已下载成功"
                }
            })
        
    except Exception as e:
        logger.error(f"下载任务失败: {e}")
        # 发送失败通知
        await manager.broadcast({
            "type": "notification", 
            "data": {
                "type": "error",
                "title": "下载失败",
                "message": f"{full_path.name} 下载失败: {str(e)}"
            }
        })

@app.post("/api/resources/import-mrpack")
async def api_import_mrpack(request: Dict = Body(...)):
    """导入 .mrpack 整合包"""
    file_path = request.get("file_path")
    instance_name = request.get("instance_name")
    
    if not file_path or not instance_name:
        return JSONResponse({"ok": False, "error": "缺少参数"}, status_code=400)
        
    from service.minecraft.mrpack_installer import MrPackInstaller
    from config import Config
    
    try:
        installer = MrPackInstaller(Config.MINECRAFT_DIR)
        
        # 定义进度回调，推送到前端
        def progress_callback(stage, current, total, message):
            percent = 0
            if total > 0:
                percent = int((current / total) * 100)
            elif stage == "done":
                percent = 100
                
            # 发送进度
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(manager.broadcast({
                        "type": "download_progress", 
                        "data": {
                            "filename": f"安装整合包: {instance_name}", 
                            "percent": percent,
                            "total": total,
                            "current": current,
                            "message": message
                        }
                    }))
            except RuntimeError:
                pass

        installer.set_progress_callback(progress_callback)
        
        # 后台执行安装
        asyncio.create_task(installer.install(file_path, instance_name))
        
        return JSONResponse({"ok": True, "message": "整合包安装任务已启动"})
    except Exception as e:
        logger.error(f"导入整合包失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# ... (rest of the file)

# ==================== 存档同步 API ====================

@app.get("/api/sync/peers")
def api_sync_peers():
    """获取所有EasyTier节点及其分享目录"""
    try:
        # 1. 获取 EasyTier 节点
        peers = _easytier.discover_peers()
        if not peers:
            return JSONResponse({"ok": True, "shares": []})
        
        # 2. 扫描分享
        shares = _syncthing.scan_network_shares(peers)
        return JSONResponse({"ok": True, "shares": shares})
    except Exception as e:
        logger.error(f"扫描网络分享失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/sync/local_saves")
def api_sync_local_saves():
    """获取本地存档列表（按版本分组）"""
    try:
        from config import Config
        import os
        
        minecraft_dir = Config.MINECRAFT_DIR
        if not minecraft_dir or not minecraft_dir.exists():
             return JSONResponse({"ok": True, "saves": []})
             
        saves_data = []
        
        # 扫描 versions 目录下的存档 (版本隔离模式)
        versions_dir = minecraft_dir / "versions"
        if versions_dir.exists():
            for version_dir in versions_dir.iterdir():
                if version_dir.is_dir():
                    saves_dir = version_dir / "saves"
                    if saves_dir.exists():
                        for save_dir in saves_dir.iterdir():
                            if save_dir.is_dir():
                                # 获取存档图标（如果有）
                                icon_path = save_dir / "icon.png"
                                has_icon = icon_path.exists()
                                
                                # 获取最后修改时间
                                mtime = save_dir.stat().st_mtime
                                
                                saves_data.append({
                                    "version_id": version_dir.name,
                                    "name": save_dir.name,
                                    "path": str(save_dir),
                                    "has_icon": has_icon,
                                    "last_modified": mtime,
                                    "is_shared": False # TODO: 检查是否已在Syncthing中分享
                                })
                                
        # 检查是否已在 Syncthing 中分享
        if _syncthing.is_running():
            # 获取 Syncthing 文件夹列表
            st_config = _syncthing.get_config()
            if st_config and 'folders' in st_config:
                st_folders = {f['path']: f for f in st_config['folders']}
                for save in saves_data:
                    if save['path'] in st_folders:
                        save['is_shared'] = True
                        save['folder_id'] = st_folders[save['path']]['id']
        
        return JSONResponse({"ok": True, "saves": saves_data})
    except Exception as e:
        logger.error(f"获取本地存档失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/sync/share")
def api_sync_share(request: Dict = Body(...)):
    """分享存档"""
    try:
        # 确保 Syncthing 已启动
        if not _syncthing.is_running():
            logger.info("Syncthing 未运行，正在自动启动...")
            _syncthing.start()
            import time
            time.sleep(2) # 等待启动
            
        version_id = request.get('version_id')
        save_name = request.get('save_name')
        save_path = request.get('save_path')
        
        if not all([version_id, save_name, save_path]):
            return JSONResponse({"ok": False, "error": "缺少必要参数"}, status_code=400)
            
        result = _syncthing.share_save(version_id, save_name, save_path)
        
        if result:
            return JSONResponse({"ok": True, "message": "存档分享成功"})
        else:
            return JSONResponse({"ok": False, "error": "分享失败"}, status_code=500)
    except Exception as e:
        logger.error(f"分享存档失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/sync/connect")
def api_sync_connect(request: Dict = Body(...)):
    """连接远程分享"""
    try:
        # 确保 Syncthing 已启动
        if not _syncthing.is_running():
            logger.info("Syncthing 未运行，正在自动启动...")
            _syncthing.start()
            import time
            time.sleep(2) # 等待启动
            
        device_id = request.get('device_id')
        folder_id = request.get('folder_id')
        folder_label = request.get('folder_label')
        local_path = request.get('local_path') # 用户手动指定的本地路径（绝对路径）
        
        # 新增：通过 version_id 和 save_name 自动构造路径
        local_version_id = request.get('local_version_id')
        save_name = request.get('save_name')
        
        device_ip = request.get('device_ip')
        device_name = request.get('device_name')
        
        # 如果没有提供 local_path，尝试通过版本ID和存档名构造
        if not local_path and local_version_id and save_name:
            from config import Config
            if Config.MINECRAFT_DIR:
                # 构造路径：.minecraft/versions/{version_id}/saves/{save_name}
                local_path = str(Config.MINECRAFT_DIR / "versions" / local_version_id / "saves" / save_name)
                logger.info(f"自动构造本地同步路径: {local_path}")
        
        if not all([device_id, folder_id, local_path]):
            return JSONResponse({"ok": False, "error": "缺少必要参数"}, status_code=400)
            
        result = _syncthing.connect_share(device_id, folder_id, local_path, folder_label, device_ip, device_name)
        
        if result:
            return JSONResponse({"ok": True, "message": "连接成功"})
        else:
            return JSONResponse({"ok": False, "error": "连接失败"}, status_code=500)
    except Exception as e:
        logger.error(f"连接分享失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/sync/status")
def api_sync_status():
    """获取同步状态"""
    try:
        # 检查 Syncthing 是否运行
        if not _syncthing.is_running():
            return JSONResponse({
                "ok": True,
                "running": False,
                "connections": {},
                "folders": []
            })

        # 获取连接状态
        connections = _syncthing.device_manager.get_connections()
        # 获取配置（文件夹列表）
        config = _syncthing.get_config()
        
        folders = []
        if config and 'folders' in config:
             for f in config['folders']:
                 folders.append({
                     "id": f['id'],
                     "label": f['label'],
                     "path": f['path'],
                     "paused": f.get('paused', False),
                     "status": "synced" # 简化状态，实际应查询 completion
                 })
                 
        return JSONResponse({
            "ok": True,
            "running": True,
            "connections": connections,
            "folders": folders
        })
    except Exception as e:
         return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# ==================== Java 环境 API ====================
# JavaManager 已在 lifespan 中初始化
# from service.java_environment import JavaManager
# _java_manager = JavaManager()

@app.get("/api/java/info")
def api_java_info():
    """获取 Java 环境信息"""
    try:
        info = _java_manager.get_java_info()
        return JSONResponse({"ok": True, "data": info})
    except Exception as e:
        logger.error(f"获取 Java 信息失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

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

@app.get("/api/system/pick-file")
def api_pick_file():
    """选择文件（使用文件对话框）"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        selected_path = filedialog.askopenfilename(
            title="选择 Modrinth 整合包",
            filetypes=[("Modrinth Modpack", "*.mrpack"), ("All Files", "*.*")]
        )
        
        root.destroy()
        
        if not selected_path:
            return JSONResponse({"ok": False, "error": "用户取消选择"})
            
        return JSONResponse({"ok": True, "path": selected_path})
    except Exception as e:
        logger.error(f"选择文件失败: {e}")
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
            logger.info(f"📂 使用默认游戏目录: {mc_dir}")
        
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

@app.post("/api/minecraft/delete-version")
async def api_mc_delete_version(request: Dict = Body(...)):
    """删除已安装的 Minecraft 版本"""
    import shutil
    
    try:
        version_id = request.get("version_id")
        
        if not version_id:
            return JSONResponse({"ok": False, "error": "缺少版本 ID"}, status_code=400)
        
        # 获取用户配置的目录
        global _minecraft_dir
        mc_dir = _minecraft_dir
        
        if mc_dir is None:
            from config import Config
            if not Config.is_configured():
                return JSONResponse({"ok": False, "error": "未配置 FlowerGame 目录"}, status_code=400)
            Config.init_dirs()
            mc_dir = Config.MINECRAFT_DIR
        
        # 版本目录路径
        versions_dir = Path(mc_dir) / "versions" / version_id
        
        if not versions_dir.exists():
            return JSONResponse({"ok": False, "error": f"版本 {version_id} 不存在"}, status_code=404)
        
        # 删除版本目录
        logger.info(f"🗑️ 删除版本: {version_id}, 路径: {versions_dir}")
        shutil.rmtree(versions_dir)
        
        logger.info(f"✅ 版本 {version_id} 删除成功")
        return JSONResponse({"ok": True, "message": f"版本 {version_id} 已删除"})
        
    except Exception as e:
        logger.error(f"删除版本失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/minecraft/loader-versions")
def api_mc_get_loader_versions(loader_type: str, mc_version: str):
    """获取加载器版本列表"""
    try:
        # 检查缓存
        cache_key = f"{loader_type}:{mc_version}"
        if cache_key in _loader_versions_cache:
            cached_data = _loader_versions_cache[cache_key]
            logger.info(f"✨ 使用缓存的加载器版本: {cache_key}")
            return JSONResponse(cached_data)
        
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
            
            result = {
                "ok": True,
                "versions": versions,
                "total": len(versions)
            }
            
            # 缓存结果
            _loader_versions_cache[cache_key] = result
            logger.info(f"💾 已缓存加载器版本: {cache_key}, 数量: {len(versions)}")
            
            return JSONResponse(result)
        finally:
            temp_manager.close()
    except Exception as e:
        logger.error(f"获取加载器版本失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/minecraft/fabric-api-versions")
def api_mc_get_fabric_api_versions(mc_version: str):
    """获取 Fabric API 版本列表"""
    try:
        # 检查缓存
        if mc_version in _fabric_api_cache:
            cached_data = _fabric_api_cache[mc_version]
            logger.info(f"✨ 使用缓存的 Fabric API 版本: {mc_version}")
            return JSONResponse(cached_data)
        
        import httpx
        from utils.httpx import get_session
        
        # 使用 Modrinth API 获取 Fabric API 版本
        # Fabric API 的 Modrinth 项目 ID
        fabric_api_id = "P7dR8mSH"  # Fabric API 在 Modrinth 上的 ID
        
        client = get_session()
        
        # 直接获取所有版本，然后手动过滤
        url = f"https://api.modrinth.com/v2/project/{fabric_api_id}/version"
        
        logger.info(f"请求 Fabric API 版本: mc_version={mc_version}")
        
        response = client.get(url, timeout=10.0)
        
        logger.info(f"Modrinth API 响应状态: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"获取 Fabric API 版本失败: {response.status_code}")
            return JSONResponse({"ok": True, "versions": [], "total": 0})
        
        all_versions = response.json()
        logger.info(f"获取到 {len(all_versions)} 个 Fabric API 版本")
        
        # 手动过滤出包含当前 MC 版本的版本
        versions_data = []
        for version in all_versions:
            game_versions = version.get("game_versions", [])
            loaders = version.get("loaders", [])
            # 检查是否支持当前 MC 版本和 Fabric 加载器
            if mc_version in game_versions and "fabric" in loaders:
                versions_data.append(version)
                if len(versions_data) >= 20:  # 限制最多20个版本
                    break
        
        logger.info(f"过滤后得到 {len(versions_data)} 个版本")
        
        # 提取版本信息
        versions = []
        for version in versions_data:
            versions.append({
                "version": version.get("version_number", ""),
                "name": version.get("name", ""),
                "game_version": mc_version,
                "downloads": version.get("downloads", 0),
                "date_published": version.get("date_published", "")
            })
        
        logger.info(f"返回 {len(versions)} 个 Fabric API 版本")
        
        result = {
            "ok": True,
            "versions": versions,
            "total": len(versions)
        }
        
        # 缓存结果
        _fabric_api_cache[mc_version] = result
        logger.info(f"💾 已缓存 Fabric API 版本: {mc_version}, 数量: {len(versions)}")
        
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"获取 Fabric API 版本失败: {e}", exc_info=True)
        # 返回空列表而不是错误，因为 Fabric API 是可选的
        return JSONResponse({"ok": True, "versions": [], "total": 0})

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
                logger.info(f"📂 使用默认游戏目录: {mc_dir}")
            
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
        fabric_api_version = request.get('fabric_api_version')
        
        # 安全地处理字符串
        mc_version = mc_version.strip() if mc_version else ''
        loader_type = loader_type.strip() if loader_type else ''
        loader_version = loader_version.strip() if loader_version else ''
        custom_name = custom_name.strip() if custom_name else None
        fabric_api_version = fabric_api_version.strip() if fabric_api_version else None
        
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
                    mc_version, loader, loader_version, custom_name, fabric_api_version
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


def get_offline_uuid(username: str) -> str:
    """生成离线 UUID (Version 3, based on MD5)"""
    string = f"OfflinePlayer:{username}"
    hash_bytes = hashlib.md5(string.encode('utf-8')).digest()
    hash_bytes = bytearray(hash_bytes)
    hash_bytes[6] = (hash_bytes[6] & 0x0f) | 0x30  # Version 3
    hash_bytes[8] = (hash_bytes[8] & 0x3f) | 0x80  # Variant 1
    return str(uuid_lib.UUID(bytes=bytes(hash_bytes)))


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
        if access_token:
            logger.info(f"🔑 正版认证信息: username={username}, uuid={uuid[:8]}...")
        else:
            logger.info(f"⚡ 离线模式启动: username={username}")
            # 如果是离线登录且没有 UUID，自动生成
            if not uuid:
                uuid = get_offline_uuid(username)
                logger.info(f"✅ 已生成离线 UUID: {uuid}")

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
            logger.info(f"📂 使用默认游戏目录: {mc_dir}")
        
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
@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """
    WebSocket 连接端点，用于实时推送网络状态、房间列表和流量统计
    """
    # 接受连接前不检查 origin，因为我们允许所有来源
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
        
        # 立即发送房间列表
        try:
            current_rooms = room_manager.get_all_rooms()
            await websocket.send_json({
                "type": "rooms_update",
                "data": current_rooms
            })
        except Exception as e:
            logger.error(f"发送初始房间列表失败: {e}")

        # 保持连接，等待客户端断开
        while True:
            try:
                # 接收客户端消息（如果有），设置超时防止无限等待
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # 可以处理客户端发送的消息
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except (ConnectionResetError, BrokenPipeError, EOFError):
        # 处理客户端断开连接错误
        logger.debug("WebSocket 客户端已断开连接")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(websocket)


# ==================== 联机房间 API ====================

from service.minecraft.online_lobby import NBTModifier, room_manager, LANPublishService, PublishConfig

# 全局联机服务实例
_lan_service: LANPublishService = None

def get_lan_service() -> LANPublishService:
    """获取联机服务（延迟初始化）"""
    global _lan_service, _minecraft_dir
    if _lan_service is None and _minecraft_dir:
        _lan_service = LANPublishService(minecraft_dir=_minecraft_dir)
    return _lan_service

@app.get("/api/room/check-port")
def api_room_check_port(port: int):
    """检查端口是否被占用
    
    Args:
        port: 要检查的端口号
        
    Returns:
        {ok: bool, available: bool, message: str}
    """
    import socket
    
    if port < 1024 or port > 65535:
        return {"ok": False, "error": "端口号必须在 1024-65535 之间"}
    
    try:
        # 尝试绑定端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            # 端口被占用
            return {"ok": True, "available": False, "message": f"端口 {port} 已被占用"}
        else:
            # 端口可用
            return {"ok": True, "available": True, "message": f"端口 {port} 可用"}
    except Exception as e:
        return {"ok": True, "available": True, "message": f"端口 {port} 可用"}


@app.get("/api/room/saves")
def api_room_list_saves(version_id: str = None):
    """获取存档列表"""
    try:
        # 记录收到的参数，用于调试
        # 使用 print 直接输出到控制台，以防 logger 本身有问题
        print(f"DEBUG: api_room_list_saves called with version_id='{version_id}'")
        if logger:
            logger.info(f"📥 收到获取存档请求，参数 version_id: '{version_id}'")
        
        global _minecraft_dir
        mc_dir = _minecraft_dir
        print(f"DEBUG: _minecraft_dir='{mc_dir}'")
        
        if mc_dir is None:
            from config import Config
            if not Config.is_configured():
                print("DEBUG: Config not configured")
                return JSONResponse({"ok": False, "error": "未配置 FlowerGame 目录"}, status_code=400)
            Config.init_dirs()
            mc_dir = Config.MINECRAFT_DIR
            print(f"DEBUG: Config initialized, mc_dir='{mc_dir}'")
        
        # 处理 version_id 为空字符串的情况
        if version_id and not version_id.strip():
            version_id = None
            
        # 构建存档目录路径
        if version_id:
            saves_dir = Path(mc_dir) / "versions" / version_id / "saves"
            if logger:
                logger.info(f"📂 [严格隔离] 查找存档 - 目标版本: {version_id}")
                logger.info(f"📂 [严格隔离] 目标路径: {saves_dir}")
        else:
            saves_dir = Path(mc_dir) / "saves"
            if logger:
                logger.info(f"📂 [标准模式] 存档目录: {saves_dir}")
        
        print(f"DEBUG: saves_dir='{saves_dir}', exists={saves_dir.exists()}")

        if not saves_dir.exists():
            if logger:
                logger.warning(f"⚠️ 存档目录不存在: {saves_dir}")
            # 尝试列出父目录内容
            try:
                parent = saves_dir.parent
                if parent.exists():
                    items = [x.name for x in parent.iterdir()]
                    print(f"DEBUG: Parent dir content: {items}")
                    if logger:
                        logger.info(f"📂 父目录 {parent} 内容: {items}")
                else:
                    if logger:
                        logger.warning(f"⚠️ 父目录 {parent} 也不存在")
                    # 再往上一层
                    grandparent = parent.parent
                    if grandparent.exists():
                        items = [x.name for x in grandparent.iterdir()]
                        print(f"DEBUG: Grandparent dir content: {items}")
                        if logger:
                            logger.info(f"📂 祖父目录 {grandparent} 内容: {items}")
            except Exception as e:
                print(f"DEBUG: Error listing directories: {e}")
                pass
        
        print("DEBUG: Initializing NBTModifier")
        modifier = NBTModifier(minecraft_dir=mc_dir, saves_dir=saves_dir)
        print("DEBUG: Calling get_saves_list")
        saves = modifier.get_saves_list()
        print(f"DEBUG: get_saves_list returned {len(saves)} saves")
        
        if logger:
            logger.info(f"🔍 扫描完成，找到 {len(saves)} 个存档")
        
        return JSONResponse({
            "ok": True,
            "saves": saves,
            "saves_dir": str(saves_dir)
        })
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(f"CRITICAL ERROR in api_room_list_saves: {e}\n{trace}")
        if logger:
            logger.error(f"获取存档列表失败: {e}", exc_info=True)
        # 即使发生错误，也返回空列表，避免前端崩溃
        return JSONResponse({
            "ok": True,
            "saves": [],
            "error": str(e),
            "saves_dir": ""
        })

@app.post("/api/room/create")
async def api_room_create(request: Dict = Body(...)):
    """创建联机房间"""
    try:
        # 获取参数（处理 None 值）
        room_name = (request.get('room_name') or '').strip()
        save_name = (request.get('save_name') or '').strip()
        port = request.get('port') or 25565
        # password = (request.get('password') or '').strip() or None
        password = None # 强制不使用密码
        game_mode = request.get('game_mode') or 'survival'
        
        # 账号信息
        username = request.get('username') or 'Player'
        uuid = request.get('uuid') or ''
        access_token = request.get('access_token') or ''
        
        # 如果是离线登录且没有 UUID，自动生成
        if not uuid and not access_token:
            uuid = get_offline_uuid(username)
            logger.info(f"✅ 检测到离线登录，已生成离线 UUID: {uuid}")
        
        # 版本信息
        version_id = (request.get('version_id') or '').strip()
        
        # JVM参数
        jvm_args = request.get('jvm_args', [])
        
        # 额外的游戏参数（如 --quickPlayMultiplayer）
        extra_game_args = request.get('extra_game_args', [])
        
        if not room_name:
            logger.warning("❌ 创建房间失败: 房间名称为空")
            return JSONResponse({"ok": False, "error": "房间名称不能为空"}, status_code=400)
        if not save_name:
            logger.warning("❌ 创建房间失败: 未选择存档")
            return JSONResponse({"ok": False, "error": "请选择存档"}, status_code=400)
        if not version_id:
            logger.warning("❌ 创建房间失败: 未选择游戏版本")
            return JSONResponse({"ok": False, "error": "请选择游戏版本"}, status_code=400)
        
        global _minecraft_dir
        mc_dir = _minecraft_dir
        
        if mc_dir is None:
            from config import Config
            if not Config.is_configured():
                return JSONResponse({"ok": False, "error": "未配置 FlowerGame 目录"}, status_code=400)
            Config.init_dirs()
            mc_dir = Config.MINECRAFT_DIR
        
        # 1. 修改存档开启作弊
        # 严格隔离模式：存档只能在 versions/{version_id}/saves 目录下
        if version_id:
            saves_dir = Path(mc_dir) / "versions" / version_id / "saves"
        else:
            saves_dir = Path(mc_dir) / "saves"
        
        logger.info(f"🔧 为存档 {save_name} 开启作弊... (存档目录: {saves_dir})")
        modifier = NBTModifier(minecraft_dir=mc_dir, saves_dir=saves_dir)
        success, msg = modifier.enable_commands(save_name)
        if not success:
            return JSONResponse({"ok": False, "error": f"修改存档失败: {msg}"}, status_code=500)
        
        # 2. 获取虚拟IP
        virtual_ip = _easytier.virtual_ip or ""
        
        # 3. 创建房间
        room = room_manager.create_room(
            name=room_name,
            save_name=save_name,
            port=port,
            host_player=username,
            password=password,
            game_mode=game_mode,
            virtual_ip=virtual_ip
        )
        
        # 4. 启动游戏并发布局域网
        lan_service = get_lan_service()
        if not lan_service:
            lan_service = LANPublishService(minecraft_dir=mc_dir)
        
        def on_game_started(pid: int):
            room_manager.set_room_process(room.room_id, pid)
            room_manager.update_room_status(room.room_id, 'waiting')
            # 启动进程监控，游戏退出时自动关闭房间
            room_manager.start_process_monitor(room.room_id, pid)
            logger.info(f"🎮 游戏已启动，PID: {pid}")
        
        def on_publish_success():
            room_manager.update_room_status(room.room_id, 'open')
            logger.info(f"✅ 房间 {room_name} 已开放！")
            
            # 广播房间创建消息到Easytier网络
            try:
                peers = _easytier.discover_peers()
                peer_ips = [p.get('ipv4') for p in peers if p.get('ipv4')]
                _easytier.udp_manager.broadcast_room_created(room, peer_ips)
                logger.info(f"📡 已广播房间信息到 {len(peer_ips)} 个节点")
            except Exception as e:
                logger.warning(f"广播房间信息失败: {e}")
        
        def on_error(error_msg: str):
            room_manager.update_room_status(room.room_id, 'error', error_msg)
            logger.error(f"❌ 房间创建失败: {error_msg}")
        
        room_manager.update_room_status(room.room_id, 'creating')
        
        lan_service.start_and_publish(
            version_id=version_id,
            save_name=save_name,
            username=username,
            port=port,
            game_mode=game_mode,
            uuid=uuid,
            access_token=access_token,
            jvm_args=jvm_args,
            on_game_started=on_game_started,
            on_publish_success=on_publish_success,
            on_error=on_error
        )
        
        return JSONResponse({
            "ok": True,
            "message": "房间创建中...",
            "room": room.to_dict()
        })
        
    except Exception as e:
        logger.error(f"创建房间失败: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/room/saves")
def api_room_saves(version_id: str = ""):
    """
    获取可用的存档列表
    支持版本隔离：如果指定了 version_id，则从 versions/{version_id}/saves 读取
    """
    try:
        global _minecraft_dir
        mc_dir = _minecraft_dir
        
        if mc_dir is None:
            from config import Config
            if not Config.is_configured():
                return JSONResponse({"ok": False, "error": "未配置 FlowerGame 目录"}, status_code=400)
            Config.init_dirs()
            mc_dir = Config.MINECRAFT_DIR
        
        # 严格版本隔离逻辑
        if version_id:
            # 如果指定了版本，只从该版本的 saves 目录读取
            logger.info(f"📂 [严格隔离] 查找存档 - 目标版本: {version_id}")
            saves_dir = Path(mc_dir) / "versions" / version_id / "saves"
            logger.info(f"📂 [严格隔离] 目标路径: {saves_dir}")
        else:
            # 默认目录
            saves_dir = Path(mc_dir) / "saves"
        
        if not saves_dir.exists():
            logger.warning(f"⚠️ 存档目录不存在: {saves_dir}")
            return JSONResponse({
                "ok": True,
                "saves": []
            })
            
        saves = []
        for save_path in saves_dir.iterdir():
            if save_path.is_dir():
                # 检查是否有 level.dat
                if (save_path / "level.dat").exists():
                    save_info = {
                        "name": save_path.name,
                        "path": str(save_path),
                        "game_mode": 0, # 默认生存
                        "level_name": save_path.name,
                        "allow_commands": False
                    }
                    
                    # 尝试读取 level.dat 获取更多信息
                    try:
                        modifier = NBTModifier(minecraft_dir=mc_dir, saves_dir=saves_dir)
                        details = modifier.get_save_info(save_path.name)
                        if details:
                            save_info.update(details)
                    except Exception as e:
                        logger.warning(f"读取存档 {save_path.name} 信息失败: {e}")
                        
                    saves.append(save_info)
        
        logger.info(f"🔍 扫描完成，找到 {len(saves)} 个存档")
        return JSONResponse({
            "ok": True,
            "saves": saves
        })
        
    except Exception as e:
        logger.error(f"获取存档列表失败: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/room/current")
def api_room_get_current():
    """获取当前房间状态"""
    try:
        room = room_manager.get_current_room()
        if room:
            return JSONResponse({
                "ok": True,
                "room": room.to_dict()
            })
        return JSONResponse({
            "ok": True,
            "room": None
        })
    except Exception as e:
        logger.error(f"获取当前房间失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/room/list")
def api_room_list_all():
    """获取所有房间列表"""
    try:
        # 尝试主动请求房间信息，加速发现
        if _easytier.udp_manager:
            try:
                _easytier.udp_manager.broadcast_request_room_info()
            except Exception:
                pass

        rooms = room_manager.get_all_rooms()
        return JSONResponse({
            "ok": True,
            "rooms": rooms
        })
    except Exception as e:
        logger.error(f"获取房间列表失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/room/close")
def api_room_close(request: Dict = Body(...)):
    """关闭房间"""
    try:
        room_id = request.get('room_id', '')
        
        if not room_id:
            # 关闭当前房间
            room = room_manager.get_current_room()
            if room:
                room_id = room.room_id
            else:
                return JSONResponse({"ok": False, "error": "没有活动的房间"}, status_code=400)
        
        room_manager.close_room(room_id)
        
        return JSONResponse({
            "ok": True,
            "message": "房间已关闭"
        })
    except Exception as e:
        logger.error(f"关闭房间失败: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# 删除 GUI/浏览器打开逻辑，保留命令行启动



def run_web_server():
    ProcessHelper.kill_by_port(Config.WEB_PORT)
    uvicorn.run(
        app,
        host=Config.WEB_HOST,
        port=Config.WEB_PORT,
        log_level="info",
        access_log=False  # 禁用访问日志
    )


def open_browser():
    # 打开公共Web控制台
    # url = Config.WEB_CONSOLE_URL
    url = "https://mc.765.run"
    logger.info(f"正在打开Web控制台: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        logger.warning(f"无法自动打开浏览器，请手动访问 {url}")


def start_gui():
    import tkinter as tk
    from tkinter import ttk
    import sys
    import ctypes
    
    # 设置 DPI 感知
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    
    # 设置窗口图标
    try:
        icon_path = RESOURCE_DIR / "logo.ico"
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
    except Exception as e:
        logger.warning(f"设置窗口图标失败: {e}")

    # 去除原生标题栏 (不再使用 overrideredirect)
    # root.overrideredirect(True) 
    
    root.title(f"{Config.APP_NAME}")
    root.geometry("400x280")
    root.configure(bg="#0f172a")  # 深蓝色背景
    
    # 使用 WinAPI 移除标题栏和边框，保留任务栏图标和最小化功能
    def setup_window_style():
        try:
            # 确保窗口已映射
            root.update_idletasks()
            
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            if hwnd == 0:
                hwnd = root.winfo_id()
                
            # 获取当前样式 (GWL_STYLE = -16)
            old_style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
            
            # 移除标题栏 (WS_CAPTION = 0x00C00000) 和 厚边框 (WS_THICKFRAME = 0x00040000)
            new_style = old_style & ~0x00C00000
            new_style = new_style & ~0x00040000
            
            ctypes.windll.user32.SetWindowLongW(hwnd, -16, new_style)
            
            # 强制刷新 (SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0020)
                
        except Exception as e:
            logger.warning(f"设置窗口样式失败: {e}")
            
    # 延时执行，确保窗口已创建
    root.after(100, setup_window_style)
    
    # 居中窗口
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 400) // 2
    y = (screen_height - 280) // 2
    root.geometry(f"400x280+{x}+{y}")

    # 顶部标题栏区域 (用于拖拽和放置按钮)
    title_bar = tk.Frame(root, bg="#0f172a", height=30)
    title_bar.pack(fill="x", side="top")

    # 实现窗口拖拽 (使用 WinAPI 替代 Python 层面计算，解决不流畅问题)
    def start_move(event):
        # 只有左键点击才触发
        # 释放鼠标捕获，让系统处理拖拽
        try:
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            if hwnd == 0:
                hwnd = root.winfo_id()
            
            # ReleaseCapture
            ctypes.windll.user32.ReleaseCapture()
            # SendMessage(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)
            # WM_NCLBUTTONDOWN = 0xA1
            # HTCAPTION = 2
            ctypes.windll.user32.SendMessageW(hwnd, 0xA1, 2, 0)
        except Exception as e:
            logger.warning(f"窗口拖拽失败: {e}")

    # 自定义最小化按钮
    def minimize_window():
        root.iconify()

    def on_min_enter(e):
        e.widget['background'] = '#1e293b'  # 稍微亮一点的背景
        e.widget['foreground'] = 'white'

    def on_min_leave(e):
        e.widget['background'] = '#0f172a'  # 背景色
        e.widget['foreground'] = '#94a3b8'

    # 自定义关闭按钮
    def close_window():
        root.destroy()
        sys.exit(0)
        
    def on_close_enter(e):
        e.widget['background'] = '#ef4444'  # 红色
        e.widget['foreground'] = 'white'

    def on_close_leave(e):
        e.widget['background'] = '#0f172a'  # 背景色
        e.widget['foreground'] = '#94a3b8'

    close_btn = tk.Button(
        title_bar,
        text="✕",
        command=close_window,
        font=("Segoe UI", 10),
        bg="#0f172a",
        fg="#94a3b8",
        bd=0,
        relief="flat",
        activebackground="#ef4444",
        activeforeground="white",
        width=4
    )
    close_btn.pack(side="right", padx=0, pady=0, fill="y")
    
    close_btn.bind("<Enter>", on_close_enter)
    close_btn.bind("<Leave>", on_close_leave)

    min_btn = tk.Button(
        title_bar,
        text="—",
        command=minimize_window,
        font=("Segoe UI", 10, "bold"),
        bg="#0f172a",
        fg="#94a3b8",
        bd=0,
        relief="flat",
        activebackground="#1e293b",
        activeforeground="white",
        width=4
    )
    min_btn.pack(side="right", padx=0, pady=0, fill="y")
    
    min_btn.bind("<Enter>", on_min_enter)
    min_btn.bind("<Leave>", on_min_leave)

    # 只需要绑定 ButtonPress-1，不需要 Motion 和 Release
    # 绑定拖拽事件到整个窗口和标题栏
    root.bind("<ButtonPress-1>", start_move)
    title_bar.bind("<ButtonPress-1>", start_move)
    
    # 内容区域
    content_frame = tk.Frame(root, bg="#0f172a")
    content_frame.pack(expand=True, fill="both")
    content_frame.bind("<ButtonPress-1>", start_move)

    # 标题样式
    # 尝试加载 Logo 图片
    logo_img = None
    try:
        from PIL import Image, ImageTk
        logo_path = RESOURCE_DIR / "logo.png"
        if logo_path.exists():
            pil_image = Image.open(str(logo_path))
            # 调整大小 (保持比例，最大高度 150)
            # 计算新的尺寸
            width, height = pil_image.size
            max_height = 130
            if height > max_height:
                ratio = max_height / height
                new_width = int(width * ratio)
                new_height = max_height
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            logo_img = ImageTk.PhotoImage(pil_image)
            
            logo_label = tk.Label(
                content_frame,
                image=logo_img,
                bg="#0f172a"
            )
            logo_label.pack(pady=(10, 5))
            logo_label.bind("<ButtonPress-1>", start_move)
            
            # 如果有 Logo，不显示标题文字
            title_text = ""
        else:
            title_text = "🌸 FlowerGame"
    except Exception as e:
        logger.warning(f"加载 Logo 失败: {e}")
        title_text = "🌸 FlowerGame"

    if title_text:
        title_label = tk.Label(
            content_frame, 
            text=title_text, 
            font=("Segoe UI", 24, "bold"),
            bg="#0f172a",
            fg="#f1f5f9"  # 浅色文字
        )
        title_label.pack(pady=(0, 10))
        title_label.bind("<ButtonPress-1>", start_move)

    # 按钮样式
    def on_enter(e):
        e.widget['background'] = '#4ade80'  # 悬停颜色 (更亮的绿色)

    def on_leave(e):
        e.widget['background'] = '#22c55e'  # 默认颜色 (绿色)

    btn = tk.Button(
        content_frame, 
        text="打开控制台", 
        command=open_browser,
        font=("Segoe UI", 12, "bold"),
        bg="#22c55e",        # 绿色背景
        fg="white",          # 白色文字
        activebackground="#16a34a", # 点击颜色 (深绿色)
        activeforeground="white",
        relief="flat",       # 扁平化
        bd=0,
        cursor="hand2",
        width=16,
        height=2
    )
    btn.pack(pady=(10, 20))
    
    # 绑定悬停效果
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)

    # 副标题/状态样式 - 移动到按钮下方
    status_label = tk.Label(
        content_frame, 
        text="服务正在运行中...", 
        font=("Segoe UI", 10),
        bg="#0f172a",
        fg="#94a3b8"  # 灰色文字
    )
    status_label.pack(pady=(0, 10))
    status_label.bind("<ButtonPress-1>", start_move)

    # 底部版本信息
    version_label = tk.Label(
        content_frame, 
        text="v1.0.0", 
        font=("Segoe UI", 9),
        bg="#0f172a",
        fg="#64748b"  # 深灰色文字
    )
    version_label.pack(side="bottom", pady=15)
    version_label.bind("<ButtonPress-1>", start_move)

    root.mainloop()


if __name__ == "__main__":
    # ==================== Nuitka 路径调试 ====================
    try:
        import sys
        import os
        from pathlib import Path
        
        # 确定日志文件路径：优先在 exe 同级目录
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.getcwd()
            
        debug_file = os.path.join(base_dir, "nuitka_debug_info.txt")
        
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(f"Python Version: {sys.version}\n")
            f.write(f"sys.executable: {sys.executable}\n")
            f.write(f"sys.argv: {sys.argv}\n")
            f.write(f"os.getcwd(): {os.getcwd()}\n")
            f.write(f"sys.frozen: {getattr(sys, 'frozen', 'Not Set')}\n")
            f.write(f"__file__: {__file__ if '__file__' in globals() else 'Not Set'}\n")
            
            if getattr(sys, 'frozen', False):
                 f.write(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'Not Set')}\n")
            
            # 检查 config.py 中的路径逻辑
            try:
                # 模拟 config.py 的逻辑
                if hasattr(sys, "_MEIPASS"):
                    sim_base = Path(sys._MEIPASS)
                    f.write(f"Simulated BASE_DIR (PyInstaller): {sim_base}\n")
                elif getattr(sys, "frozen", False):
                    # Nuitka onefile/standalone
                    # 注意：这里我们直接用 __file__，看看它在 Nuitka 中是什么
                    if '__file__' in globals():
                        sim_base = Path(__file__).resolve().parent
                        f.write(f"Simulated BASE_DIR (Nuitka from main.py __file__): {sim_base}\n")
                    else:
                        f.write("Simulated BASE_DIR (Nuitka): __file__ is not defined\n")
                        sim_base = Path(os.getcwd()) # Fallback
                else:
                    sim_base = Path(__file__).resolve().parent
                    f.write(f"Simulated BASE_DIR (Normal): {sim_base}\n")
                
                # 检查 resources 目录
                if 'sim_base' in locals():
                    f.write(f"Listing all files in BASE_DIR: {sim_base}\n")
                    for root, dirs, files in os.walk(sim_base):
                        for name in files:
                            f.write(f"  FILE: {os.path.join(root, name)}\n")
                        for name in dirs:
                            f.write(f"  DIR:  {os.path.join(root, name)}\n")

                    res_dir = sim_base / "resources"
                    f.write(f"Simulated RESOURCE_DIR: {res_dir}\n")
                    f.write(f"Resource dir exists: {res_dir.exists()}\n")
                    
                    if res_dir.exists():
                        f.write(f"Resource dir content: {[p.name for p in res_dir.iterdir()]}\n")
                        
                        # 检查 easytier
                        et_dir = res_dir / "easytier"
                        if et_dir.exists():
                            f.write(f"Easytier dir content: {[p.name for p in et_dir.iterdir()]}\n")
                        else:
                            f.write("Easytier dir NOT found inside resources\n")
                    else:
                        # 如果 resources 不在 sim_base，尝试在 sys.executable 旁边找（Standalone 模式）
                        exe_dir = Path(sys.executable).parent
                        res_dir_exe = exe_dir / "resources"
                        f.write(f"Checking resources next to exe: {res_dir_exe}\n")
                        f.write(f"Exists: {res_dir_exe.exists()}\n")
                        if res_dir_exe.exists():
                             f.write(f"Content: {[p.name for p in res_dir_exe.iterdir()]}\n")

            except Exception as e:
                f.write(f"Error checking paths: {e}\n")

    except Exception as e:
        # 哪怕出错也不要崩溃，尽量忽略
        pass

    # ==================== 权限检查 ====================
    import ctypes
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False
        
    if not is_admin:
        # 尝试重新以管理员身份运行
        # logger.info("正在请求管理员权限...") # 此时 logger 可能还没初始化
        import sys
        import subprocess
        
        # 如果是打包后的 exe
        if getattr(sys, 'frozen', False):
            # 使用 ShellExecute 显式请求 runas
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv[1:]), None, 1)
        else:
            # 如果是脚本运行
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        
        sys.exit(0)
    
    # ==================== 首次启动检查 ====================
    # 在权限检查之后再导入 Config，确保日志文件能正确创建（如果有权限问题）
    from config import Config
    
    if not Config.is_configured():
        # 使用美化后的设置窗口
        from ui.setup_window import SetupWindow, show_success_dialog
        
        setup = SetupWindow()
        selected_path = setup.run()
        
        if not selected_path:
            sys.exit(0)  # 用户关闭窗口
            
        # 保存配置
        if Config.set_main_dir(selected_path):
            show_success_dialog(selected_path)
        else:
            # 失败回退到简单弹窗
            import tkinter.messagebox as messagebox
            messagebox.showerror("错误", "配置保存失败，请检查权限后重试。")
            sys.exit(1)
    
    # ==================== 初始化目录 ====================
    if not Config.init_dirs():
        # 这里的 logger 还没初始化（因为 Logger 依赖 Config.init_dirs），所以只能用 print 或者简单的文件写入
        print("初始化目录失败！")
        sys.exit(1)
    
    # 在目录初始化完成后，强制重新初始化 Logger
    # 这样日志文件才会生成在用户配置的 logs 目录中，而不是临时目录
    from utils.logger import Logger
    # 如果之前已经实例化过 Logger（比如在 import 阶段），需要重新配置 handler
    Logger._instance = None 
    logger = Logger().get_logger("Main")

    logger.info(f"📁 FlowerGame 主目录: {Config.get_main_dir()}")
    logger.info(f"🎮 Minecraft 目录: {Config.MINECRAFT_DIR}")
    
    # ==================== 启动 Web 服务 ====================
    # 确保日志能输出到文件
    sys.stdout = open(Config.LOG_DIR / "stdout.log", "a", encoding="utf-8", buffering=1)
    sys.stderr = open(Config.LOG_DIR / "stderr.log", "a", encoding="utf-8", buffering=1)

    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()
    # ProcessHelper.wait_for_port(Config.WEB_PORT, timeout=30) # 移除阻塞等待，让界面尽快显示
    start_gui()
