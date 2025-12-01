<template>
  <div class="game-page">
    <div class="panel-section">
      <h3 class="section-title">🎮 Minecraft 下载</h3>
      
      <div class="download-form">
        <!-- 版本类型选择 -->
        <div class="form-group">
          <label class="form-label">版本类型</label>
          <div class="version-type-grid">
            <button
              v-for="type in versionTypes"
              :key="type.value"
              :class="['type-btn', { active: selectedVersionType === type.value }]"
              @click="selectVersionType(type.value)"
            >
              <img :src="type.icon" :alt="type.label" class="type-icon" />
              <span class="type-label">{{ type.label }}</span>
            </button>
          </div>
        </div>
        
        <!-- MC版本选择 -->
        <div class="form-group">
          <label class="form-label">Minecraft 版本</label>
          <div class="version-filter-group">
            <div class="version-type-filter">
              <button
                v-for="vtype in versionTypeFilters"
                :key="vtype.value"
                :class="['filter-btn', { active: selectedVersionFilter === vtype.value }]"
                @click="selectVersionFilter(vtype.value)"
              >
                {{ vtype.label }}
              </button>
            </div>
          </div>
          <div class="version-selector">
            <select v-model="versionId" class="qq-select" @change="onVersionChange">
              <option value="">请选择版本</option>
              <option v-for="ver in mcVersions" :key="ver.id" :value="ver.id">
                {{ ver.id }} ({{ getVersionTypeLabel(ver.type) }})
              </option>
            </select>
            <button @click="loadVersions" class="qq-btn" :disabled="loadingVersions">
              {{ loadingVersions ? '加载中...' : '刷新' }}
            </button>
          </div>
        </div>
        
        <!-- 加载器版本选择 -->
        <div class="form-group" v-if="selectedVersionType !== 'vanilla'">
          <label class="form-label">加载器版本</label>
          <select v-model="loaderVersion" class="qq-select">
            <option value="">请选择加载器版本</option>
            <option v-for="lv in loaderVersions" :key="lv" :value="lv">
              {{ lv }}
            </option>
          </select>
        </div>
        
        <!-- 自定义名称 -->
        <div class="form-group">
          <label class="form-label">自定义名称 <span class="required-mark">*</span></label>
          <input 
            v-model="customName" 
            placeholder="请输入版本名称（必填）" 
            class="qq-input"
            @input="checkVersionNameConflict"
          />
          <div v-if="versionNameConflict" class="error-hint">
            ⚠️ 该名称已存在，请使用其他名称
          </div>
          <div v-if="customName && !versionNameConflict" class="success-hint">
            ✓ 名称可用
          </div>
        </div>
        
        <!-- 下载按钮 -->
        <div class="form-actions">
          <button 
            @click="startDownload" 
            class="qq-btn qq-btn-download qq-btn-large qq-btn-block"
            :disabled="!canDownload || isDownloading"
          >
            <span class="btn-icon">{{ isDownloading ? '⏳' : '⬇️' }}</span>
            {{ isDownloading ? '下载中...' : '开始下载' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 下载进度区 -->
    <div v-if="downloadTasks.length > 0" class="panel-section">
      <h4 class="section-title">下载进度</h4>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const router = useRouter()
const { showToast } = useToast()

const versionTypes = [
  { label: '原版', value: 'vanilla', icon: '/icons/vanilla.png' },
  { label: 'Fabric', value: 'fabric', icon: '/icons/fabric.png' },
  { label: 'Forge', value: 'forge', icon: '/icons/forge.png' },
  { label: 'NeoForge', value: 'neoforge', icon: '/icons/neoforge.png' },
  { label: 'OptiFine', value: 'optifine', icon: '/icons/optifine.png' }
]

const versionTypeFilters = [
  { label: '所有版本', value: '' },
  { label: '正式版', value: 'release' },
  { label: '快照版', value: 'snapshot' }
]

const selectedVersionType = ref('vanilla')
const selectedVersionFilter = ref<string | null>('release')
const versionId = ref('')
const loaderVersion = ref('')
const loaderVersions = ref<string[]>([])
const customName = ref('')
const versionNameConflict = ref(false)
const installedVersions = ref<string[]>([])
const mcVersions = ref<any[]>([])
const loadingVersions = ref(false)
const isDownloading = ref(false)
const downloadTasks = ref<any[]>([])

const canDownload = computed(() => {
  // 检查是否有版本名称
  if (!customName.value || customName.value.trim() === '') {
    return false
  }
  // 检查是否有重名
  if (versionNameConflict.value) {
    return false
  }
  // 原版只需要选择版本
  if (selectedVersionType.value === 'vanilla') {
    return versionId.value.length > 0
  }
  // 加载器版本需要选择MC版本和加载器版本
  return versionId.value.length > 0 && loaderVersion.value.length > 0
})

function checkVersionNameConflict() {
  const name = customName.value.trim()
  if (!name) {
    versionNameConflict.value = false
    return
  }
  // 检查是否与已安装版本重名
  versionNameConflict.value = installedVersions.value.includes(name)
}

async function loadInstalledVersions() {
  try {
    const r = await fetch('/api/minecraft/installed-versions')
    const result = await r.json()
    if (result.ok && Array.isArray(result.versions)) {
      installedVersions.value = result.versions.map((v: any) => v.id)
    }
  } catch (e: any) {
    console.error('加载已安装版本失败:', e)
  }
}

function selectVersionType(type: string) {
  selectedVersionType.value = type
  loaderVersion.value = ''
  loaderVersions.value = []
  if (type !== 'vanilla' && versionId.value) {
    loadLoaderVersions()
  }
}

function selectVersionFilter(filter: string | null) {
  selectedVersionFilter.value = filter
  loadVersions()
}

function getVersionTypeLabel(type: string): string {
  const typeMap: Record<string, string> = {
    'release': '正式版',
    'snapshot': '快照版',
    'old_beta': 'Beta',
    'old_alpha': 'Alpha'
  }
  return typeMap[type?.toLowerCase()] || '正式版'
}

function onVersionChange() {
  if (selectedVersionType.value !== 'vanilla' && versionId.value) {
    loadLoaderVersions()
  }
}

async function loadVersions() {
  loadingVersions.value = true
  try {
    const versionType = selectedVersionFilter.value || ''
    const url = versionType ? `/api/minecraft/versions?version_type=${versionType}` : '/api/minecraft/versions'
    const r = await fetch(url)
    const result = await r.json()
    if (result.ok && Array.isArray(result.versions)) {
      mcVersions.value = result.versions
    } else if (result.error) {
      showToast(`加载失败: ${result.error}`, 'error')
    }
  } catch (e: any) {
    showToast(`加载失败: ${e.message}`, 'error')
  } finally {
    loadingVersions.value = false
  }
}

async function loadLoaderVersions() {
  if (!versionId.value || selectedVersionType.value === 'vanilla') {
    return
  }
  
  try {
    const r = await fetch(`/api/minecraft/loader-versions?loader_type=${selectedVersionType.value}&mc_version=${versionId.value}`)
    const result = await r.json()
    if (result.ok && Array.isArray(result.versions)) {
      loaderVersions.value = result.versions
    } else {
      showToast('获取加载器版本失败', 'error')
      // 降级：使用默认版本列表
      loaderVersions.value = ['0.15.11', '0.15.10', '0.15.9', '0.15.7']
    }
  } catch (e: any) {
    showToast(`加载失败: ${e.message}`, 'error')
    // 降级：使用默认版本列表
    loaderVersions.value = ['0.15.11', '0.15.10', '0.15.9', '0.15.7']
  }
}

async function startDownload() {
  if (!canDownload.value) {
    if (!customName.value || customName.value.trim() === '') {
      showToast('请输入版本名称', 'error')
    } else if (versionNameConflict.value) {
      showToast('该名称已存在，请使用其他名称', 'error')
    } else {
      showToast('请选择要下载的版本', 'error')
    }
    return
  }
  
  isDownloading.value = true
  
  downloadTasks.value = [
    { id: 'version_info', name: '📄 版本信息', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'client_jar', name: '🎮 JAR', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'libraries', name: '📦 依赖库', progress: 0, status: 'pending', statusText: '等待中...' },
    { id: 'assets', name: '🎨 资源', progress: 0, status: 'pending', statusText: '等待中...' }
  ]
  
  let taskId = ''
  
  try {
    if (selectedVersionType.value === 'vanilla') {
      const r = await fetch('/api/minecraft/download', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          version_id: versionId.value.trim(), 
          custom_name: customName.value.trim()
        }) 
      })
      const result = await r.json()
      
      if (!result.ok) {
        throw new Error(result.error || '下载请求失败')
      }
      
      // 使用自定义名称作为 task_id
      taskId = customName.value.trim()
    } else {
      const r = await fetch('/api/minecraft/download-with-loader', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          mc_version: versionId.value.trim(),
          loader_type: selectedVersionType.value,
          loader_version: loaderVersion.value,
          custom_name: customName.value.trim() || null
        }) 
      })
      const result = await r.json()
      
      if (!result.ok) {
        throw new Error(result.error || '下载请求失败')
      }
      
      taskId = result.task_id
    }
    
    await pollDownloadProgress(taskId)
    
  } catch (e: any) {
    showToast(`下载失败: ${e.message}`, 'error')
    downloadTasks.value.forEach(task => {
      if (task.status !== 'completed') {
        task.status = 'failed'
        task.statusText = '下载失败'
      }
    })
    isDownloading.value = false
  }
}

async function pollDownloadProgress(taskId: string) {
  const stageMap: Record<string, number> = {
    'version_info': 0,
    'client_jar': 1,
    'libraries': 2,
    'assets': 3,
    'complete': 4
  }
  
  let pollCount = 0
  const maxPolls = 600
  
  while (pollCount < maxPolls) {
    try {
      const r = await fetch(`/api/minecraft/download-progress?task_id=${encodeURIComponent(taskId)}`)
      
      if (!r.ok) {
        if (r.status === 404) {
          await new Promise(resolve => setTimeout(resolve, 500))
          pollCount++
          continue
        }
        throw new Error(`获取进度失败: ${r.status}`)
      }
      
      const result = await r.json()
      
      if (result.ok && result.progress) {
        const progress = result.progress
        const stage = progress.stage
        const stageIndex = stageMap[stage] ?? -1
        
        if (stageIndex >= 0 && stageIndex < downloadTasks.value.length) {
          const task = downloadTasks.value[stageIndex]
          task.progress = progress.percentage || 0
          task.status = 'downloading'
          task.statusText = progress.message || '下载中...'
          
          for (let i = 0; i < stageIndex; i++) {
            if (downloadTasks.value[i].status !== 'completed') {
              downloadTasks.value[i].progress = 100
              downloadTasks.value[i].status = 'completed'
              downloadTasks.value[i].statusText = '✓ 完成'
            }
          }
        }
        
        if (stage === 'complete') {
          downloadTasks.value.forEach(task => {
            task.progress = 100
            task.status = 'completed'
            task.statusText = '✓ 完成'
          })
          showToast(`版本 ${taskId} 下载成功！`, 'success')
          isDownloading.value = false
          
          // 等待1秒后清空进度条并跳转到游戏联机页面
          await new Promise(resolve => setTimeout(resolve, 1000))
          downloadTasks.value = []
          router.push('/multiplayer')
          
          return
        }
        
        if (stage === 'error') {
          throw new Error(progress.message || '下载失败')
        }
      }
      
      await new Promise(resolve => setTimeout(resolve, 1000))
      pollCount++
      
    } catch (e: any) {
      showToast(`下载失败: ${e.message}`, 'error')
      downloadTasks.value.forEach(task => {
        if (task.status !== 'completed') {
          task.status = 'failed'
          task.statusText = '失败'
        }
      })
      isDownloading.value = false
      return
    }
  }
}

onMounted(() => {
  loadVersions()
  loadInstalledVersions()
})
</script>

<style scoped>
.game-page {
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

.download-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-label {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
}

.version-filter-group {
  margin-bottom: 12px;
}

.version-type-filter {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-btn {
  padding: 6px 16px;
  border: 2px solid #e8e8e8;
  background: white;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  cursor: pointer;
  transition: all 0.3s ease;
}

.filter-btn:hover {
  border-color: #4a90e2;
  color: #4a90e2;
}

.filter-btn.active {
  background: linear-gradient(135deg, #4a90e2 0%, #357abd 100%);
  border-color: #4a90e2;
  color: white;
}

.version-type-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.type-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: white;
  border: 2px solid #e8e8e8;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.type-btn:hover {
  border-color: #4a90e2;
}

.type-btn.active {
  border-color: #4a90e2;
  background: linear-gradient(135deg, #e8f4f8 0%, #f0f9ff 100%);
}

.type-icon {
  width: 40px;
  height: 40px;
  object-fit: contain;
}

.type-label {
  font-size: 13px;
  font-weight: 600;
  color: #2c3e50;
}

.version-selector {
  display: flex;
  gap: 12px;
}

.qq-select {
  flex: 1;
  height: 40px;
  padding: 0 12px;
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  background: white;
  cursor: pointer;
}

.qq-select:focus {
  outline: none;
  border-color: #4a90e2;
}

.qq-input {
  width: 100%;
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

.required-mark {
  color: #f56c6c;
  font-weight: 700;
  margin-left: 4px;
}

.error-hint {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fef0f0;
  border: 1px solid #fde2e2;
  border-radius: 6px;
  color: #f56c6c;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.success-hint {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f0f9ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  color: #1d4ed8;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.form-actions {
  margin-top: 8px;
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

.qq-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.qq-btn-download {
  background: linear-gradient(135deg, #52c41a 0%, #73d13d 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(82, 196, 26, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.qq-btn-download:hover:not(:disabled) {
  background: linear-gradient(135deg, #73d13d 0%, #95de64 100%);
  transform: translateY(-2px);
}

.qq-btn-large {
  height: 48px;
  font-size: 16px;
  font-weight: 700;
}

.qq-btn-block {
  width: 100%;
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
  border: 1px solid #e8e8e8;
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

.btn-icon {
  font-size: 20px;
}
</style>
