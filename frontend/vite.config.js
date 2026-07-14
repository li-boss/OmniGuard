import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia'],
          element: ['element-plus'],
          socket: ['socket.io-client'],
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': apiTarget,
      '/static': apiTarget,
      '/socket.io': {
        target: apiTarget,
        ws: true,
      },
    },
  },
})
