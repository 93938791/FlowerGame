<template>
  <ClientOnly>
    <div class="qq-layout">
      <!-- 消息提示 -->
      <div v-if="toast.show" class="toast" :class="toast.type">
        <span class="toast-icon">{{ toast.type === 'success' ? '✓' : toast.type === 'error' ? '✗' : 'ℹ' }}</span>
        <span class="toast-message">{{ toast.message }}</span>
      </div>
      
      <!-- 设备代码登录弹窗 -->
      <div v-if="deviceCodeData" class="modal-overlay device-code-modal" @click="cancelDeviceAuth">
        <div class="modal-content device-code-content" @click.stop>
          <div class="device-code-header">
            <h3>🔐 Microsoft 登录</h3>
            <button @click="cancelDeviceAuth" class="modal-close">×</button>
          </div>
          
          <div class="device-code-body">
            <!-- 登录说明 -->
            <div class="login-instruction">
              <div class="instruction-icon">ℹ️</div>
              <div class="instruction-text">点击下方按钮将自动复制代码并打开登录页面</div>
            </div>
            
            <!-- 代码显示 -->
            <div class="code-display-large">
              <div class="code-label">登录代码</div>
              <div class="code-value-large">{{ deviceCodeData.user_code }}</div>
            </div>
            
            <!-- 一键复制并打开按钮 -->
            <div class="open-login-section">
              <button @click="copyAndOpen" class="qq-btn qq-btn-success qq-btn-block qq-btn-large">
                🚀 复制代码并打开登录页面
              </button>
              <div class="open-hint">代码会自动复制，在新窗口中直接粘贴即可</div>
            </div>
            
            <!-- 等待状态 -->
            <div class="auth-waiting">
              <div class="waiting-spinner"></div>
              <div class="waiting-text">{{ authProgress }}</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 离线登录弹窗 -->
      <div v-if="showOfflineLogin" class="modal-overlay" @click="showOfflineLogin = false">
        <div class="modal-content offline-login-modal" @click.stop>
          <div class="device-code-header">
            <h3>👤 离线登录</h3>
            <button @click="showOfflineLogin = false" class="modal-close">×</button>
          </div>
          <div class="device-code-body">
            <div class="login-instruction">
              <div class="instruction-icon">ℹ️</div>
              <div class="instruction-text">输入一个游戏名称（3-16个字符）</div>
            </div>
            <input 
              v-model="offlineName" 
              placeholder="输入游戏名称" 
              class="qq-input qq-input-large"
              maxlength="16"
              @keyup.enter="confirmOfflineLogin"
            />
            <button @click="confirmOfflineLogin" class="qq-btn qq-btn-success qq-btn-block qq-btn-large" style="margin-top: 16px;">
              ✅ 确认登录
            </button>
          </div>
        </div>
      </div>
      
      <!-- 左侧导航栏 -->
      <div class="sidebar">
        <div class="sidebar-header">
          <div class="logo">
            <span class="logo-icon">🌸</span>
            <span class="logo-text">FlowerGame</span>
          </div>
        </div>
        
        <div class="menu-list">
          <div 
            v-for="item in menuItems" 
            :key="item.id"
            :class="['menu-item', { active: activeMenu === item.id }]"
            @click="activeMenu = item.id"
          >
            <span class="menu-icon">{{ item.icon }}</span>
            <span class="menu-text">{{ item.name }}</span>
          </div>
        </div>
        
        <!-- 账号登录区域 -->
        <div class="sidebar-account">
          <!-- 登录状态显示 -->
          <div v-if="accountInfo || offlineAccount" class="account-card">
            <!-- 3D皮肤预览（正版和离线都显示） -->
            <div class="skin-3d-preview">
              <img 
                v-if="accountInfo" 
                :src="getSkinUrl(accountInfo.id, 'full', 256)" 
                alt="3D皮肤" 
                class="skin-3d" 
              />
              <img 
                v-else-if="offlineAccount" 
                :src="getOfflineSkinUrl('full', 256)" 
                alt="默认皮肤" 
                class="skin-3d" 
              />
            </div>
            
            <div class="account-info">
              <div class="account-name">{{ accountInfo?.name || offlineAccount }}</div>
              <div class="account-badge" :class="accountInfo ? 'premium' : 'offline'">
                {{ accountInfo ? '✓ 正版' : '离线' }}
              </div>
            </div>
            
            <button @click="accountInfo ? logout() : logoutOffline()" class="logout-btn">
              退出登录
            </button>
          </div>
          
          <!-- 登录按钮 -->
          <div v-else class="login-buttons">
            <button 
              @click="startDeviceAuth" 
              class="sidebar-login-btn microsoft"
              :disabled="isAuthenticating || deviceCodeData !== null"
            >
              <span class="btn-icon">🔐</span>
              <span class="btn-text">{{ isAuthenticating ? '请求中...' : '正版登录' }}</span>
            </button>
            <button @click="showOfflineLogin = true" class="sidebar-login-btn offline">
              <span class="btn-icon">👤</span>
              <span class="btn-text">离线登录</span>
            </button>
          </div>
        </div>
        
        <div class="sidebar-footer">
          <!-- 登录状态 -->
          <div class="status-indicator">
            <span class="status-dot" :class="{
              'online': accountInfo || offlineAccount,
              'offline': !accountInfo && !offlineAccount
            }"></span>
            <span class="status-text">
              {{ accountInfo || offlineAccount ? '已登录' : '未登录' }}
            </span>
          </div>
          
          <!-- 网络连接状态 -->
          <div class="status-indicator">
            <span class="status-dot" :class="{
              'online': networkStatus.connected,
              'offline': !networkStatus.connected
            }"></span>
            <span class="status-text">
              {{ networkStatus.connected ? '网络已连接' : '网络未连接' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 右侧内容区域 -->
      <div class="content-area">
        <div class="content-header">
          <h2 class="content-title">{{ currentMenuName }}</h2>
        </div>
        
        <div class="content-body">
          <!-- 网络管理 -->
          <div v-show="activeMenu === 'network'" class="panel">
            <!-- 连接状态和节点管理并排显示 -->
            <div class="panel-row">
              <!-- 连接状态卡片 -->
              <div class="panel-section panel-half">
                <h3 class="section-title">连接状态</h3>
                <div class="status-card" :class="{ connected: networkStatus.connected }">
                  <div class="status-icon">
                    <span v-if="networkStatus.connected">✓</span>
                    <span v-else>○</span>
                  </div>
                  <div class="status-info">
                    <div class="status-label">{{ networkStatus.connected ? '已连接' : '未连接' }}</div>
                    <div class="status-ip">虚拟IP: {{ networkStatus.virtual_ip }}</div>
                  </div>
                </div>
              </div>

              <!-- 节点管理卡片 -->
              <div class="panel-section panel-half">
                <div class="section-header">
                  <h3 class="section-title">节点管理</h3>
                  <button @click="loadNodes" class="qq-btn qq-btn-small">刷新</button>
                </div>
                
                <!-- 节点列表 -->
                <div class="node-list-compact">
                  <div v-if="nodeList.length === 0" class="empty-state-small">
                    <p>暂无自定义节点</p>
                  </div>
                  <div v-else class="node-count">
                    <span class="count-badge">{{ nodeList.length }}</span>
                    <span class="count-text">个自定义节点</span>
                  </div>
                </div>
                
                <!-- 快捷操作 -->
                <div class="quick-actions">
                  <button @click="showNodeModal = true" class="qq-btn qq-btn-primary qq-btn-block">管理节点</button>
                </div>
              </div>
            </div>

            <!-- 节点管理模态框 -->
            <div v-if="showNodeModal" class="modal-overlay" @click="showNodeModal = false">
              <div class="modal-content" @click.stop>
                <div class="modal-header">
                  <h3>节点管理</h3>
                  <button @click="showNodeModal = false" class="modal-close">×</button>
                </div>
                
                <div class="modal-body">
                  <!-- 节点列表 -->
                  <div class="node-list">
                    <div v-if="nodeList.length === 0" class="empty-state">
                      <p>暂无自定义节点</p>
                    </div>
                    <div v-else>
                      <div v-for="(node, index) in nodeList" :key="index" class="node-item" :class="{ selected: node === selectedNode }">
                        <input 
                          type="radio" 
                          :id="'node-' + index" 
                          :value="node" 
                          v-model="selectedNode"
                          @change="selectNode(node)"
                          class="node-radio"
                        />
                        <label :for="'node-' + index" class="node-content">
                          <div class="node-icon">🌐</div>
                          <div class="node-address">{{ node }}</div>
                        </label>
                        <button @click.stop="removeNode(node)" class="qq-btn qq-btn-danger qq-btn-small">删除</button>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 添加节点 -->
                  <div class="add-node-form">
                    <input 
                      v-model="newNodeAddress" 
                      placeholder="输入节点地址，如: tcp://example.com:11010"
                      class="qq-input"
                      @keyup.enter="addNode"
                    />
                    <button @click="addNode" class="qq-btn qq-btn-primary">添加节点</button>
                  </div>
                  
                  <!-- 节点管理操作 -->
                  <div class="node-actions">
                    <button @click="resetNodes" class="qq-btn qq-btn-danger">清空所有节点</button>
                    <button @click="showNodeModal = false" class="qq-btn qq-btn-primary">确定</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 网络配置和流量统计并排显示 -->
            <div class="panel-row">
              <!-- 网络配置 -->
              <div class="panel-section panel-half">
                <h3 class="section-title">网络配置</h3>
                <div class="config-form">
                  <div class="form-row">
                    <label class="form-label">
                      <span class="label-icon">🏠</span>
                      房间名称
                    </label>
                    <div class="input-wrapper">
                      <input 
                        v-model="networkConfig.network_name" 
                        placeholder="输入房间名称"
                        class="qq-input qq-input-enhanced"
                      />
                    </div>
                  </div>
                  <div class="form-row">
                    <label class="form-label">
                      <span class="label-icon">🔒</span>
                      房间密码
                    </label>
                    <div class="input-wrapper">
                      <input 
                        v-model="networkConfig.network_secret" 
                        type="password"
                        placeholder="输入房间密码"
                        class="qq-input qq-input-enhanced"
                      />
                    </div>
                  </div>
                  <div class="button-group">
                    <button 
                      @click="connectNetwork" 
                      class="qq-btn qq-btn-primary" 
                      :disabled="networkStatus.connected || isConnecting"
                    >
                      {{ isConnecting ? '连接中...' : (networkStatus.connected ? '已连接' : '连接房间') }}
                    </button>
                    <button 
                      @click="disconnectNetwork" 
                      class="qq-btn qq-btn-danger" 
                      :disabled="!networkStatus.connected || isDisconnecting"
                    >
                      {{ isDisconnecting ? '断开中...' : '断开连接' }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- 流量统计 -->
              <div class="panel-section panel-half">
                <h3 class="section-title">流量统计</h3>
                <div class="traffic-stats">
                  <div class="traffic-item upload">
                    <div class="traffic-icon">⬆️</div>
                    <div class="traffic-info">
                      <div class="traffic-label">上传</div>
                      <div class="traffic-value">{{ formatBytes(trafficStats.tx_bytes) }}</div>
                      <div class="traffic-speed">{{ formatSpeed(trafficStats.tx_speed) }}</div>
                    </div>
                  </div>
                  <div class="traffic-divider"></div>
                  <div class="traffic-item download">
                    <div class="traffic-icon">⬇️</div>
                    <div class="traffic-info">
                      <div class="traffic-label">下载</div>
                      <div class="traffic-value">{{ formatBytes(trafficStats.rx_bytes) }}</div>
                      <div class="traffic-speed">{{ formatSpeed(trafficStats.rx_speed) }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 在线设备列表 -->
            <div class="panel-section">
              <h3 class="section-title">在线设备</h3>
              <div v-if="peers.length === 0" class="empty-state">
                <p>暂无在线设备</p>
              </div>
              <div v-else class="device-list">
                <div v-for="peer in peers" :key="peer.ipv4 + peer.hostname" class="device-item" :class="{ 'local-device': peer.is_local }">
                  <div class="device-avatar">
                    <img :src="getConnectionIcon(peer.latency)" :alt="getConnectionQuality(peer.latency)" class="connection-icon" />
                  </div>
                  <div class="device-info">
                    <div class="device-name">
                      {{ peer.hostname || '未知设备' }}
                      <span v-if="peer.is_local" class="local-badge">👤 本机</span>
                    </div>
                    <div class="device-ip">{{ peer.ipv4 }}</div>
                  </div>
                  <div class="device-status">
                    <span class="device-latency" :class="getLatencyClass(peer.latency)">{{ peer.latency }}ms</span>
                    <span class="device-badge" :class="getQualityBadgeClass(peer.latency)">{{ getConnectionQuality(peer.latency) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 游戏管理 -->
          <div v-show="activeMenu === 'game'" class="panel">
            <!-- MC版本下载区域 -->
            <div class="panel-section">
              <h3 class="section-title">📦 版本下载</h3>
              
              <div class="download-compact">
                <!-- 版本类型选择 -->
                <div class="version-type-tabs">
                  <button 
                    v-for="type in versionTypes" 
                    :key="type.value"
                    :class="['type-tab', { active: selectedVersionType === type.value }]"
                    @click="selectVersionType(type.value)"
                    :title="type.label"
                  >
                    {{ type.icon }}
                  </button>
                </div>
                
                <!-- 版本选择 -->
                <div class="form-row-compact">
                  <select v-model="versionId" class="qq-select qq-select-compact" @change="onVersionChange">
                    <option value="">选择MC版本</option>
                    <option v-for="ver in filteredVersions" :key="ver.id" :value="ver.id">
                      {{ ver.id }}
                    </option>
                  </select>
                  <button @click="loadVersions" class="qq-btn qq-btn-icon" :disabled="loadingVersions" title="刷新">
                    🔄
                  </button>
                </div>
                
                <!-- 加载器选择 -->
                <div class="form-row-compact" v-if="selectedVersionType !== 'vanilla'">
                  <select v-model="loaderVersion" class="qq-select qq-select-compact">
                    <option value="">加载器版本</option>
                    <option v-for="lv in loaderVersions" :key="lv" :value="lv">{{ lv }}</option>
                  </select>
                </div>
                
                <!-- 自定义名称 -->
                <div class="form-row-compact">
                  <input 
                    v-model="customName" 
                    placeholder="自定义名称（可选）" 
                    class="qq-input qq-input-compact"
                  />
                </div>
                
                <!-- 下载按钮 -->
                <button 
                  @click="startDownload" 
                  class="qq-btn qq-btn-primary qq-btn-block"
                  :disabled="!canDownload || isDownloading"
                >
                  {{ isDownloading ? '⏳ 下载中...' : '⬇️ 开始下载' }}
                </button>
              </div>
            </div>
            
            <!-- 下载进度区 -->
            <div v-if="downloadTasks.length > 0" class="panel-section">
              <h3 class="section-title">📊 下载进度</h3>
              <div class="progress-grid">
                <div 
                  v-for="task in downloadTasks" 
                  :key="task.id"
                  class="progress-card"
                >
                  <div class="progress-header-compact">
                    <span class="progress-name-compact">{{ task.name }}</span>
                    <span class="progress-percentage">{{ task.progress }}%</span>
                  </div>
                  <div class="progress-bar progress-bar-compact">
                    <div 
                      class="progress-bar-fill" 
                      :style="{ width: task.progress + '%' }"
                      :class="{ 
                        'progress-success': task.status === 'completed',
                        'progress-error': task.status === 'failed',
                        'progress-active': task.status === 'downloading'
                      }"
                    ></div>
                  </div>
                  <div class="progress-status-compact">{{ task.statusText }}</div>
                </div>
              </div>
            </div>
            
            <!-- 输出日志 -->
            <div v-if="dlOut || authOut" class="panel-section">
              <h3 class="section-title">📝 日志输出</h3>
              <div class="output-box output-box-compact">
                <pre>{{ dlOut || authOut }}</pre>
              </div>
            </div>
          </div>

          <!-- 存档同步 -->
          <div v-show="activeMenu === 'sync'" class="panel">
            <div class="panel-section">
              <h3 class="section-title">Syncthing 存档同步</h3>
              <div class="button-group">
                <button @click="synStart" class="qq-btn qq-btn-primary">启动同步</button>
                <button @click="synStop" class="qq-btn qq-btn-danger">停止同步</button>
                <button @click="synInfo" class="qq-btn">设备信息</button>
              </div>
              <div v-if="synOut" class="output-box">
                <pre>{{ synOut }}</pre>
              </div>
            </div>
          </div>

          <!-- 游戏联机 -->
          <div v-show="activeMenu === 'multiplayer'" class="panel">
            <div class="panel-section">
              <h3 class="section-title">联机配置</h3>
              <div class="info-card">
                <p>🎮 通过 Easytier 虚拟网络，您可以与好友轻松联机</p>
                <p>📡 请先在「网络管理」中启动 Easytier 网络</p>
                <p>🔗 确保您和好友都已连接到同一虚拟网络</p>
                <p>🎯 本机地址：{{ base }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </ClientOnly>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface Peer {
  ipv4: string
  hostname: string
  latency: string
  connected: boolean
  is_local?: boolean  // 是否是本机
}

const menuItems = [
  { id: 'network', name: '网络管理', icon: '🌐' },
  { id: 'game', name: '游戏管理', icon: '🎮' },
  { id: 'sync', name: '存档同步', icon: '☁️' },
  { id: 'multiplayer', name: '游戏联机', icon: '🎯' }
]

const activeMenu = ref('network')
const currentMenuName = computed(() => {
  return menuItems.find(item => item.id === activeMenu.value)?.name || ''
})

const base = ref('')
onMounted(() => { base.value = `${location.protocol}//${location.host}` })

// 网络管理相关
const networkStatus = ref({
  running: false,
  connected: false,
  virtual_ip: '未连接'
})

const networkConfig = ref({
  network_name: '',
  network_secret: '',
  peers: [] as string[] // 节点列表（从后端缓存读取）
})

const nodeList = ref<string[]>([])
const newNodeAddress = ref('')
const showNodeModal = ref(false)
const selectedNode = ref<string | null>(null)
const peers = ref<Peer[]>([])
const trafficStats = ref({
  tx_bytes: 0,
  rx_bytes: 0,
  tx_speed: 0,
  rx_speed: 0
})

const isConnecting = ref(false) // 连接中状态
const isDisconnecting = ref(false) // 断开中状态

let statusTimer: number | null = null
let trafficTimer: number | null = null
let ws: WebSocket | null = null

// 消息提示
const toast = ref({
  show: false,
  message: '',
  type: 'info' as 'success' | 'error' | 'info'
})

// 显示消息提示
function showToast(message: string, type: 'success' | 'error' | 'info' = 'info') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

// WebSocket 连接
function connectWebSocket() {
  // 如果已经连接，先断开
  if (ws) {
    ws.close()
  }
  
  // 创建 WebSocket 连接
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.hostname}:17890/ws/easytier`
  
  ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    console.log('WebSocket 已连接')
  }
  
  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data)
      
      // 根据消息类型处理
      switch (message.type) {
        case 'status_update':
          networkStatus.value = message.data
          console.log('收到状态更新:', message.data)
          break
        case 'peers_update':
          peers.value = message.data
          console.log('收到设备列表更新:', message.data)
          break
        case 'traffic_update':
          trafficStats.value = message.data
          console.log('收到流量统计更新:', message.data)
          break
      }
    } catch (e) {
      console.error('WebSocket 消息解析失败:', e)
    }
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket 错误:', error)
  }
  
  ws.onclose = () => {
    console.log('WebSocket 已断开')
    // 5秒后尝试重连
    setTimeout(() => {
      if (networkStatus.value.connected) {
        connectWebSocket()
      }
    }, 5000)
  }
}

// 断开 WebSocket
function disconnectWebSocket() {
  if (ws) {
    // 设置一个标志，防止 onclose 事件中的重连逻辑
    ws.onclose = null
    ws.close()
    ws = null
    console.log('WebSocket 已主动断开')
  }
}

// 加载节点列表
async function loadNodes() {
  try {
    const r = await fetch('/api/easytier/nodes')
    if (!r.ok) {
      console.error('加载节点失败:', r.status)
      nodeList.value = []
      networkConfig.value.peers = []
      return
    }
    const result = await r.json()
    nodeList.value = result.nodes || []
    networkConfig.value.peers = result.nodes || []
  } catch (e) {
    console.error('加载节点列表失败:', e)
    nodeList.value = []
    networkConfig.value.peers = []
  }
}

// 添加节点
async function addNode() {
  const node = newNodeAddress.value.trim().replace(/[;,\s]+$/, '') // 移除末尾的分号、逗号和空格
  
  if (!node) {
    showToast('请输入节点地址', 'error')
    return
  }
  
  try {
    const r = await fetch('/api/easytier/nodes/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node })
    })
    
    const result = await r.json()
    
    if (result.ok) {
      newNodeAddress.value = ''
      await loadNodes()
      showToast('节点添加成功', 'success')
    } else {
      showToast(result.error || '添加失败', 'error')
    }
  } catch (e) {
    showToast('添加节点失败', 'error')
  }
}

// 删除节点
async function removeNode(node: string) {
  if (!confirm(`确认删除节点：${node}？`)) {
    return
  }
  
  try {
    const r = await fetch('/api/easytier/nodes/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node })
    })
    
    const result = await r.json()
    
    if (result.ok) {
      await loadNodes()
      showToast('节点删除成功', 'success')
    } else {
      showToast(result.error || '删除失败', 'error')
    }
  } catch (e) {
    showToast('删除节点失败', 'error')
  }
}

// 重置节点（清空所有自定义节点）
async function resetNodes() {
  if (!confirm('确认清空所有节点？清空后将无法连接网络。')) {
    return
  }
  
  try {
    const r = await fetch('/api/easytier/nodes/reset', { method: 'POST' })
    const result = await r.json()
    
    if (result.ok) {
      await loadNodes()
      selectedNode.value = null
      showToast('已清空所有节点', 'success')
    } else {
      showToast('清空失败', 'error')
    }
  } catch (e) {
    showToast('清空失败', 'error')
  }
}

// 选择节点
async function selectNode(node: string) {
  try {
    const r = await fetch('/api/easytier/nodes/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node })
    })
    
    const result = await r.json()
    if (result.ok) {
      console.log('已选择节点:', node)
      // 更新配置中的peers，只使用选中的节点
      networkConfig.value.peers = [node]
    }
  } catch (e) {
    console.error('选择节点失败:', e)
  }
}

// 加载选中的节点
async function loadSelectedNode() {
  try {
    const r = await fetch('/api/easytier/nodes/selected')
    if (r.ok) {
      const result = await r.json()
      selectedNode.value = result.selected_node
      // 如果有选中的节点，更新配置
      if (selectedNode.value) {
        networkConfig.value.peers = [selectedNode.value]
      }
    }
  } catch (e) {
    console.error('加载选中节点失败:', e)
  }
}

// 加载默认配置（从后端缓存读取）
async function loadDefaultConfig() {
  try {
    const r = await fetch('/api/easytier/config')
    if (!r.ok) {
      console.error('加载配置失败:', r.status)
      return
    }
    const config = await r.json()
    networkConfig.value.network_name = config.network_name || ''
    networkConfig.value.network_secret = config.network_secret || ''
    networkConfig.value.peers = config.peers || [] // 保存节点列表到配置中
  } catch (e) {
    console.error('加载配置失败:', e)
  }
}

// 连接网络
async function connectNetwork() {
  // 防止重复点击
  if (isConnecting.value) {
    showToast('正在连接中，请稍候...', 'info')
    return
  }
  
  try {
    isConnecting.value = true
    
    // 检查是否选择了节点
    if (!selectedNode.value) {
      showToast('请先选择一个节点！', 'error')
      showNodeModal.value = true
      return
    }
    
    // 清理节点地址（移除末尾的分号和空格）
    const cleanedNode = selectedNode.value.trim().replace(/[;,\s]+$/, '')
    const peersToUse = [cleanedNode]
    
    console.log('连接配置:', {
      network_name: networkConfig.value.network_name,
      network_secret: networkConfig.value.network_secret,
      peers: peersToUse
    })
    
    const r = await fetch('/api/easytier/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        network_name: networkConfig.value.network_name,
        network_secret: networkConfig.value.network_secret,
        peers: peersToUse
      })
    })
    
    const result = await r.json()
    
    if (result.ok) {
      showToast('连接成功！', 'success')
      // 连接 WebSocket 代替轮询
      connectWebSocket()
    } else {
      showToast(`连接失败: ${result.error}`, 'error')
    }
  } catch (e) {
    showToast(`连接失败: ${e}`, 'error')
  } finally {
    isConnecting.value = false
  }
}

// 断开连接
async function disconnectNetwork() {
  // 防止重复点击
  if (isDisconnecting.value) {
    showToast('正在断开中，请稍候...', 'info')
    return
  }
  
  try {
    isDisconnecting.value = true
    
    const r = await fetch('/api/easytier/stop', { method: 'POST' })
    const result = await r.json()
    
    if (result.ok) {
      // 立即更新状态
      networkStatus.value = {
        running: false,
        connected: false,
        virtual_ip: '未连接'
      }
      
      // 断开 WebSocket
      disconnectWebSocket()
      // 清空数据
      peers.value = []
      trafficStats.value = {
        tx_bytes: 0,
        rx_bytes: 0,
        tx_speed: 0,
        rx_speed: 0
      }
      
      // 所有操作完成后再显示提示
      showToast('已断开连接', 'success')
    } else {
      showToast(`断开失败: ${result.error || '未知错误'}`, 'error')
    }
  } catch (e) {
    showToast(`断开失败: ${e}`, 'error')
  } finally {
    isDisconnecting.value = false
  }
}

// 更新网络状态
async function updateNetworkStatus() {
  try {
    const r = await fetch('/api/easytier/status')
    if (!r.ok) {
      console.error('更新状态失败:', r.status)
      return
    }
    const status = await r.json()
    networkStatus.value = status
  } catch (e) {
    console.error('更新状态失败:', e)
  }
}

// 更新设备列表
async function updatePeers() {
  try {
    const r = await fetch('/api/easytier/peers')
    peers.value = await r.json()
  } catch (e) {
    console.error('更新设备列表失败:', e)
  }
}

// 更新流量统计
async function updateTraffic() {
  try {
    const r = await fetch('/api/easytier/traffic')
    trafficStats.value = await r.json()
  } catch (e) {
    console.error('更新流量统计失败:', e)
  }
}

// 启动自动更新
function startAutoUpdate() {
  if (statusTimer) return
  
  // 每10秒更新一次状态和设备列表（降低频率）
  statusTimer = window.setInterval(() => {
    // 只在页面可见时更新
    if (document.visibilityState === 'visible') {
      updateNetworkStatus()
      updatePeers()
    }
  }, 10000)
  
  // 每5秒更新一次流量（降低频率）
  trafficTimer = window.setInterval(() => {
    // 只在页面可见时更新
    if (document.visibilityState === 'visible') {
      updateTraffic()
    }
  }, 5000)
}

// 停止自动更新
function stopAutoUpdate() {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
  if (trafficTimer) {
    clearInterval(trafficTimer)
    trafficTimer = null
  }
}

// 格式化字节数
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

// 格式化速度
function formatSpeed(bytesPerSecond: number): string {
  if (bytesPerSecond === 0) return '0 B/s'
  if (bytesPerSecond < 1024) return `${bytesPerSecond.toFixed(0)} B/s`
  if (bytesPerSecond < 1024 * 1024) return `${(bytesPerSecond / 1024).toFixed(2)} KB/s`
  return `${(bytesPerSecond / 1024 / 1024).toFixed(2)} MB/s`
}

// 根据延迟获取连接图标
function getConnectionIcon(latency: string): string {
  const ms = parseInt(latency)
  if (isNaN(ms) || latency === '-') return '/web/icons/good.png'  // 本机显示优秀图标
  if (ms < 50) return '/web/icons/good.png'  // 优秀
  if (ms < 100) return '/web/icons/fluid.png' // 流畅
  if (ms < 200) return '/web/icons/laggy.png' // 较慢
  return '/web/icons/drop.png' // 掉线/很慢
}

// 根据延迟获取连接质量文本
function getConnectionQuality(latency: string): string {
  const ms = parseInt(latency)
  if (isNaN(ms)) return '未知'
  if (ms < 50) return '优秀'
  if (ms < 100) return '流畅'
  if (ms < 200) return '较慢'
  return '很慢'
}

// 根据延迟获取延迟文本样式类
function getLatencyClass(latency: string): string {
  const ms = parseInt(latency)
  if (isNaN(ms)) return 'latency-unknown'
  if (ms < 50) return 'latency-good'
  if (ms < 100) return 'latency-fluid'
  if (ms < 200) return 'latency-laggy'
  return 'latency-bad'
}

// 根据延迟获取徽章样式类
function getQualityBadgeClass(latency: string): string {
  const ms = parseInt(latency)
  if (isNaN(ms)) return 'badge-unknown'
  if (ms < 50) return 'badge-good'
  if (ms < 100) return 'badge-fluid'
  if (ms < 200) return 'badge-laggy'
  return 'badge-bad'
}

// 页面加载时初始化
onMounted(async () => {
  await loadDefaultConfig() // 自动加载默认配置
  await loadNodes() // 加载节点列表
  await loadSelectedNode() // 加载选中的节点
  await updateNetworkStatus()
  
  // 如果已经连接，启动 WebSocket 连接
  if (networkStatus.value.connected) {
    connectWebSocket()
  }
})

// 页面卸载时清理资源
onUnmounted(() => {
  disconnectWebSocket()
  stopAutoUpdate()
})

// 其他功能区域
const authCode = ref('')
const authOut = ref('')
const versionId = ref('')
const customName = ref('')
const dlOut = ref('')
const synOut = ref('')
const etOut = ref('')

// 登录相关状态
const loginType = ref<'microsoft' | 'offline'>('microsoft')
const accountInfo = ref<any>(null)
const offlineAccount = ref<string | null>(null)
const offlineName = ref('')
const deviceCodeData = ref<any>(null)
const authProgress = ref('等待授权...')
const isAuthenticating = ref(false)
const showOfflineLogin = ref(false)
let pollTimer: number | null = null // 轮询定时器

// 皮肤API配置 - 使用 Visage（支持3D渲染，国内有CDN）
const SKIN_API_BASE = 'https://visage.surgeplay.com'

// 生成皮肤URL的函数（优先使用缓存）
function getSkinUrl(uuid: string, type: 'avatar' | 'bust' | 'full' = 'full', size: number = 256) {
  if (!uuid) return ''
  
  // 如果accountInfo中有缓存的URL，优先使用
  if (type === 'full' && accountInfo.value?.skin_url) {
    return accountInfo.value.skin_url
  }
  if (type === 'avatar' && accountInfo.value?.avatar_url) {
    return accountInfo.value.avatar_url
  }
  
  // visage.surgeplay.com 支持: 
  // /avatar/{size}/{uuid} - 头像
  // /bust/{size}/{uuid} - 半身像  
  // /full/{size}/{uuid} - 3D全身像
  return `${SKIN_API_BASE}/${type}/${size}/${uuid}`
}

// 离线账号使用默认 Steve 皮肤
function getOfflineSkinUrl(type: 'avatar' | 'bust' | 'full' = 'full', size: number = 256) {
  // 使用 Minecraft 默认 Steve 皮肤的 UUID
  const steveSkinUuid = 'c06f89064c8a49119c29ea1dbd1aab82' // Steve 默认皮肤
  return `${SKIN_API_BASE}/${type}/${size}/${steveSkinUuid}`
}

// 页面加载时恢复登录状态
onMounted(() => {
  loadCachedLoginInfo()
})

// 从后端加载登录信息
async function loadCachedLoginInfo() {
  try {
    // 从后端获取缓存的登录信息
    const r = await fetch('/api/auth/status')
    const result = await r.json()
    
    if (result.ok && result.profile) {
      accountInfo.value = result.profile
      console.log('已从后端恢复正版账号:', result.profile.name)
    } else if (result.offline_account) {
      offlineAccount.value = result.offline_account
      console.log('已从后端恢复离线账号:', result.offline_account)
    }
  } catch (e) {
    console.error('从后端恢复登录信息失败:', e)
  }
}

// 保存登录信息到后端
async function saveAccountToCache(account: any) {
  try {
    await fetch('/api/auth/save-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile: account })
    })
    console.log('已保存正版账号到后端:', account.name)
  } catch (e) {
    console.error('保存账号信息到后端失败:', e)
  }
}

async function saveOfflineToCache(username: string) {
  try {
    await fetch('/api/auth/save-offline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username })
    })
    console.log('已保存离线账号到后端:', username)
  } catch (e) {
    console.error('保存离线账号到后端失败:', e)
  }
}

// 清除缓存
async function clearAccountCache() {
  try {
    await fetch('/api/auth/clear-profile', { method: 'POST' })
  } catch (e) {
    console.error('清除账号缓存失败:', e)
  }
}

async function clearOfflineCache() {
  try {
    await fetch('/api/auth/clear-offline', { method: 'POST' })
  } catch (e) {
    console.error('清除离线账号缓存失败:', e)
  }
}

// 版本下载相关
const versionTypes = [
  { label: '原版', value: 'vanilla', icon: '🎯' },
  { label: 'Fabric', value: 'fabric', icon: '📦' },
  { label: 'Forge', value: 'forge', icon: '🔧' },
  { label: 'NeoForge', value: 'neoforge', icon: '🌟' },
  { label: 'OptiFine', value: 'optifine', icon: '👍' }
]
const selectedVersionType = ref('vanilla')
const loaderType = ref('fabric')
const loaderVersion = ref('')
const loaderVersions = ref<string[]>([])
const mcVersions = ref<any[]>([])
const filteredVersions = computed(() => mcVersions.value)
const loadingVersions = ref(false)
const isDownloading = ref(false)
const downloadTasks = ref<any[]>([])
const canDownload = computed(() => {
  if (selectedVersionType.value === 'vanilla') {
    return versionId.value.length > 0
  }
  return versionId.value.length > 0 && loaderVersion.value.length > 0
})

async function authorize() {
  const r = await fetch('/api/auth/authorize-url')
  const j = await r.json()
  authOut.value = JSON.stringify(j, null, 2)
  if (j.url) window.open(j.url, '_blank')
}

async function authenticate() {
  let code = authCode.value.trim()
  
  // 如果用户粘贴的是完整URL，提取code参数
  if (code.includes('?code=') || code.includes('&code=')) {
    try {
      const url = new URL(code)
      const extractedCode = url.searchParams.get('code')
      if (extractedCode) {
        code = extractedCode
        authCode.value = code // 更新输入框显示提取后的code
        showToast('已从 URL 中提取 code 参数', 'info')
      }
    } catch (e) {
      // 如果不是合法URL，尝试用正则提取
      const match = code.match(/[?&]code=([^&]+)/)
      if (match && match[1]) {
        code = match[1]
        authCode.value = code
        showToast('已从 URL 中提取 code 参数', 'info')
      }
    }
  }
  
  if (!code) {
    showToast('请输入授权代码或URL', 'error')
    return
  }
  
  try {
    const r = await fetch('/api/auth/authenticate', { 
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' }, 
      body: JSON.stringify({ auth_code: code }) 
    })
    const result = await r.json()
    authOut.value = JSON.stringify(result, null, 2)
    
    if (result.ok && result.profile) {
      accountInfo.value = result.profile
      saveAccountToCache(result.profile) // 保存到缓存
      authCode.value = '' // 清空输入框
      showToast(`欢迎 ${result.profile.name}! 登录成功`, 'success')
    } else if (result.error) {
      showToast(`登录失败: ${result.error}`, 'error')
    } else {
      showToast('登录失败，请重试', 'error')
    }
  } catch (e: any) {
    showToast(`请求失败: ${e.message}`, 'error')
  }
}

async function authStatus() {
  const r = await fetch('/api/auth/status')
  const result = await r.json()
  authOut.value = JSON.stringify(result, null, 2)
  if (result.profile) {
    accountInfo.value = result.profile
  }
}

function logout() {
  accountInfo.value = null
  authOut.value = ''
  authCode.value = ''
  clearAccountCache() // 清除缓存
  showToast('已退出登录', 'info')
}

function loginOffline() {
  if (offlineName.value.length < 3 || offlineName.value.length > 16) {
    showToast('游戏名称长度必须在3-16个字符之间', 'error')
    return
  }
  offlineAccount.value = offlineName.value
  offlineName.value = ''
  showToast('离线登录成功', 'success')
}

function confirmOfflineLogin() {
  if (offlineName.value.length < 3 || offlineName.value.length > 16) {
    showToast('游戏名称长度必须在3-16个字符之间', 'error')
    return
  }
  offlineAccount.value = offlineName.value
  saveOfflineToCache(offlineName.value) // 保存到缓存
  offlineName.value = ''
  showOfflineLogin.value = false
  showToast(`欢迎 ${offlineAccount.value}! 离线登录成功`, 'success')
}

function logoutOffline() {
  offlineAccount.value = null
  clearOfflineCache() // 清除缓存
  showToast('已退出登录', 'info')
}

// 设备代码登录方法
async function startDeviceAuth() {
  // 防止重复请求
  if (isAuthenticating.value || deviceCodeData.value) {
    showToast('登录请求正在进行中，请勿重复点击', 'info')
    return
  }
  
  isAuthenticating.value = true
  authProgress.value = '正在获取设备代码...'
  
  try {
    const r = await fetch('/api/auth/device-code')
    const result = await r.json()
    
    if (!result.ok || !result.data) {
      showToast(`获取设备代码失败: ${result.error || '未知错误'}`, 'error')
      isAuthenticating.value = false
      return
    }
    
    deviceCodeData.value = result.data
    isAuthenticating.value = false
    authProgress.value = '请点击按钮打开登录页面...'
    
    // 自动复制代码到剪贴板
    copyCodeToClipboard(deviceCodeData.value.user_code)
    
    // 不自动打开浏览器，让用户手动点击
    // window.open(deviceCodeData.value.verification_uri, '_blank')
    
    // 开始轮询
    pollDeviceAuth()
  } catch (e: any) {
    showToast(`请求失败: ${e.message}`, 'error')
    isAuthenticating.value = false
  }
}

function copyCodeToClipboard(code: string) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(code)
      .then(() => {
        console.log('代码已复制到剪贴板:', code)
      })
      .catch(err => {
        console.error('复制失败:', err)
        // Fallback
        fallbackCopyCode(code)
      })
  } else {
    // Fallback for older browsers
    fallbackCopyCode(code)
  }
}

function fallbackCopyCode(code: string) {
  const textarea = document.createElement('textarea')
  textarea.value = code
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    document.execCommand('copy')
    console.log('代码已复制到剪贴板 (fallback):', code)
  } catch (err) {
    console.error('复制失败 (fallback):', err)
  }
  document.body.removeChild(textarea)
}

async function pollDeviceAuth() {
  if (!deviceCodeData.value) return
  
  authProgress.value = '等待用户授权...'
  
  // 清除之前的定时器
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  
  // 开始定时轮询（每5秒一次）
  pollTimer = window.setInterval(async () => {
    if (!deviceCodeData.value) {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
      return
    }
    
    try {
      const r = await fetch('/api/auth/device-auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_code: deviceCodeData.value.device_code })
      })
      const result = await r.json()
      
      if (result.ok && result.profile) {
        // 登录成功
        accountInfo.value = result.profile
        saveAccountToCache(result.profile) // 保存到缓存
        deviceCodeData.value = null
        isAuthenticating.value = false // 重置认证状态
        if (pollTimer) {
          clearInterval(pollTimer)
          pollTimer = null
        }
        showToast(`欢迎 ${result.profile.name}! 登录成功`, 'success')
      } else if (result.error && result.error !== 'authorization_pending') {
        // 其他错误（非authorization_pending）
        // 检查是否已经登录成功，避免显示误导性错误
        if (!accountInfo.value) {
          showToast(`登录失败: ${result.error}`, 'error')
        }
        deviceCodeData.value = null
        isAuthenticating.value = false
        if (pollTimer) {
          clearInterval(pollTimer)
          pollTimer = null
        }
      }
      // 如果是 authorization_pending，继续轮询
    } catch (e: any) {
      console.error('轮询错误:', e)
    }
  }, 5000) // 每5秒轮询一次
}

function cancelDeviceAuth() {
  // 清除轮询定时器
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  deviceCodeData.value = null
  isAuthenticating.value = false
  showToast('已取消登录', 'info')
}

function openUrl(url: string) {
  window.open(url, '_blank')
  // 打开后更新状态
  if (authProgress.value === '请点击按钮打开登录页面...') {
    authProgress.value = '等待用户在浏览器中完成授权...'
  }
}

function copyAndOpen() {
  if (!deviceCodeData.value) return
  
  // 先复制代码
  copyCodeToClipboard(deviceCodeData.value.user_code)
  
  // 稍微延迟后打开窗口，确保复制成功
  setTimeout(() => {
    window.open(deviceCodeData.value.verification_uri, '_blank')
    authProgress.value = '等待用户在浏览器中完成授权...'
  }, 100)
}

function copyCode(code: string) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(code)
    showToast('代码已复制到剪贴板', 'success')
  } else {
    // Fallback
    const textarea = document.createElement('textarea')
    textarea.value = code
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    showToast('代码已复制到剪贴板', 'success')
  }
}

async function loadVersions() {
  loadingVersions.value = true
  try {
    const r = await fetch('/api/minecraft/versions')
    mcVersions.value = await r.json()
    showToast(`已加载 ${mcVersions.value.length} 个版本`, 'success')
  } catch (e: any) {
    showToast(`加载失败: ${e.message}`, 'error')
  } finally {
    loadingVersions.value = false
  }
}

function selectVersionType(type: string) {
  selectedVersionType.value = type
  loaderVersion.value = ''
  loaderVersions.value = []
  if (type !== 'vanilla') {
    loaderType.value = type
  }
}

function onVersionChange() {
  if (selectedVersionType.value !== 'vanilla' && versionId.value) {
    loadLoaderVersions()
  }
}

function onLoaderChange() {
  loaderVersion.value = ''
  loaderVersions.value = []
  if (versionId.value) {
    loadLoaderVersions()
  }
}

async function loadLoaderVersions() {
  loaderVersions.value = ['0.15.11', '0.15.10', '0.15.9', '0.15.7']
}

async function startDownload() {
  isDownloading.value = true
  dlOut.value = ''
  
  downloadTasks.value = [
    { id: 'version_info', name: '📄 版本信息', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'client_jar', name: '🎮 JAR', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'libraries', name: '📦 依赖库', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'assets', name: '🎨 资源', progress: 0, status: 'pending', statusText: '等待中...' }
  ]
  
  try {
    if (selectedVersionType.value === 'vanilla') {
      const r = await fetch('/api/minecraft/download', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          version_id: versionId.value.trim(), 
          custom_name: customName.value.trim() || null 
        }) 
      })
      const result = await r.json()
      dlOut.value = JSON.stringify(result, null, 2)
      await simulateProgress()
    } else {
      const r = await fetch('/api/minecraft/download-with-loader', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          mc_version: versionId.value.trim(),
          loader_type: loaderType.value,
          loader_version: loaderVersion.value,
          custom_name: customName.value.trim() || null
        }) 
      })
      const result = await r.json()
      dlOut.value = JSON.stringify(result, null, 2)
      await simulateProgress()
    }
    showToast('下载完成', 'success')
  } catch (e: any) {
    dlOut.value = `下载失败: ${e.message}`
    showToast(`下载失败: ${e.message}`, 'error')
    downloadTasks.value.forEach(task => {
      if (task.status === 'downloading') {
        task.status = 'failed'
        task.statusText = '下载失败'
      }
    })
  } finally {
    isDownloading.value = false
  }
}

async function simulateProgress() {
  for (const task of downloadTasks.value) {
    task.status = 'downloading'
    task.statusText = '下载中...'
    
    for (let i = 0; i <= 100; i += 10) {
      await new Promise(resolve => setTimeout(resolve, 150))
      task.progress = i
      if (i === 100) {
        task.status = 'completed'
        task.statusText = '✓ 完成'
      }
    }
  }
}

async function listVersions() {
  await loadVersions()
}

async function downloadVersion() {
  await startDownload()
}
async function synStart() {
  const r = await fetch('/api/syncthing/start', { method: 'POST' })
  synOut.value = await r.text()
}
async function synStop() {
  const r = await fetch('/api/syncthing/stop', { method: 'POST' })
  synOut.value = await r.text()
}
async function synInfo() {
  const r1 = await fetch('/api/syncthing/device-id')
  const id = await r1.json()
  const r2 = await fetch('/api/syncthing/traffic')
  const traf = await r2.json()
  synOut.value = JSON.stringify({ id, traf }, null, 2)
}
async function etStart() {
  const r = await fetch('/api/easytier/start', { method: 'POST' })
  etOut.value = await r.text()
}
async function etStop() {
  const r = await fetch('/api/easytier/stop', { method: 'POST' })
  etOut.value = await r.text()
}
async function etPeers() {
  const r = await fetch('/api/easytier/peers')
  etOut.value = JSON.stringify(await r.json(), null, 2)
}
async function etTraffic() {
  const r = await fetch('/api/easytier/traffic')
  etOut.value = JSON.stringify(await r.json(), null, 2)
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Microsoft YaHei', 'PingFang SC', 'Helvetica Neue', Arial, sans-serif;
  overflow: hidden;
}

.qq-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background: #f5f5f5;
  position: relative;
}

/* 消息提示样式 */
.toast {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 10000;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.toast.success {
  background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(168, 224, 99, 0.5);
}

.toast.error {
  background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(255, 107, 107, 0.5);
}

.toast.info {
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(0, 217, 255, 0.5);
}

.toast-icon {
  font-size: 16px;
  font-weight: bold;
}

.toast-message {
  flex: 1;
}

/* 侧边栏样式 - 游戏风格渐变 */
.sidebar {
  width: 240px;
  background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.2);
}

.sidebar-header {
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  color: white;
}

.logo-icon {
  font-size: 32px;
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
}

.menu-list {
  flex: 1;
  padding: 12px 0;
  overflow-y: auto;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  color: rgba(255, 255, 255, 0.9);
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  margin: 4px 8px;
  border-radius: 8px;
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.menu-item.active {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  font-weight: 600;
}

.menu-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 24px;
  background: linear-gradient(180deg, #00d9ff 0%, #00b8d4 100%);
  border-radius: 0 2px 2px 0;
  box-shadow: 0 0 12px rgba(0, 217, 255, 0.8);
}

.menu-icon {
  font-size: 20px;
}

.menu-text {
  font-size: 15px;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 侧边栏账号区域 */
.sidebar-account {
  padding: 12px;
  margin-top: auto;
}

.account-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 20px 16px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.account-card:hover {
  background: rgba(255, 255, 255, 0.12);
  transform: translateY(-2px);
}

/* 3D皮肤预览 - 简洁无边框设计 */
.skin-3d-preview {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 8px 0;
}

.skin-3d {
  width: 100%;
  height: auto;
  max-width: 180px;
  image-rendering: pixelated;
  filter: drop-shadow(0 8px 16px rgba(0, 0, 0, 0.4));
  transition: all 0.3s ease;
}

.skin-3d:hover {
  transform: scale(1.08) translateY(-4px);
  filter: drop-shadow(0 12px 24px rgba(0, 0, 0, 0.5));
}

/* 账号信息 */
.account-info {
  width: 100%;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.account-name {
  font-size: 16px;
  font-weight: 700;
  color: white;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.account-badge {
  display: inline-block;
  align-self: center;
  padding: 5px 14px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 12px;
}

.account-badge.premium {
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 217, 255, 0.5);
  font-weight: 700;
}

.account-badge.offline {
  background: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.3);
}

/* 退出按钮 */
.logout-btn {
  width: 100%;
  padding: 8px 16px;
  background: rgba(244, 67, 54, 0.2);
  color: white;
  border: 1px solid rgba(244, 67, 54, 0.4);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.logout-btn:hover {
  background: rgba(244, 67, 54, 0.4);
  border-color: rgba(244, 67, 54, 0.6);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(244, 67, 54, 0.3);
}

.login-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar-login-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.sidebar-login-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.sidebar-login-btn.microsoft {
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 217, 255, 0.3);
  font-weight: 700;
}

.sidebar-login-btn.microsoft:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 217, 255, 0.6);
}

.sidebar-login-btn.offline {
  background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(168, 224, 99, 0.3);
  font-weight: 600;
}

.sidebar-login-btn.offline:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(168, 224, 99, 0.6);
}

.sidebar-login-btn .btn-icon {
  font-size: 16px;
}

.sidebar-login-btn .btn-text {
  font-size: 13px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: white;
  font-size: 12px;
  padding: 4px 0;
}

/* 状态指示灯 - 在线状态（绿色呼吸灯） */
.status-dot.online {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
  animation: pulse 2s infinite;
  box-shadow: 0 0 8px rgba(168, 224, 99, 0.8);
}

/* 状态指示灯 - 离线状态（灰色呼吸灯） */
.status-dot.offline {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #95a5a6 0%, #7f8c8d 100%);
  animation: pulse 2s infinite;
  box-shadow: 0 0 8px rgba(149, 165, 166, 0.6);
}

/* 呼吸灯动画 */
@keyframes pulse {
  0%, 100% { 
    opacity: 1;
    transform: scale(1);
  }
  50% { 
    opacity: 0.5;
    transform: scale(0.95);
  }
}

/* 内容区域样式 */
.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
  overflow: hidden;
}

.content-header {
  padding: 24px 32px;
  background: white;
  border-bottom: 1px solid #e8e8e8;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.content-title {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.content-body {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}

.panel {
  animation: fadeIn 0.3s ease;
}

.panel-row {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.panel-half {
  flex: 1;
  min-width: 0;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.panel-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.3s ease;
  display: flex;
  flex-direction: column;
}

.panel-section:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 2px solid #00d9ff;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header .section-title {
  margin: 0;
  padding: 0;
  border: none;
}

.button-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

/* 自定义按钮样式 */
.qq-btn {
  border: none;
  border-radius: 6px;
  font-size: 14px;
  padding: 0 20px;
  height: 36px;
  cursor: pointer;
  transition: all 0.3s ease;
  background: #fff;
  color: #333;
  border: 1px solid #dcdfe6;
  font-family: inherit;
}

.qq-btn:hover {
  background: #f5f7fa;
  border-color: #c0c4cc;
}

.qq-btn:active {
  transform: translateY(1px);
}

.qq-btn-primary {
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
  border: none;
  box-shadow: 0 2px 8px rgba(0, 217, 255, 0.3);
  font-weight: 600;
}

.qq-btn-primary:hover {
  background: linear-gradient(135deg, #00c4ea 0%, #00a3bf 100%);
  box-shadow: 0 4px 12px rgba(0, 217, 255, 0.5);
  transform: translateY(-1px);
}

.qq-btn-danger {
  background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
  color: white;
  border: none;
  box-shadow: 0 2px 8px rgba(255, 107, 107, 0.3);
}

.qq-btn-danger:hover {
  background: linear-gradient(135deg, #ff5555 0%, #dd4a5a 100%);
  box-shadow: 0 4px 12px rgba(255, 107, 107, 0.5);
  transform: translateY(-1px);
}

.qq-btn-success {
  background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
  color: white;
  border: none;
  box-shadow: 0 2px 8px rgba(168, 224, 99, 0.3);
}

.qq-btn-success:hover {
  background: linear-gradient(135deg, #95d450 0%, #4a9625 100%);
  box-shadow: 0 4px 12px rgba(168, 224, 99, 0.5);
  transform: translateY(-1px);
}

.qq-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.qq-btn-small {
  height: 32px;
  padding: 0 16px;
  font-size: 13px;
}

.input-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

/* 自定义输入框样式 */
.qq-input {
  flex: 1;
  min-width: 200px;
  height: 36px;
  padding: 0 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  transition: all 0.3s ease;
  outline: none;
}

.qq-input:focus {
  border-color: #00d9ff;
  box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.15);
}

.qq-input::placeholder {
  color: #c0c4cc;
}

.input-wrapper {
  position: relative;
  width: 100%;
}

.qq-input-enhanced {
  width: 100%;
  height: 42px;
  padding: 0 16px;
  font-size: 15px;
  background: #f8f9fa;
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.qq-input-enhanced:hover {
  background: #fff;
  border-color: #d0d0d0;
}

.qq-input-enhanced:focus {
  background: #fff;
  border-color: #00d9ff;
  box-shadow: 0 0 0 4px rgba(0, 217, 255, 0.15);
  transform: translateY(-1px);
}

.qq-input-enhanced::placeholder {
  color: #aaa;
  font-size: 14px;
}

.qq-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.3s ease;
  outline: none;
  resize: vertical;
}

.qq-textarea:focus {
  border-color: #00d9ff;
  box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.15);
}

.qq-textarea::placeholder {
  color: #c0c4cc;
}

/* 网络管理特定样式 */
.status-card {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 2px solid #e8e8e8;
  transition: all 0.3s ease;
}

.status-card.connected {
  background: linear-gradient(135deg, #d4f4dd 0%, #e8f9ed 100%);
  border-color: #51cf66;
}

.status-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  color: #999;
  transition: all 0.3s ease;
}

.status-card.connected .status-icon {
  background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(168, 224, 99, 0.4);
}

.status-info {
  flex: 1;
}

.status-label {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.status-ip {
  font-size: 14px;
  color: #666;
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.label-icon {
  font-size: 16px;
}

.form-tip {
  font-size: 12px;
  font-weight: normal;
  color: #999;
}

.node-list {
  margin-bottom: 16px;
}

.node-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e8e8e8;
  margin-bottom: 8px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.node-item:hover {
  background: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.node-item.selected {
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  border: 2px solid #4a90e2;
  box-shadow: 0 2px 8px rgba(74, 144, 226, 0.3);
}

.node-radio {
  width: 18px;
  height: 18px;
  cursor: pointer;
  flex-shrink: 0;
  accent-color: #4a90e2;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  cursor: pointer;
}

.node-icon {
  font-size: 20px;
}

.node-address {
  flex: 1;
  font-size: 14px;
  color: #333;
  word-break: break-all;
}

.add-node-form {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.add-node-form .qq-input {
  flex: 1;
}

.node-actions {
  display: flex;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px dashed #e8e8e8;
}

/* 节点管理简化显示 */
.node-list-compact {
  margin: 16px 0;
}

.empty-state-small {
  text-align: center;
  padding: 20px;
  color: #999;
  font-size: 13px;
}

.empty-state-small p {
  margin: 0;
}

.node-count {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, #e3f2fd 0%, #f5f5f5 100%);
  border-radius: 8px;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: #4a90e2;
  color: white;
  border-radius: 50%;
  font-size: 18px;
  font-weight: 600;
}

.count-text {
  font-size: 14px;
  color: #666;
}

.quick-actions {
  margin-top: 16px;
}

.qq-btn-block {
  width: 100%;
  display: block;
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e8e8e8;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: none;
  background: #f5f5f5;
  border-radius: 50%;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  color: #666;
  transition: all 0.3s ease;
}

.modal-close:hover {
  background: #e8e8e8;
  color: #333;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.traffic-stats {
  display: flex;
  gap: 16px;
  align-items: stretch;
  flex: 1;
}

.traffic-item {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: 10px;
  border: 1px solid #e8e8e8;
  transition: all 0.3s ease;
  min-height: 100px;
}

.traffic-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.traffic-item.upload {
  background: linear-gradient(135deg, #e3f2fd 0%, #ffffff 100%);
  border-left: 3px solid #2196f3;
}

.traffic-item.download {
  background: linear-gradient(135deg, #e8f5e9 0%, #ffffff 100%);
  border-left: 3px solid #4caf50;
}

.traffic-icon {
  font-size: 40px;
  line-height: 1;
  flex-shrink: 0;
}

.traffic-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.traffic-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
  font-weight: 500;
}

.traffic-value {
  font-size: 26px;
  font-weight: 700;
  color: #333;
  margin-bottom: 4px;
  font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}

.traffic-item.upload .traffic-value {
  color: #2196f3;
}

.traffic-item.download .traffic-value {
  color: #4caf50;
}

.traffic-speed {
  font-size: 12px;
  color: #999;
  font-weight: 500;
  white-space: nowrap;
}

.traffic-divider {
  width: 2px;
  background: linear-gradient(to bottom, transparent, #e8e8e8, transparent);
  align-self: stretch;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}

.device-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
  transition: all 0.3s ease;
}

.device-item:hover {
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 本机设备样式 */
.local-device {
  background: linear-gradient(to right, #e6f7ff, #f5f5f5);
  border-left: 3px solid #1890ff;
}

.local-badge {
  margin-left: 8px;
  padding: 2px 8px;
  background: #1890ff;
  color: white;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}

.device-avatar {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 50%;
  border: 2px solid #e8e8e8;
  padding: 4px;
}

.connection-icon {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.device-icon {
  font-size: 32px;
}

.device-info {
  flex: 1;
}

.device-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.device-ip {
  font-size: 14px;
  color: #666;
}

.relay-node {
  color: #1890ff;
  font-weight: 500;
  font-style: italic;
}

.device-status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.device-latency {
  font-size: 12px;
  font-weight: 600;
}

/* 延迟样式 */
.latency-good {
  color: #52c41a;
}

.latency-fluid {
  color: #1890ff;
}

.latency-laggy {
  color: #faad14;
}

.latency-bad {
  color: #ff4d4f;
}

.latency-unknown {
  color: #999;
}

.device-badge {
  padding: 4px 12px;
  color: white;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

/* 徽章样式 */
.badge-good {
  background: #52c41a;
}

.badge-fluid {
  background: #1890ff;
}

.badge-laggy {
  background: #faad14;
}

.badge-bad {
  background: #ff4d4f;
}

.badge-unknown {
  background: #999;
}

.output-box {
  background: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
  max-height: 400px;
  overflow: auto;
}

.output-box pre {
  margin: 0;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.info-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 24px;
  border-radius: 12px;
  line-height: 2;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
  font-weight: 500;
}

.info-card p {
  margin: 8px 0;
  font-size: 15px;
}

/* 滚动条美化 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 游戏管理 - 紧凑版样式 */
.login-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}

.tab-btn {
  flex: 1;
  padding: 8px 12px;
  border: 2px solid #dcdfe6;
  background: white;
  color: #606266;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
  font-weight: 500;
}

.tab-btn:hover {
  border-color: #4a90e2;
  color: #4a90e2;
}

.tab-btn.active {
  border-color: #00d9ff;
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
  font-weight: 700;
  box-shadow: 0 2px 8px rgba(0, 217, 255, 0.4);
}

.login-content {
  animation: fadeIn 0.3s ease;
}

.account-status {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  border-radius: 8px;
  color: white;
  box-shadow: 0 2px 8px rgba(0, 217, 255, 0.3);
}

.account-avatar img {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 2px solid white;
}

.offline-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
  color: white;
  border: 2px solid white;
}

.account-details {
  flex: 1;
}

.account-name {
  font-size: 15px;
  font-weight: 600;
}

.account-type {
  font-size: 12px;
  opacity: 0.9;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.login-step {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.step-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0, 217, 255, 0.4);
}

.step-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.step-hint {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}

.step-example {
  font-size: 11px;
  color: #909399;
  font-family: 'Consolas', 'Monaco', monospace;
  background: #f5f5f5;
  padding: 4px 8px;
  border-radius: 4px;
  margin-top: 2px;
  word-break: break-all;
}

.input-group-vertical {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-with-btn {
  display: flex;
  gap: 6px;
}

.qq-input-compact {
  flex: 1;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
}

.qq-input-compact:focus {
  border-color: #4a90e2;
  outline: none;
}

.qq-btn-small {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}

.qq-btn-block {
  width: 100%;
}

.qq-btn-icon {
  width: 32px;
  height: 32px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.download-compact {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.version-type-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: #f5f5f5;
  border-radius: 6px;
}

.type-tab {
  flex: 1;
  padding: 6px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 18px;
  transition: all 0.2s ease;
}

.type-tab:hover {
  background: rgba(74, 144, 226, 0.1);
}

.type-tab.active {
  background: #4a90e2;
  transform: scale(1.1);
}

.form-row-compact {
  display: flex;
  gap: 6px;
}

.qq-select-compact {
  flex: 1;
  height: 32px;
  padding: 0 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
  background: white;
  cursor: pointer;
}

.qq-select-compact:focus {
  border-color: #4a90e2;
  outline: none;
}

.progress-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.progress-card {
  background: white;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.progress-header-compact {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.progress-name-compact {
  font-weight: 500;
  color: #333;
  font-size: 13px;
}

.progress-percentage {
  font-weight: 600;
  color: #4a90e2;
  font-size: 13px;
}

.progress-bar-compact {
  height: 6px;
  background: #e8e8e8;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}

.progress-bar-fill {
  height: 100%;
  background: #4a90e2;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-bar-fill.progress-active {
  background: linear-gradient(90deg, #4a90e2 0%, #357abd 50%, #4a90e2 100%);
  background-size: 200% 100%;
  animation: progressShine 2s linear infinite;
}

.progress-bar-fill.progress-success {
  background: #67c23a;
}

.progress-bar-fill.progress-error {
  background: #f56c6c;
}

@keyframes progressShine {
  0% { background-position: 0% 0%; }
  100% { background-position: 200% 0%; }
}

.progress-status-compact {
  font-size: 11px;
  color: #909399;
}

.output-box-compact {
  max-height: 200px;
  padding: 12px;
  font-size: 12px;
}

@media (max-width: 768px) {
  .progress-grid {
    grid-template-columns: 1fr;
  }
}

/* 设备代码登录样式 */
.device-auth-card {
  animation: fadeIn 0.3s ease;
}

.device-code-modal .modal-content {
  max-width: 480px;
  width: 90%;
  max-height: none;
}

.device-code-content {
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.device-code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
}

.device-code-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.device-code-header .modal-close {
  background: rgba(255, 255, 255, 0.15);
  color: white;
  border: none;
  font-size: 28px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  padding: 0;
}

.device-code-header .modal-close:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: rotate(90deg);
}

.device-code-body {
  padding: 24px;
  background: white;
}

.login-instruction {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: #e8f4fd;
  border-radius: 8px;
  margin-bottom: 20px;
  align-items: flex-start;
}

.instruction-icon {
  font-size: 20px;
  flex-shrink: 0;
  line-height: 1;
}

.instruction-text {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  flex: 1;
}

.code-display-large {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  margin-bottom: 20px;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
}

.code-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 16px;
  font-weight: 500;
}

.code-value-large {
  font-size: 36px;
  font-weight: 700;
  font-family: 'Consolas', 'Monaco', monospace;
  color: white;
  letter-spacing: 6px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  word-break: break-all;
}

.open-login-section {
  text-align: center;
  margin-bottom: 16px;
}

.open-login-section .qq-btn-large {
  padding: 16px 32px;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 10px;
  border: none;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.open-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.qq-btn-success {
  background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
  color: white;
  font-weight: 600;
}

.qq-btn-success:hover {
  background: linear-gradient(135deg, #95d450 0%, #4a9625 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(168, 224, 99, 0.5);
}

.auth-waiting {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 14px;
  background: #f8f9fa;
  border-radius: 8px;
}

.waiting-spinner {
  width: 18px;
  height: 18px;
  border: 3px solid #e8e8f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.waiting-text {
  font-size: 14px;
  color: #606266;
}

.login-hint {
  font-size: 12px;
  color: #909399;
  text-align: center;
  margin-top: 8px;
}
</style>
