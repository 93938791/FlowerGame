<template>
  <ClientOnly>
    <div class="qq-layout">
      <!-- 消息提示 -->
      <div v-if="toast.show" class="toast" :class="toast.type">
        <span class="toast-icon">{{ toast.type === 'success' ? '✓' : toast.type === 'error' ? '✗' : 'ℹ' }}</span>
        <span class="toast-message">{{ toast.message }}</span>
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
        
        <div class="sidebar-footer">
          <div class="status-indicator">
            <span class="status-dot online"></span>
            <span class="status-text">在线</span>
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
                    <button @click="connectNetwork" class="qq-btn qq-btn-primary" :disabled="networkStatus.connected">
                      {{ networkStatus.connected ? '已连接' : '连接房间' }}
                    </button>
                    <button @click="disconnectNetwork" class="qq-btn qq-btn-danger" :disabled="!networkStatus.connected">
                      断开连接
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
            <div class="panel-section">
              <h3 class="section-title">Minecraft 版本下载</h3>
              <div class="button-group">
                <button @click="listVersions" class="qq-btn">获取版本清单</button>
              </div>
              <div class="input-group">
                <input 
                  v-model="versionId" 
                  placeholder="输入版本号，如 1.21.1" 
                  class="qq-input"
                />
                <input 
                  v-model="customName" 
                  placeholder="自定义名称（可选）" 
                  class="qq-input"
                />
                <button @click="downloadVersion" class="qq-btn qq-btn-primary">下载原版</button>
              </div>
              <div v-if="dlOut" class="output-box">
                <pre>{{ dlOut }}</pre>
              </div>
            </div>
            
            <div class="panel-section">
              <h3 class="section-title">Microsoft 账户登录</h3>
              <div class="button-group">
                <button @click="authorize" class="qq-btn qq-btn-primary">获取授权</button>
                <button @click="authStatus" class="qq-btn">查看状态</button>
              </div>
              <div class="input-group">
                <input 
                  v-model="authCode" 
                  placeholder="粘贴授权 code" 
                  class="qq-input"
                />
                <button @click="authenticate" class="qq-btn qq-btn-success">提交认证</button>
              </div>
              <div v-if="authOut" class="output-box">
                <pre>{{ authOut }}</pre>
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
    ws.close()
    ws = null
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
  try {
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
  }
}

// 断开连接
async function disconnectNetwork() {
  try {
    const r = await fetch('/api/easytier/stop', { method: 'POST' })
    const result = await r.json()
    
    if (result.ok) {
      showToast('已断开连接', 'success')
      // 断开 WebSocket
      disconnectWebSocket()
      await updateNetworkStatus()
      peers.value = []
      trafficStats.value = {
        tx_bytes: 0,
        rx_bytes: 0,
        tx_speed: 0,
        rx_speed: 0
      }
    }
  } catch (e) {
    showToast(`断开失败: ${e}`, 'error')
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

async function authorize() {
  const r = await fetch('/api/auth/authorize-url')
  const j = await r.json()
  authOut.value = JSON.stringify(j, null, 2)
  if (j.url) window.open(j.url, '_blank')
}
async function authenticate() {
  const r = await fetch('/api/auth/authenticate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auth_code: authCode.value.trim() }) })
  authOut.value = JSON.stringify(await r.json(), null, 2)
}
async function authStatus() {
  const r = await fetch('/api/auth/status')
  authOut.value = JSON.stringify(await r.json(), null, 2)
}
async function listVersions() {
  const r = await fetch('/api/minecraft/versions')
  dlOut.value = JSON.stringify(await r.json(), null, 2)
}
async function downloadVersion() {
  const r = await fetch('/api/minecraft/download', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId.value.trim(), custom_name: customName.value.trim() || null }) })
  dlOut.value = JSON.stringify(await r.json(), null, 2)
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
  background: #52c41a;
  color: white;
}

.toast.error {
  background: #ff4d4f;
  color: white;
}

.toast.info {
  background: #1890ff;
  color: white;
}

.toast-icon {
  font-size: 16px;
  font-weight: bold;
}

.toast-message {
  flex: 1;
}

/* 侧边栏样式 */
.sidebar {
  width: 240px;
  background: linear-gradient(180deg, #4a90e2 0%, #357abd 100%);
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
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
  background: white;
  border-radius: 0 2px 2px 0;
}

.menu-icon {
  font-size: 20px;
}

.menu-text {
  font-size: 15px;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: white;
  font-size: 14px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #4caf50;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
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
  border-bottom: 2px solid #4a90e2;
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
  background: #4a90e2;
  color: white;
  border-color: #4a90e2;
}

.qq-btn-primary:hover {
  background: #357abd;
  border-color: #357abd;
}

.qq-btn-danger {
  background: #f56c6c;
  color: white;
  border-color: #f56c6c;
}

.qq-btn-danger:hover {
  background: #f34d4d;
  border-color: #f34d4d;
}

.qq-btn-success {
  background: #67c23a;
  color: white;
  border-color: #67c23a;
}

.qq-btn-success:hover {
  background: #5daf34;
  border-color: #5daf34;
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
  border-color: #4a90e2;
  box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1);
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
  border-color: #4a90e2;
  box-shadow: 0 0 0 4px rgba(74, 144, 226, 0.12);
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
  border-color: #4a90e2;
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
  background: linear-gradient(135deg, #e8f5e9 0%, #f1f8e9 100%);
  border-color: #4caf50;
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
  background: #4caf50;
  color: white;
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
</style>
