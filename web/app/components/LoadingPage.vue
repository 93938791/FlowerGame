<template>
  <div class="loading-page">
    <div class="loading-content">
      <div class="logo-container">
        <div class="logo-circle">
          <span class="logo-icon">🌸</span>
        </div>
        <div class="logo-pulse"></div>
      </div>
      
      <h1 class="app-title">FlowerGame</h1>
      
      <div class="status-container">
        <div class="loading-spinner"></div>
        <div class="status-text">正在连接后端服务...</div>
        <div class="status-detail">尝试连接 localhost:17890</div>
      </div>
      
      <div class="help-text">
        <p>如果您尚未启动 FlowerGame 桌面客户端，请先启动它。</p>
        <p>如果客户端已运行，请稍候...</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 简单的展示组件，无需复杂逻辑
</script>

<style scoped>
.loading-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #0f172a;
  color: #f1f5f9;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.loading-content {
  text-align: center;
  padding: 40px;
  max-width: 400px;
  width: 90%;
}

.logo-container {
  position: relative;
  width: 80px;
  height: 80px;
  margin: 0 auto 24px;
}

.logo-circle {
  position: relative;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 25px rgba(34, 197, 94, 0.4);
  z-index: 2;
}

.logo-icon {
  font-size: 40px;
}

.logo-pulse {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(34, 197, 94, 0.4);
  border-radius: 50%;
  z-index: 1;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  70% {
    transform: scale(1.5);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 0;
  }
}

.app-title {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 40px;
  background: linear-gradient(to right, #22c55e, #4ade80);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
}

.status-container {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  backdrop-filter: blur(10px);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(34, 197, 94, 0.2);
  border-top-color: #22c55e;
  border-radius: 50%;
  margin: 0 auto 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-text {
  font-size: 16px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 8px;
}

.status-detail {
  font-size: 13px;
  color: #94a3b8;
}

.help-text {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
}

.help-text p {
  margin-bottom: 8px;
}
</style>
