// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  ssr: false,
  app: {
    baseURL: '/web/'
  },
  build: {
    transpile: ['naive-ui', 'vueuc', '@css-render/vue3-ssr', '@juggle/resize-observer']
  },
  // 开发服务器配置
  devServer: {
    port: 3000
  },
  // Nitro 代理配置
  nitro: {
    devProxy: {
      '/api': {
        target: 'http://127.0.0.1:17890',
        changeOrigin: true,
        prependPath: true
      }
    }
  },
  // Vite 配置
  vite: {
    server: {
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:17890',
          changeOrigin: true,
          secure: false
        }
      }
    }
  }
})
