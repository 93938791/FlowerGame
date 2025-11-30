import threading
import webbrowser
import time
import os
import sys
import asyncio
from typing import Dict, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from utils.logger import Logger
from utils.process_helper import ProcessHelper
from config import Config

# 业务模块
from service.minecraft.login.microsoft_auth import MicrosoftAuth
from service.minecraft.download.download_service import DownloadService
from service.syncthing.syncthing_manager import SyncthingManager
from service.easytier.easytier_manager import EasytierManager
from service.cache.config_cache import ConfigCache

logger = Logger().get_logger("Main")

# 单例服务实例
_auth = MicrosoftAuth()
_download = DownloadService(config={})  # 使用默认下载配置
_syncthing = SyncthingManager()
_easytier = EasytierManager()

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：启动后台推送任务
    task = asyncio.create_task(broadcast_network_status())
    logger.info("后台 WebSocket 推送任务已启动")
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
                logger.info(f"获取到 {len(peers)} 个设备: {peers}")
                
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
        
        return {"ok": True, "error": None, "profile": profile}
    else:
        # 返回错误（包括authorization_pending）
        return {"ok": False, "error": err, "profile": None}

@app.post("/api/auth/authenticate")
def api_auth_authenticate(payload: Dict):
    code = payload.get("auth_code", "")
    ok, err, profile = _auth.authenticate(code)
    return {"ok": ok, "error": err, "profile": profile}

@app.get("/api/auth/status")
def api_auth_status():
    return _auth.get_auth_info()

@app.post("/api/auth/save-profile")
def api_auth_save_profile(payload: Dict):
    """保存正版账号信息到配置文件"""
    profile = payload.get("profile")
    if profile:
        _auth.save_profile(profile)
        return {"ok": True, "message": "账号信息已保存"}
    return {"ok": False, "error": "缺少profile参数"}

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
@app.get("/api/minecraft/versions")
def api_mc_versions():
    return _download.get_minecraft_versions()

@app.post("/api/minecraft/download")
def api_mc_download(payload: Dict):
    version_id = payload.get("version_id")
    custom_name = payload.get("custom_name")
    ok = _download.download_minecraft_version(version_id, custom_name)
    return {"ok": ok}

@app.post("/api/minecraft/download-with-loader")
def api_mc_download_loader(payload: Dict):
    mc_version = payload.get("mc_version")
    loader_type = payload.get("loader_type")
    loader_version = payload.get("loader_version")
    fabric_api_version = payload.get("fabric_api_version")
    custom_name = payload.get("custom_name")
    ok = _download.download_minecraft_version_with_loader(
        mc_version, loader_type, loader_version, fabric_api_version, custom_name
    )
    return {"ok": ok}

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
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()
    ProcessHelper.wait_for_port(Config.WEB_PORT, timeout=30)
    start_gui()
