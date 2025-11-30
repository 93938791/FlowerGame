<template>
  <ClientOnly>
    <div class="qq-layout">
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
            <div class="panel-section">
              <h3 class="section-title">Easytier 虚拟网络</h3>
              <div class="button-group">
                <button @click="etStart" class="qq-btn qq-btn-primary">启动网络</button>
                <button @click="etStop" class="qq-btn qq-btn-danger">停止网络</button>
                <button @click="etPeers" class="qq-btn">发现设备</button>
                <button @click="etTraffic" class="qq-btn">流量统计</button>
              </div>
              <div v-if="etOut" class="output-box">
                <pre>{{ etOut }}</pre>
              </div>
            </div>
          </div>

          <!-- 游戏管理 -->
          <div v-show="activeMenu === 'game'" class="panel">
            <!-- 账号登录区域 -->
            <div class="panel-section">
              <h3 class="section-title">🎮 账号登录</h3>
              <div class="login-tabs">
                <button 
                  :class="['tab-btn', { active: loginType === 'microsoft' }]"
                  @click="loginType = 'microsoft'"
                >
                  🔐 正版登录
                </button>
                <button 
                  :class="['tab-btn', { active: loginType === 'offline' }]"
                  @click="loginType = 'offline'"
                >
                  👤 离线登录
                </button>
              </div>
              
              <!-- 正版登录 -->
              <div v-if="loginType === 'microsoft'" class="login-content">
                <div class="account-status" v-if="accountInfo">
                  <div class="account-avatar">
                    <img :src="`https://crafatar.com/avatars/${accountInfo.id}?size=64`" alt="头像" />
                  </div>
                  <div class="account-details">
                    <div class="account-name">{{ accountInfo.name }}</div>
                    <div class="account-type">正版账号</div>
                  </div>
                  <button @click="logout" class="qq-btn qq-btn-danger">退出登录</button>
                </div>
                <div v-else>
                  <div class="button-group">
                    <button @click="authorize" class="qq-btn qq-btn-primary">🔗 获取授权链接</button>
                    <button @click="authStatus" class="qq-btn">📊 查看状态</button>
                  </div>
                  <div class="input-group" style="margin-top: 12px;">
                    <input 
                      v-model="authCode" 
                      placeholder="粘贴从浏览器复制的授权代码" 
                      class="qq-input"
                      @keyup.enter="authenticate"
                    />
                    <button @click="authenticate" class="qq-btn qq-btn-success">✓ 提交认证</button>
                  </div>
                  <div class="auth-hint">
                    💡 点击"获取授权链接"后，在打开的页面登录并复制跳转后的URL中的code参数
                  </div>
                </div>
                <div v-if="authOut" class="output-box" style="margin-top: 12px;">
                  <pre>{{ authOut }}</pre>
                </div>
              </div>
              
              <!-- 离线登录 -->
              <div v-if="loginType === 'offline'" class="login-content">
                <div class="account-status" v-if="offlineAccount">
                  <div class="account-avatar">
                    <div class="offline-avatar">{{ offlineAccount.charAt(0).toUpperCase() }}</div>
                  </div>
                  <div class="account-details">
                    <div class="account-name">{{ offlineAccount }}</div>
                    <div class="account-type">离线账号</div>
                  </div>
                  <button @click="logoutOffline" class="qq-btn qq-btn-danger">退出登录</button>
                </div>
                <div v-else>
                  <div class="input-group">
                    <input 
                      v-model="offlineName" 
                      placeholder="输入游戏名称（3-16个字符）" 
                      class="qq-input"
                      maxlength="16"
                      @keyup.enter="loginOffline"
                    />
                    <button @click="loginOffline" class="qq-btn qq-btn-primary">✓ 离线登录</button>
                  </div>
                  <div class="auth-hint">
                    💡 离线模式仅用于单人游戏或局域网联机，无需正版验证
                  </div>
                </div>
              </div>
            </div>

            <!-- MC版本下载区域 -->
            <div class="panel-section">
              <h3 class="section-title">📦 Minecraft 下载</h3>
              
              <!-- 版本选择区 -->
              <div class="download-config">
                <div class="config-row">
                  <label class="config-label">版本类型:</label>
                  <div class="button-group">
                    <button 
                      v-for="type in versionTypes" 
                      :key="type.value"
                      :class="['qq-btn', 'qq-btn-sm', { 'qq-btn-primary': selectedVersionType === type.value }]"
                      @click="selectVersionType(type.value)"
                    >
                      {{ type.label }}
                    </button>
                  </div>
                </div>
                
                <div class="config-row">
                  <label class="config-label">MC版本:</label>
                  <div class="version-selector">
                    <select v-model="versionId" class="qq-select" @change="onVersionChange">
                      <option value="">-- 请选择版本 --</option>
                      <option v-for="ver in filteredVersions" :key="ver.id" :value="ver.id">
                        {{ ver.id }} ({{ ver.type }})
                      </option>
                    </select>
                    <button @click="loadVersions" class="qq-btn" :disabled="loadingVersions">
                      {{ loadingVersions ? '加载中...' : '🔄 刷新版本' }}
                    </button>
                  </div>
                </div>
                
                <!-- 加载器选择 -->
                <div class="config-row" v-if="selectedVersionType !== 'vanilla'">
                  <label class="config-label">加载器:</label>
                  <div class="loader-selector">
                    <select v-model="loaderType" class="qq-select" @change="onLoaderChange">
                      <option value="fabric">Fabric</option>
                      <option value="forge">Forge</option>
                      <option value="neoforge">NeoForge</option>
                      <option value="optifine">OptiFine</option>
                    </select>
                    <select v-model="loaderVersion" class="qq-select">
                      <option value="">-- 选择加载器版本 --</option>
                      <option v-for="lv in loaderVersions" :key="lv" :value="lv">
                        {{ lv }}
                      </option>
                    </select>
                  </div>
                </div>
                
                <div class="config-row">
                  <label class="config-label">自定义名称:</label>
                  <input 
                    v-model="customName" 
                    placeholder="留空则使用版本号" 
                    class="qq-input"
                  />
                </div>
              </div>
              
              <!-- 下载按钮 -->
              <div class="download-actions">
                <button 
                  @click="startDownload" 
                  class="qq-btn qq-btn-primary qq-btn-large"
                  :disabled="!canDownload || isDownloading"
                >
                  {{ isDownloading ? '⏳ 下载中...' : '⬇️ 开始下载' }}
                </button>
                <button 
                  v-if="isDownloading"
                  @click="cancelDownload" 
                  class="qq-btn qq-btn-danger qq-btn-large"
                >
                  ❌ 取消下载
                </button>
              </div>
              
              <!-- 下载进度区 -->
              <div v-if="downloadTasks.length > 0" class="download-progress-area">
                <h4 class="progress-title">下载进度</h4>
                <div class="progress-list">
                  <div 
                    v-for="task in downloadTasks" 
                    :key="task.id"
                    class="progress-item"
                  >
                    <div class="progress-header">
                      <span class="progress-name">{{ task.name }}</span>
                      <span class="progress-percentage">{{ task.progress }}%</span>
                    </div>
                    <div class="progress-bar">
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
                    <div class="progress-status">{{ task.statusText }}</div>
                  </div>
                </div>
              </div>
              
              <!-- 下载日志 -->
              <div v-if="dlOut" class="output-box" style="margin-top: 16px;">
                <pre>{{ dlOut }}</pre>
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
import { ref, computed, onMounted } from 'vue'

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

// 版本下载相关
const versionTypes = [
  { label: '🎯 原版', value: 'vanilla' },
  { label: '📦 Fabric', value: 'fabric' },
  { label: '🔧 Forge', value: 'forge' },
  { label: '🌟 NeoForge', value: 'neoforge' },
  { label: '👍 OptiFine', value: 'optifine' }
]
const selectedVersionType = ref('vanilla')
const loaderType = ref('fabric')
const loaderVersion = ref('')
const loaderVersions = ref<string[]>([])
const mcVersions = ref<any[]>([])
const filteredVersions = computed(() => {
  return mcVersions.value
})
const loadingVersions = ref(false)
const isDownloading = ref(false)
const downloadTasks = ref<any[]>([])
const canDownload = computed(() => {
  if (selectedVersionType.value === 'vanilla') {
    return versionId.value.length > 0
  }
  return versionId.value.length > 0 && loaderVersion.value.length > 0
})

// 登录相关方法
async function authorize() {
  const r = await fetch('/api/auth/authorize-url')
  const j = await r.json()
  authOut.value = JSON.stringify(j, null, 2)
  if (j.url) window.open(j.url, '_blank')
}

async function authenticate() {
  const r = await fetch('/api/auth/authenticate', { 
    method: 'POST', 
    headers: { 'Content-Type': 'application/json' }, 
    body: JSON.stringify({ auth_code: authCode.value.trim() }) 
  })
  const result = await r.json()
  authOut.value = JSON.stringify(result, null, 2)
  
  // 如果认证成功，保存账户信息
  if (result.ok && result.profile) {
    accountInfo.value = result.profile
  }
}

async function authStatus() {
  const r = await fetch('/api/auth/status')
  const result = await r.json()
  authOut.value = JSON.stringify(result, null, 2)
  
  // 更新账户信息
  if (result.profile) {
    accountInfo.value = result.profile
  }
}

function logout() {
  accountInfo.value = null
  authOut.value = ''
  authCode.value = ''
}

function loginOffline() {
  if (offlineName.value.length < 3 || offlineName.value.length > 16) {
    alert('游戏名称长度必须在3-16个字符之间')
    return
  }
  offlineAccount.value = offlineName.value
  offlineName.value = ''
}

function logoutOffline() {
  offlineAccount.value = null
}

// 版本管理方法
async function loadVersions() {
  loadingVersions.value = true
  try {
    const r = await fetch('/api/minecraft/versions')
    mcVersions.value = await r.json()
    dlOut.value = `已加载 ${mcVersions.value.length} 个版本`
  } catch (e: any) {
    dlOut.value = `加载失败: ${e.message}`
  } finally {
    loadingVersions.value = false
  }
}

function selectVersionType(type: string) {
  selectedVersionType.value = type
  loaderVersion.value = ''
  loaderVersions.value = []
  if (type !== 'vanilla') {
    loaderType.value = type === 'fabric' ? 'fabric' : type === 'forge' ? 'forge' : type === 'neoforge' ? 'neoforge' : 'optifine'
  }
}

function onVersionChange() {
  // 版本改变时，更新加载器版本列表
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
  // 模拟加载器版本列表（实际应调用API）
  loaderVersions.value = ['0.15.11', '0.15.10', '0.15.9', '0.15.7']
}

async function startDownload() {
  isDownloading.value = true
  dlOut.value = ''
  
  // 初始化下载任务
  downloadTasks.value = [
    { id: 'version_info', name: '📄 版本信息', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'client_jar', name: '🎮 客户端 JAR', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'libraries', name: '📦 依赖库', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'assets', name: '🎨 资源文件', progress: 0, status: 'pending', statusText: '等待中...' }
  ]
  
  try {
    if (selectedVersionType.value === 'vanilla') {
      // 下载原版
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
      
      // 模拟进度更新
      await simulateProgress()
    } else {
      // 下载带加载器的版本
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
      
      // 模拟进度更新
      await simulateProgress()
    }
  } catch (e: any) {
    dlOut.value = `下载失败: ${e.message}`
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
  // 模拟进度更新（实际应通过WebSocket或轮询获取）
  for (const task of downloadTasks.value) {
    task.status = 'downloading'
    task.statusText = '下载中...'
    
    for (let i = 0; i <= 100; i += 10) {
      await new Promise(resolve => setTimeout(resolve, 200))
      task.progress = i
      if (i === 100) {
        task.status = 'completed'
        task.statusText = '✓ 完成'
      }
    }
  }
}

function cancelDownload() {
  isDownloading.value = false
  downloadTasks.value.forEach(task => {
    if (task.status === 'downloading') {
      task.status = 'failed'
      task.statusText = '已取消'
    }
  })
  dlOut.value = '下载已取消'
}

async function listVersions() {
  await loadVersions()
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

<style scoped>
.qq-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background: #f5f5f5;
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

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.panel-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.3s ease;
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
  transition: border-color 0.3s ease;
  outline: none;
}

.qq-input:focus {
  border-color: #4a90e2;
}

.qq-input::placeholder {
  color: #c0c4cc;
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

/* 登录相关样式 */
.login-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.tab-btn {
  flex: 1;
  padding: 12px 24px;
  border: 2px solid #dcdfe6;
  background: white;
  color: #606266;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 15px;
  font-weight: 500;
}

.tab-btn:hover {
  border-color: #4a90e2;
  color: #4a90e2;
}

.tab-btn.active {
  border-color: #4a90e2;
  background: #4a90e2;
  color: white;
}

.login-content {
  animation: fadeIn 0.3s ease;
}

.account-status {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.account-avatar img {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 3px solid white;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.offline-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: bold;
  color: white;
  border: 3px solid white;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.account-details {
  flex: 1;
}

.account-name {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.account-type {
  font-size: 14px;
  opacity: 0.9;
}

.auth-hint {
  margin-top: 12px;
  padding: 12px;
  background: #f0f9ff;
  border-left: 4px solid #4a90e2;
  border-radius: 4px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}

/* 下载配置样式 */
.download-config {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.config-row:last-child {
  margin-bottom: 0;
}

.config-label {
  min-width: 100px;
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.version-selector,
.loader-selector {
  display: flex;
  gap: 8px;
  flex: 1;
}

.qq-select {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  background: white;
  cursor: pointer;
  transition: border-color 0.3s ease;
  outline: none;
}

.qq-select:hover {
  border-color: #c0c4cc;
}

.qq-select:focus {
  border-color: #4a90e2;
}

.qq-btn-sm {
  height: 32px;
  padding: 0 16px;
  font-size: 13px;
}

.qq-btn-large {
  height: 48px;
  padding: 0 32px;
  font-size: 16px;
  font-weight: 600;
}

.download-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

/* 进度条样式 */
.download-progress-area {
  margin-top: 24px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.progress-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

.progress-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.progress-item {
  background: white;
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-name {
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.progress-percentage {
  font-weight: 600;
  color: #4a90e2;
  font-size: 14px;
}

.progress-bar {
  height: 8px;
  background: #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-bar-fill {
  height: 100%;
  background: #4a90e2;
  border-radius: 4px;
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

.progress-status {
  font-size: 13px;
  color: #909399;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .config-row {
    flex-direction: column;
    align-items: stretch;
  }
  
  .config-label {
    min-width: auto;
  }
  
  .version-selector,
  .loader-selector {
    flex-direction: column;
  }
  
  .download-actions {
    flex-direction: column;
  }
}
</style>
