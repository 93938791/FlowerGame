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
</style>
