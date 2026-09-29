import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// During `npm run dev`, API and WebSocket calls go to a running `alfred-ui` server.
const backend = process.env.ALFRED_UI_BACKEND ?? 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: fileURLToPath(new URL('../src/alfred_ui/static', import.meta.url)),
    emptyOutDir: true,
    chunkSizeWarningLimit: 1600,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: backend, ws: true, changeOrigin: false },
    },
  },
})
