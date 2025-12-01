<template>
  <div class="network-page">
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
        
        <div class="node-list-compact">
          <div v-if="nodeList.length === 0" class="empty-state-small">
            <p>暂无自定义节点</p>
          </div>
          <div v-else class="node-count">
            <span class="count-badge">{{ nodeList.length }}</span>
            <span class="count-text">个自定义节点</span>
          </div>
        </div>
        
        <div class="quick-actions">
          <button @click="showNodeModal = true" class="qq-btn qq-btn-primary qq-btn-block">管理节点</button>
        </div>
      </div>
    </div>

    <!-- 网络配置和流量统计 -->
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
            <input 
              v-model="networkConfig.network_name" 
              placeholder="输入房间名称"
              class="qq-input"
            />
          </div>
          <div class="form-row">
            <label class="form-label">
              <span class="label-icon">🔒</span>
              房间密码
            </label>
            <input 
              v-model="networkConfig.network_secret" 
              type="password"
              placeholder="输入房间密码"
              class="qq-input"
            />
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
        <div v-for="peer in peers" :key="peer.ipv4 + peer.hostname" class="device-item">
          <div class="device-info">
            <img :src="getLatencyIcon(peer.latency)" class="device-icon" alt="延迟图标" />
            <div>
              <div class="device-name">{{ peer.hostname || '未知设备' }}</div>
              <div class="device-ip">{{ peer.ipv4 }}</div>
            </div>
          </div>
          <div class="device-status">
            <span class="device-latency">{{ peer.latency }}ms</span>
          </div>
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
          <div class="node-list">
            <div v-if="nodeList.length === 0" class="empty-state">
              <p>暂无自定义节点</p>
            </div>
            <div v-else>
              <div v-for="(node, index) in nodeList" :key="index" class="node-item">
                <div class="node-content">
                  <div class="node-icon">🌐</div>
                  <div class="node-address">{{ node }}</div>
                </div>
                <button @click.stop="removeNode(node)" class="qq-btn qq-btn-danger qq-btn-small">删除</button>
              </div>
            </div>
          </div>
          
          <div class="add-node-form">
            <input 
              v-model="newNodeAddress" 
              placeholder="输入节点地址，如: tcp://example.com:11010"
              class="qq-input"
              @keyup.enter="addNode"
            />
            <button @click="addNode" class="qq-btn qq-btn-primary">添加节点</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const { showToast } = useToast()

const networkStatus = ref({
  running: false,
  connected: false,
  virtual_ip: '未连接'
})

const networkConfig = ref({
  network_name: '',
  network_secret: '',
  peers: [] as string[]
})

const nodeList = ref<string[]>([])
const newNodeAddress = ref('')
const showNodeModal = ref(false)
const peers = ref<any[]>([])
const trafficStats = ref({
  tx_bytes: 0,
  rx_bytes: 0,
  tx_speed: 0,
  rx_speed: 0
})

const isConnecting = ref(false)
const isDisconnecting = ref(false)

let statusTimer: ReturnType<typeof setInterval> | null = null

async function connectNetwork() {
  if (!networkConfig.value.network_name || !networkConfig.value.network_secret) {
    showToast('请输入房间名称和密码', 'error')
    return
  }

  isConnecting.value = true
  try {
    const r = await fetch('/api/easytier/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        network_name: networkConfig.value.network_name,
        network_secret: networkConfig.value.network_secret,
        peers: nodeList.value
      })
    })

    const result = await r.json()
    if (result.ok) {
      showToast('连接成功！', 'success')
      startStatusPolling()
    } else {
      showToast(result.error || '连接失败', 'error')
    }
  } catch (e: any) {
    showToast(`连接失败: ${e.message}`, 'error')
  } finally {
    isConnecting.value = false
  }
}

async function disconnectNetwork() {
  isDisconnecting.value = true
  try {
    const r = await fetch('/api/easytier/stop', { method: 'POST' })
    const result = await r.json()
    
    if (result.ok) {
      networkStatus.value.connected = false
      networkStatus.value.virtual_ip = '未连接'
      peers.value = []
      showToast('已断开连接', 'info')
      stopStatusPolling()
    } else {
      showToast(result.error || '断开失败', 'error')
    }
  } catch (e: any) {
    showToast(`断开失败: ${e.message}`, 'error')
  } finally {
    isDisconnecting.value = false
  }
}

async function loadNodes() {
  try {
    const r = await fetch('/api/easytier/nodes')
    const result = await r.json()
    if (Array.isArray(result.nodes)) {
      nodeList.value = result.nodes
    }
  } catch (e: any) {
    console.error('加载节点失败:', e)
  }
}

async function addNode() {
  if (!newNodeAddress.value.trim()) {
    showToast('请输入节点地址', 'error')
    return
  }

  try {
    const r = await fetch('/api/easytier/nodes/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node: newNodeAddress.value.trim() })
    })

    const result = await r.json()
    if (result.ok) {
      nodeList.value.push(newNodeAddress.value.trim())
      newNodeAddress.value = ''
      showToast('节点添加成功', 'success')
    } else {
      showToast(result.error || '添加失败', 'error')
    }
  } catch (e: any) {
    showToast(`添加失败: ${e.message}`, 'error')
  }
}

async function removeNode(node: string) {
  try {
    const r = await fetch('/api/easytier/nodes/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node })
    })

    const result = await r.json()
    if (result.ok) {
      nodeList.value = nodeList.value.filter(n => n !== node)
      showToast('节点删除成功', 'success')
    } else {
      showToast(result.error || '删除失败', 'error')
    }
  } catch (e: any) {
    showToast(`删除失败: ${e.message}`, 'error')
  }
}

async function updateStatus() {
  try {
    const r = await fetch('/api/easytier/status')
    const result = await r.json()
    networkStatus.value = {
      running: result.running || false,
      connected: result.connected || false,
      virtual_ip: result.virtual_ip || '未连接'
    }

    const r2 = await fetch('/api/easytier/peers')
    const peers_result = await r2.json()
    if (Array.isArray(peers_result)) {
      peers.value = peers_result
    }

    const r3 = await fetch('/api/easytier/traffic')
    const traffic_result = await r3.json()
    trafficStats.value = {
      tx_bytes: traffic_result.tx_bytes || 0,
      rx_bytes: traffic_result.rx_bytes || 0,
      tx_speed: traffic_result.tx_speed || 0,
      rx_speed: traffic_result.rx_speed || 0
    }
  } catch (e: any) {
    console.error('更新状态失败:', e)
  }
}

function startStatusPolling() {
  if (statusTimer) return
  statusTimer = setInterval(updateStatus, 2000)
}

function stopStatusPolling() {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

function formatSpeed(speed: number): string {
  return formatBytes(speed) + '/s'
}

function getLatencyIcon(latency: number): string {
  if (latency < 0 || latency === null || latency === undefined) {
    return '/icons/drop.png'  // 断开或未知
  } else if (latency < 50) {
    return '/icons/good.png'  // 良好：< 50ms
  } else if (latency < 150) {
    return '/icons/fluid.png'  // 流畅：50-150ms
  } else {
    return '/icons/laggy.png'  // 卡顿：>= 150ms
  }
}

onMounted(() => {
  loadNodes()
  updateStatus()
  startStatusPolling()
})

onUnmounted(() => {
  stopStatusPolling()
})
</script>

<style scoped>
.network-page {
  width: 100%;
}

.panel-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.panel-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.panel-half {
  width: 100%;
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

.status-card {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 24px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 2px solid #e8e8e8;
}

.status-card.connected {
  background: linear-gradient(135deg, #d4f4dd 0%, #e8f8ec 100%);
  border-color: #52c41a;
}

.status-icon {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border-radius: 50%;
  font-size: 32px;
}

.status-info {
  flex: 1;
}

.status-label {
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 8px;
}

.status-ip {
  font-size: 14px;
  color: #606266;
}

.node-list-compact {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 16px;
}

.empty-state-small {
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.node-count {
  display: flex;
  align-items: center;
  gap: 8px;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #4a90e2;
  color: white;
  border-radius: 50%;
  font-weight: 700;
}

.quick-actions {
  margin-top: 16px;
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
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
}

.label-icon {
  font-size: 16px;
}

.button-group {
  display: flex;
  gap: 12px;
}

.traffic-stats {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
}

.traffic-item {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px;
}

.traffic-icon {
  font-size: 32px;
}

.traffic-info {
  flex: 1;
}

.traffic-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 4px;
}

.traffic-value {
  font-size: 20px;
  font-weight: 700;
  color: #2c3e50;
}

.traffic-speed {
  font-size: 13px;
  color: #606266;
}

.traffic-divider {
  width: 2px;
  height: 60px;
  background: #e8e8e8;
}

.device-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 2px solid #e8e8e8;
}

.device-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.device-icon {
  width: 64px;
  height: 64px;
  object-fit: contain;
}

.device-name {
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
}

.device-ip {
  font-size: 14px;
  color: #606266;
}

.device-latency {
  font-size: 14px;
  font-weight: 600;
  color: #52c41a;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #909399;
}

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
  z-index: 9999;
}

.modal-content {
  background: white;
  border-radius: 16px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid #e8e8e8;
}

.modal-close {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
}

.modal-body {
  padding: 24px;
}

.node-list {
  margin-bottom: 20px;
}

.node-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 8px;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.node-icon {
  font-size: 20px;
}

.node-address {
  font-size: 14px;
  color: #2c3e50;
}

.add-node-form {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.qq-input {
  flex: 1;
  padding: 12px 16px;
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
}

.qq-input:focus {
  outline: none;
  border-color: #4a90e2;
}

.qq-btn {
  border: none;
  border-radius: 6px;
  font-size: 14px;
  padding: 0 20px;
  height: 40px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
}

.qq-btn-primary {
  background: #4a90e2;
  color: white;
}

.qq-btn-primary:hover {
  background: #357abd;
}

.qq-btn-danger {
  background: #f56c6c;
  color: white;
}

.qq-btn-small {
  height: 32px;
  padding: 0 16px;
  font-size: 13px;
}

.qq-btn-block {
  width: 100%;
}

.qq-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
