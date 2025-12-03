import { ref, computed } from 'vue'

// 全局状态，确保跨组件共享
const backendUrl = ref('http://127.0.0.1:17890')
const isInitialized = ref(false)

export const useBackend = () => {
  
  // 初始化（强制使用 localhost）
  function init() {
    if (isInitialized.value) return
    
    // 无论在什么环境下（公网域名、局域网IP），前端都只请求本地后端的端口
    // 因为这是一个桌面应用的 Web UI，后端永远运行在用户本地机器上
    // 所以目标永远是 127.0.0.1:17890
    backendUrl.value = 'http://127.0.0.1:17890'
    isInitialized.value = true
  }

  // 设置新的后端地址 (保留方法但不公开 UI)
  function setBackendUrl(url: string) {
    // 移除末尾斜杠
    let cleanUrl = url.trim().replace(/\/$/, '')
    
    // 如果没有协议，默认 http
    if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
      cleanUrl = 'http://' + cleanUrl
    }
    
    backendUrl.value = cleanUrl
    
    if (typeof window !== 'undefined') {
      localStorage.setItem('flowergame_backend_url', cleanUrl)
    }
  }

  // 获取完整的 API URL
  function getApiUrl(path: string) {
    init()
    // 确保 path 以 / 开头
    const cleanPath = path.startsWith('/') ? path : '/' + path
    return `${backendUrl.value}${cleanPath}`
  }
  
  // 获取完整的 WebSocket URL
  function getWsUrl(path: string) {
    init()
    // 将 http/https 替换为 ws/wss
    let wsBase = backendUrl.value.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')
    const cleanPath = path.startsWith('/') ? path : '/' + path
    return `${wsBase}${cleanPath}`
  }
  
  // 封装 fetch
  async function fetchApi(path: string, options?: RequestInit) {
    const url = getApiUrl(path)
    return fetch(url, options)
  }

  return {
    backendUrl,
    setBackendUrl,
    getApiUrl,
    getWsUrl,
    fetchApi,
    init
  }
}
