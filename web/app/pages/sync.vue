<template>
  <div class="sync-page">
    <div class="panel-section">
      <h3 class="section-title">☁️ Syncthing 存档同步</h3>
      
      <div class="sync-info-card">
        <div class="info-icon">ℹ️</div>
        <div class="info-content">
          <div class="info-title">关于存档同步</div>
          <div class="info-text">
            Syncthing 可以自动同步您的 Minecraft 存档到多台设备，
            确保您的游戏进度在不同电脑间保持一致。
          </div>
        </div>
      </div>

      <div class="sync-controls">
        <div class="button-group">
          <button @click="startSync" class="qq-btn qq-btn-primary" :disabled="syncRunning">
            {{ syncRunning ? '✓ 同步运行中' : '启动同步' }}
          </button>
          <button @click="stopSync" class="qq-btn qq-btn-danger" :disabled="!syncRunning">
            停止同步
          </button>
          <button @click="getSyncInfo" class="qq-btn">
            设备信息
          </button>
        </div>
      </div>

      <div v-if="syncOutput" class="output-box">
        <pre>{{ syncOutput }}</pre>
      </div>
    </div>

    <!-- 同步状态 -->
    <div class="panel-section" v-if="syncRunning">
      <h3 class="section-title">同步状态</h3>
      
      <div class="status-grid">
        <div class="status-card">
          <div class="status-icon">🔗</div>
          <div class="status-info">
            <div class="status-label">连接状态</div>
            <div class="status-value">{{ syncRunning ? '已连接' : '未连接' }}</div>
          </div>
        </div>
        
        <div class="status-card">
          <div class="status-icon">📁</div>
          <div class="status-info">
            <div class="status-label">同步文件夹</div>
            <div class="status-value">{{ syncFolders }}</div>
          </div>
        </div>
        
        <div class="status-card">
          <div class="status-icon">💻</div>
          <div class="status-info">
            <div class="status-label">已连接设备</div>
            <div class="status-value">{{ connectedDevices }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 使用说明 -->
    <div class="panel-section">
      <h3 class="section-title">📖 使用说明</h3>
      
      <div class="guide-steps">
        <div class="guide-step">
          <div class="step-number">1</div>
          <div class="step-content">
            <div class="step-title">启动同步服务</div>
            <div class="step-text">点击"启动同步"按钮，启动 Syncthing 服务</div>
          </div>
        </div>
        
        <div class="guide-step">
          <div class="step-number">2</div>
          <div class="step-content">
            <div class="step-title">获取设备信息</div>
            <div class="step-text">点击"设备信息"查看您的设备ID，与其他设备配对</div>
          </div>
        </div>
        
        <div class="guide-step">
          <div class="step-number">3</div>
          <div class="step-content">
            <div class="step-title">添加设备</div>
            <div class="step-text">在其他设备上添加您的设备ID，建立连接</div>
          </div>
        </div>
        
        <div class="guide-step">
          <div class="step-number">4</div>
          <div class="step-content">
            <div class="step-title">自动同步</div>
            <div class="step-text">存档将自动在所有设备间同步，无需手动操作</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const { showToast } = useToast()

const syncRunning = ref(false)
const syncOutput = ref('')
const syncFolders = ref(0)
const connectedDevices = ref(0)

async function startSync() {
  try {
    const r = await fetch('/api/syncthing/start', { method: 'POST' })
    const result = await r.json()
    
    if (result.ok) {
      syncRunning.value = true
      syncOutput.value = JSON.stringify(result, null, 2)
      showToast('同步服务已启动', 'success')
      updateSyncStatus()
    } else {
      syncOutput.value = JSON.stringify(result, null, 2)
      showToast(result.error || '启动失败', 'error')
    }
  } catch (e: any) {
    showToast(`启动失败: ${e.message}`, 'error')
  }
}

async function stopSync() {
  try {
    const r = await fetch('/api/syncthing/stop', { method: 'POST' })
    const result = await r.json()
    
    if (result.ok) {
      syncRunning.value = false
      syncOutput.value = JSON.stringify(result, null, 2)
      showToast('同步服务已停止', 'info')
    } else {
      syncOutput.value = JSON.stringify(result, null, 2)
      showToast(result.error || '停止失败', 'error')
    }
  } catch (e: any) {
    showToast(`停止失败: ${e.message}`, 'error')
  }
}

async function getSyncInfo() {
  try {
    const r1 = await fetch('/api/syncthing/device-id')
    const id = await r1.json()
    const r2 = await fetch('/api/syncthing/traffic')
    const traf = await r2.json()
    syncOutput.value = JSON.stringify({ id, traf }, null, 2)
  } catch (e: any) {
    showToast(`获取信息失败: ${e.message}`, 'error')
  }
}

async function updateSyncStatus() {
  // 这里可以定期更新同步状态
  syncFolders.value = 1
  connectedDevices.value = 0
}
</script>

<style scoped>
.sync-page {
  width: 100%;
}

.panel-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 2px solid #4a90e2;
}

.sync-info-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, #e8f4f8 0%, #f0f9ff 100%);
  border-radius: 12px;
  margin-bottom: 24px;
  border: 2px solid #00d9ff;
}

.info-icon {
  font-size: 32px;
  flex-shrink: 0;
}

.info-content {
  flex: 1;
}

.info-title {
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 8px;
}

.info-text {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.sync-controls {
  margin-bottom: 20px;
}

.button-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
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

.qq-btn-primary:hover:not(:disabled) {
  background: #357abd;
}

.qq-btn-danger {
  background: #f56c6c;
  color: white;
}

.qq-btn-danger:hover:not(:disabled) {
  background: #f34d4d;
}

.qq-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.output-box {
  background: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
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

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.status-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 2px solid #e8e8e8;
}

.status-icon {
  font-size: 32px;
  flex-shrink: 0;
}

.status-info {
  flex: 1;
}

.status-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 4px;
}

.status-value {
  font-size: 18px;
  font-weight: 700;
  color: #2c3e50;
}

.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.guide-step {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
  border-left: 4px solid #4a90e2;
}

.step-number {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #4a90e2 0%, #357abd 100%);
  color: white;
  border-radius: 50%;
  font-size: 18px;
  font-weight: 700;
}

.step-content {
  flex: 1;
}

.step-title {
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
}

.step-text {
  font-size: 14px;
  color: #606266;
  line-height: 1.5;
}
</style>
