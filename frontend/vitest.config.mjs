import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 独立测试配置：避免 vitest 为解析 vite.config.ts 而生成临时文件，
// 并把缓存写到项目内的 .vitest 目录（不要写进 node_modules）。
export default defineConfig({
  plugins: [react()],
  cacheDir: './.vitest',
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
