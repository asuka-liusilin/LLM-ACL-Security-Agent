import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发服务器固定绑定 127.0.0.1:5173，
// 并把 /api 代理到 FastAPI（默认 8000 端口），避免前端跨域配置。
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
