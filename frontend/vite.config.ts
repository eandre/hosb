import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The app's gateway under `encore run`: the app port serves it by name, at
// /api/<path>. The dev server proxies the API there.
const gateway = process.env.ENCORE_GATEWAY_URL ?? 'http://localhost:4000/api'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  build: {
    // The backend serves the built app (see backend/main.py).
    outDir: '../backend/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: gateway,
        changeOrigin: true,
        rewrite: (p) => new URL(gateway).pathname.replace(/\/$/, '') + p,
      },
    },
  },
})
