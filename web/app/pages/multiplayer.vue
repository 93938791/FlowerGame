<template>
  <div class="multiplayer-container">
    <div class="multiplayer-grid">
      <!-- 左侧：版本选择和启动 -->
      <div class="multiplayer-left">
        <div class="panel-section">
          <h3 class="section-title">🎮 选择游戏版本</h3>
          
          <div v-if="loadingInstalledVersions" class="loading-hint">
            <span class="loading-icon">⏳</span>
            <span>正在加载已安装的版本...</span>
          </div>
          
          <div v-else-if="installedVersions.length === 0" class="empty-hint">
            <div class="empty-icon">📦</div>
            <div class="empty-text">还没有下载任何版本</div>
            <NuxtLink to="/game" class="qq-btn qq-btn-primary">前往下载</NuxtLink>
          </div>
          
          <div v-else class="version-grid">
            <div 
              v-for="version in installedVersions" 
              :key="version.id"
              class="version-card"
              :class="{ selected: selectedLaunchVersion === version.id }"
              @click="selectLaunchVersion(version.id)"
            >
              <div class="version-icon-img">
                <img 
                  :src="getVersionIcon(version.id)" 
                  :alt="getVersionLabel(version.id)"
                  @error="handleImageError"
                />
              </div>
              <div class="version-details">
                <div class="version-name">{{ version.id }}</div>
                <div class="version-type-tag" :class="getVersionTypeClass(version.type)">
                  {{ getVersionTypeLabel(version.type) }}
                </div>
              </div>
              <div class="version-check" v-if="selectedLaunchVersion === version.id">
                <span class="check-icon">✓</span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 启动设置 -->
        <div class="launch-settings" v-if="installedVersions.length > 0">
          <div class="settings-header">
            <h4 class="subsection-title">🚀 启动设置</h4>
            <div class="auto-calc-hint">
              <span class="hint-icon">✨</span>
              <span class="hint-text">已根据您的电脑配置自动计算参数</span>
            </div>
          </div>
          <div class="launch-form">
            <div class="launch-form-group">
              <label class="launch-label">
                <span class="label-icon">💾</span>
                <span class="label-text">最小内存 (GB)</span>
              </label>
              <input 
                v-model.number="minMemory" 
                type="number"
                min="1"
                max="32"
                placeholder="最小内存分配" 
                class="launch-input"
              />
              <div class="param-hint">游戏启动时分配的初始内存大小</div>
            </div>
            
            <div class="launch-form-group">
              <label class="launch-label">
                <span class="label-icon">💾</span>
                <span class="label-text">最大内存 (GB)</span>
              </label>
              <input 
                v-model.number="maxMemory" 
                type="number"
                min="1"
                max="32"
                placeholder="最大内存分配" 
                class="launch-input"
              />
              <div class="param-hint">游戏运行时可使用的最大内存</div>
            </div>
            
            <div class="launch-form-group">
              <label class="launch-label">
                <span class="label-icon">⚡</span>
                <span class="label-text">垃圾回收器</span>
              </label>
              <select v-model="gcType" class="launch-select">
                <option value="G1GC">G1GC (推荐)</option>
                <option value="ZGC">ZGC (低延迟)</option>
                <option value="ParallelGC">ParallelGC (高吞吐)</option>
              </select>
              <div class="param-hint">控制内存回收方式，G1GC适合大多数情况</div>
            </div>
            
            <div class="launch-form-group advanced-toggle">
              <button @click="showAdvanced = !showAdvanced" class="toggle-btn">
                <span class="toggle-icon">{{ showAdvanced ? '▼' : '▶' }}</span>
                <span>高级选项</span>
              </button>
            </div>
            
            <div v-if="showAdvanced" class="advanced-options">
              <div class="launch-form-group">
                <label class="launch-label">
                  <span class="label-icon">🔧</span>
                  <span class="label-text">额外 JVM 参数</span>
                </label>
                <textarea 
                  v-model="extraJvmArgs" 
                  placeholder="可选：输入额外的 JVM 参数" 
                  class="launch-textarea"
                  rows="2"
                ></textarea>
                <div class="param-hint">高级用户可添加自定义 JVM 参数</div>
              </div>
            </div>
            
            <button 
              @click="launchMinecraftGame" 
              class="launch-btn"
              :class="{ launching: isLaunching }"
              :disabled="isLaunching || !selectedLaunchVersion"
            >
              <span class="btn-icon">{{ isLaunching ? '⏳' : '🚀' }}</span>
              <span class="btn-text">{{ isLaunching ? '启动中...' : '启动游戏' }}</span>
            </button>
          </div>
          
          <div v-if="launchOutput" class="launch-output">
            <pre>{{ launchOutput }}</pre>
          </div>
        </div>
      </div>
      
      <!-- 右侧：联机配置 -->
      <div class="multiplayer-right">
        <!-- 登录信息 -->
        <div class="panel-section login-info-card" v-if="accountInfo || offlineAccount">
          <div class="login-info-header">
            <span class="info-icon">👤</span>
            <span class="info-title">当前账号</span>
          </div>
          <div class="login-info-content">
            <div class="account-type" v-if="accountInfo">
              <span class="type-badge genuine">✓ 正版账号</span>
            </div>
            <div class="account-type" v-else-if="offlineAccount">
              <span class="type-badge offline">⚡ 离线模式</span>
            </div>
          </div>
        </div>
        
        <div class="panel-section multiplayer-card">
          <div class="card-header">
            <h3 class="section-title">🌐 联机配置</h3>
            <div class="card-subtitle">通过虚拟网络与好友联机</div>
          </div>
          
          <div class="network-guide">
            <div class="guide-item">
              <div class="guide-icon">🎮</div>
              <div class="guide-content">
                <div class="guide-title">虚拟局域网联机</div>
                <div class="guide-text">通过 Easytier 虚拟网络，您可以与好友轻松联机</div>
              </div>
            </div>
            
            <div class="guide-item">
              <div class="guide-icon">📡</div>
              <div class="guide-content">
                <div class="guide-title">启动网络</div>
                <div class="guide-text">请先在「网络管理」中启动 Easytier 网络</div>
              </div>
            </div>
            
            <div class="guide-item">
              <div class="guide-icon">🔗</div>
              <div class="guide-content">
                <div class="guide-title">连接房间</div>
                <div class="guide-text">确保您和好友都已连接到同一虚拟网络</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const { accountInfo, offlineAccount, loadAccountFromCache, loadOfflineFromCache } = useAuth()
const { showToast } = useToast()

interface InstalledVersion {
  id: string
  type: string
  installed: boolean
  jar_exists: boolean
  json_exists: boolean
}

const installedVersions = ref<InstalledVersion[]>([])
const loadingInstalledVersions = ref(false)
const selectedLaunchVersion = ref('')
const launchUsername = ref('')
const minMemory = ref(2)
const maxMemory = ref(4)
const gcType = ref('G1GC')
const extraJvmArgs = ref('')
const showAdvanced = ref(false)
const isLaunching = ref(false)
const launchOutput = ref('')

// 根据系统内存计算推荐值
async function calculateRecommendedMemory() {
  try {
    // 从后端 API 获取系统信息
    const r = await fetch('/api/system/info')
    const result = await r.json()
    
    if (result.ok && result.memory) {
      const totalMemoryGB = result.memory.total_gb
      
      // 计算推荐值
      // 最小内存：总内存的 25%，至少 2GB
      minMemory.value = Math.max(2, Math.floor(totalMemoryGB * 0.25))
      
      // 最大内存：总内存的 50%，至少 4GB，最多不超过总内存的 75%
      maxMemory.value = Math.max(4, Math.min(
        Math.floor(totalMemoryGB * 0.5),
        Math.floor(totalMemoryGB * 0.75)
      ))
      
      console.log(`✅ 系统内存: ${totalMemoryGB.toFixed(2)}GB, 推荐配置: 最小${minMemory.value}GB, 最大${maxMemory.value}GB`)
    } else {
      // 降级：使用默认值
      minMemory.value = 2
      maxMemory.value = 4
      console.warn('无法获取系统信息，使用默认内存配置')
    }
  } catch (e: any) {
    // 降级：使用默认值
    minMemory.value = 2
    maxMemory.value = 4
    console.error('获取系统信息失败:', e)
  }
}

// 构建 JVM 参数数组
function buildJvmArgs(): string[] {
  const args: string[] = [
    `-Xms${minMemory.value}G`,
    `-Xmx${maxMemory.value}G`,
    '-XX:+UnlockExperimentalVMOptions'
  ]
  
  // 添加 GC 参数
  if (gcType.value === 'G1GC') {
    args.push(
      '-XX:+UseG1GC',
      '-XX:G1NewSizePercent=20',
      '-XX:G1ReservePercent=20',
      '-XX:MaxGCPauseMillis=50',
      '-XX:G1HeapRegionSize=32M'
    )
  } else if (gcType.value === 'ZGC') {
    args.push('-XX:+UseZGC')
  } else if (gcType.value === 'ParallelGC') {
    args.push('-XX:+UseParallelGC')
  }
  
  // 添加额外参数
  if (extraJvmArgs.value.trim()) {
    const extraArgs = extraJvmArgs.value.trim().split(/\s+/).filter(arg => arg.length > 0)
    args.push(...extraArgs)
  }
  
  return args
}

// 加载已安装版本
async function loadInstalledVersions() {
  loadingInstalledVersions.value = true
  try {
    const r = await fetch('/api/minecraft/installed-versions')
    const result = await r.json()
    if (result.ok && result.versions && Array.isArray(result.versions)) {
      installedVersions.value = result.versions.filter((v: InstalledVersion) => v.jar_exists && v.json_exists)
    }
  } catch (e: any) {
    console.error('加载已安装版本失败:', e)
    showToast(`加载失败: ${e.message}`, 'error')
  } finally {
    loadingInstalledVersions.value = false
  }
}

function selectLaunchVersion(versionId: string) {
  selectedLaunchVersion.value = versionId
}

function getVersionTypeLabel(type: string): string {
  const typeMap: Record<string, string> = {
    'release': '正式版',
    'snapshot': '快照版',
    'old_beta': 'Beta',
    'old_alpha': 'Alpha',
    'unknown': '未知'
  }
  return typeMap[type?.toLowerCase()] || '正式版'
}

function getVersionTypeClass(type: string): string {
  return type?.toLowerCase() || 'release'
}

function getVersionIcon(versionId: string): string {
  const lowerVersionId = versionId.toLowerCase()
  
  if (lowerVersionId.includes('fabric')) {
    return '/icons/fabric.png'
  } else if (lowerVersionId.includes('forge') && !lowerVersionId.includes('neoforge')) {
    return '/icons/forge.png'
  } else if (lowerVersionId.includes('neoforge')) {
    return '/icons/neoforge.png'
  } else if (lowerVersionId.includes('optifine')) {
    return '/icons/optifine.png'
  } else {
    return '/icons/vanilla.png'
  }
}

function getVersionLabel(versionId: string): string {
  const lowerVersionId = versionId.toLowerCase()
  
  if (lowerVersionId.includes('fabric')) {
    return 'Fabric'
  } else if (lowerVersionId.includes('forge') && !lowerVersionId.includes('neoforge')) {
    return 'Forge'
  } else if (lowerVersionId.includes('neoforge')) {
    return 'NeoForge'
  } else if (lowerVersionId.includes('optifine')) {
    return 'OptiFine'
  } else {
    return '原版'
  }
}

function handleImageError(event: Event) {
  const img = event.target as HTMLImageElement
  img.src = '/icons/vanilla.png'
}

async function launchMinecraftGame() {
  console.log('🚀 开始启动游戏...')
  console.log('选中的版本:', selectedLaunchVersion.value)
  
  if (!selectedLaunchVersion.value) {
    showToast('请先选择要启动的版本', 'error')
    return
  }
  
  isLaunching.value = true
  launchOutput.value = ''
  
  try {
    let username = ''
    let uuid = ''
    let accessToken = ''
    
    console.log('accountInfo:', accountInfo.value)
    console.log('offlineAccount:', offlineAccount.value)
    
    if (accountInfo.value) {
      username = accountInfo.value.name
      uuid = accountInfo.value.id
      accessToken = accountInfo.value.minecraft_token || ''
      console.log('使用正版账号:', username)
    } else if (offlineAccount.value) {
      username = offlineAccount.value
      console.log('使用离线账号:', username)
    } else {
      showToast('请先登录账号', 'error')
      isLaunching.value = false
      return
    }
    
    launchOutput.value = `正在启动 Minecraft ${selectedLaunchVersion.value}...\n`
    
    // 构建 JVM 参数
    const jvmArgsArray = buildJvmArgs()
    console.log('JVM 参数:', jvmArgsArray)
    
    const requestBody = {
      version_id: selectedLaunchVersion.value,
      username: username,
      uuid: uuid,
      access_token: accessToken,
      jvm_args: jvmArgsArray
    }
    console.log('请求参数:', requestBody)
    
    const r = await fetch('/api/minecraft/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    })
    
    console.log('响应状态:', r.status)
    const result = await r.json()
    console.log('响应结果:', result)
    
    if (result.ok) {
      launchOutput.value += `✅ 游戏启动成功！PID: ${result.pid}\n`
      showToast(`Minecraft ${selectedLaunchVersion.value} 启动成功！`, 'success')
    } else {
      launchOutput.value += `❌ 启动失败: ${result.error}\n`
      showToast(`启动失败: ${result.error}`, 'error')
    }
  } catch (e: any) {
    launchOutput.value += `❌ 启动异常: ${e.message}\n`
    showToast(`启动异常: ${e.message}`, 'error')
  } finally {
    isLaunching.value = false
  }
}

onMounted(async () => {
  // 加载已安装版本
  loadInstalledVersions()
  
  // 初始化内存推荐值
  calculateRecommendedMemory()
  
  // 加载账号信息
  await loadAccountFromCache()
  await loadOfflineFromCache()
  
  console.log('✅ 页面加载完成')
  console.log('正版账号:', accountInfo.value)
  console.log('离线账号:', offlineAccount.value)
})
</script>

<style scoped>
.multiplayer-container {
  width: 100%;
}

.multiplayer-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
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

.loading-hint,
.empty-hint {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
}

.loading-icon {
  font-size: 32px;
  display: block;
  margin-bottom: 12px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 16px;
  margin-bottom: 20px;
  color: #606266;
}

.version-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-bottom: 20px;
}

.version-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: white;
  border: 2px solid #e8e8e8;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.version-card:hover {
  border-color: #00d9ff;
  box-shadow: 0 2px 8px rgba(0, 217, 255, 0.2);
}

.version-card.selected {
  background: linear-gradient(135deg, #e8f4f8 0%, #f0f9ff 100%);
  border-color: #00d9ff;
  box-shadow: 0 4px 12px rgba(0, 217, 255, 0.3);
}

.version-icon-img {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #f5f7fa;
  padding: 6px;
}

.version-icon-img img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.version-details {
  flex: 1;
  min-width: 0;
}

.version-name {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version-type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.version-type-tag.release {
  background: #d4f4dd;
  color: #52c41a;
}

.version-type-tag.snapshot {
  background: #fff4e6;
  color: #fa8c16;
}

.version-check {
  flex-shrink: 0;
}

.check-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
  font-size: 14px;
  font-weight: 700;
}

.launch-settings {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.subsection-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.settings-header {
  margin-bottom: 16px;
}

.auto-calc-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 12px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border: 1px solid #fbbf24;
  border-radius: 6px;
}

.hint-icon {
  font-size: 16px;
}

.hint-text {
  font-size: 13px;
  color: #92400e;
  font-weight: 500;
}

.launch-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.launch-form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.launch-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
}

.launch-select,
.launch-input,
.launch-textarea {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  transition: all 0.3s ease;
  background: #fff;
}

.launch-textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.5;
}

.launch-select:focus,
.launch-input:focus,
.launch-textarea:focus {
  outline: none;
  border-color: #00d9ff;
  box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.1);
}

.param-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
}

.advanced-toggle {
  margin: 8px 0;
}

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f3f4f6;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  transition: all 0.3s ease;
}

.toggle-btn:hover {
  background: #e5e7eb;
}

.toggle-icon {
  font-size: 12px;
  transition: transform 0.3s ease;
}

.advanced-options {
  padding: 16px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-top: 12px;
}

.login-info-card {
  margin-bottom: 20px;
}

.login-info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 2px solid #00d9ff;
}

.info-icon {
  font-size: 20px;
}

.info-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.login-info-content {
  padding: 12px 0;
}

.account-type {
  display: flex;
  align-items: center;
}

.type-badge {
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.type-badge.genuine {
  background: linear-gradient(135deg, #d4f4dd 0%, #a8e6cf 100%);
  color: #27ae60;
}

.type-badge.offline {
  background: linear-gradient(135deg, #fff4e6 0%, #ffe4b3 100%);
  color: #f39c12;
}

.launch-btn {
  width: 100%;
  padding: 16px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
  color: white;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  box-shadow: 0 4px 12px rgba(168, 224, 99, 0.3);
}

.launch-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #95d450 0%, #4a9625 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(168, 224, 99, 0.4);
}

.launch-btn:disabled {
  background: linear-gradient(135deg, #d9d9d9 0%, #bfbfbf 100%);
  cursor: not-allowed;
  box-shadow: none;
}

.launch-output {
  margin-top: 16px;
  padding: 16px;
  background: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.launch-output pre {
  margin: 0;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.network-guide {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.guide-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.guide-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.guide-content {
  flex: 1;
}

.guide-title {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
}

.guide-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.qq-btn {
  border: none;
  border-radius: 6px;
  font-size: 14px;
  padding: 10px 24px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
  text-decoration: none;
  display: inline-block;
}

.qq-btn-primary {
  background: #4a90e2;
  color: white;
}

.qq-btn-primary:hover {
  background: #357abd;
}
</style>
