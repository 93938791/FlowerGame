<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <span class="logo-icon">🌸</span>
        <span class="logo-text">FlowerGame</span>
      </div>
    </div>
    
    <div class="menu-list">
      <NuxtLink
        v-for="item in menuItems" 
        :key="item.path"
        :to="item.path"
        :class="['menu-item']"
        active-class="active"
      >
        <span class="menu-icon">{{ item.icon }}</span>
        <span class="menu-text">{{ item.name }}</span>
      </NuxtLink>
    </div>
    
    <!-- 账号登录区域 -->
    <div class="sidebar-account">
      <!-- 登录状态显示 -->
      <div v-if="accountInfo || offlineAccount" class="account-card">
        <!-- 3D皮肤预览 -->
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
        
        <button @click="handleLogout" class="logout-btn">
          退出登录
        </button>
      </div>
      
      <!-- 登录按钮 -->
      <div v-else class="login-buttons">
        <button 
          @click="$emit('start-device-auth')" 
          class="sidebar-login-btn microsoft"
          :disabled="isAuthenticating"
        >
          <span class="btn-icon">🔐</span>
          <span class="btn-text">{{ isAuthenticating ? '请求中...' : '正版登录' }}</span>
        </button>
        <button @click="$emit('show-offline-login')" class="sidebar-login-btn offline">
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
          'online': networkConnected,
          'offline': !networkConnected
        }"></span>
        <span class="status-text">
          {{ networkConnected ? '网络已连接' : '网络未连接' }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  accountInfo: any
  offlineAccount: string | null
  isAuthenticating: boolean
  networkConnected: boolean
}>()

const emit = defineEmits<{
  'start-device-auth': []
  'show-offline-login': []
  'logout': []
  'logout-offline': []
}>()

const menuItems = [
  { path: '/', name: '网络管理', icon: '🌐' },
  { path: '/game', name: '游戏管理', icon: '🎮' },
  { path: '/sync', name: '存档同步', icon: '☁️' },
  { path: '/multiplayer', name: '游戏联机', icon: '🎯' }
]

function getSkinUrl(uuid: string, type: string = 'face', size: number = 64): string {
  // 移除 UUID 中的连字符 (例如: "123e4567-e89b-12d3-a456-426614174000" -> "123e4567e89b12d3a456426614174000")
  const cleanUuid = uuid.replace(/-/g, '')
  // 使用 Visage API (更稳定的 3D 皮肤渲染)
  if (type === 'full') {
    return `https://visage.surgeplay.com/full/${size}/${cleanUuid}`
  }
  return `https://visage.surgeplay.com/face/${size}/${cleanUuid}`
}

function getOfflineSkinUrl(type: string = 'face', size: number = 64): string {
  const defaultUuid = '8667ba71b85a4004af54457a9734eed7' // Steve (无连字符)
  if (type === 'full') {
    return `https://visage.surgeplay.com/full/${size}/${defaultUuid}`
  }
  return `https://visage.surgeplay.com/face/${size}/${defaultUuid}`
}

function handleLogout() {
  if (props.accountInfo) {
    emit('logout')
  } else {
    emit('logout-offline')
  }
}
</script>

<style scoped>
/* 侧边栏样式 */
.sidebar {
  width: 240px;
  background: linear-gradient(180deg, #4a90e2 0%, #357abd 100%);
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
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
  text-decoration: none;
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

.sidebar-account {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.account-card {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 16px;
  padding-top: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  position: relative;
  overflow: hidden;
  min-height: 280px;
}

.skin-3d-preview {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  width: 140px;
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 0;
  pointer-events: none;
}

.skin-3d {
  width: auto;
  height: 100%;
  object-fit: contain;
  image-rendering: crisp-edges;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3));
}

.account-info {
  text-align: center;
  width: 100%;
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.account-name {
  color: white;
  font-size: 14px;
  font-weight: 600;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
  background: rgba(0, 0, 0, 0.3);
  padding: 4px 12px;
  border-radius: 4px;
  backdrop-filter: blur(5px);
}

.account-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.account-badge.premium {
  background: #52c41a;
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.account-badge.offline {
  background: #8c8c8c;
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.logout-btn {
  width: 100%;
  padding: 8px;
  border: none;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  z-index: 1;
  backdrop-filter: blur(5px);
}

.logout-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.login-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
  z-index: 1;
}

.sidebar-login-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.sidebar-login-btn.microsoft {
  background: linear-gradient(135deg, #00d9ff 0%, #00b8d4 100%);
  color: white;
}

.sidebar-login-btn.microsoft:hover {
  background: linear-gradient(135deg, #00b8d4 0%, #0097a7 100%);
}

.sidebar-login-btn.offline {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.sidebar-login-btn.offline:hover {
  background: rgba(255, 255, 255, 0.3);
}

.sidebar-login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: white;
  font-size: 13px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #8c8c8c;
}

.status-dot.online {
  background: #52c41a;
  animation: pulse 2s infinite;
}

.status-dot.offline {
  background: #8c8c8c;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  font-size: 13px;
}
</style>
