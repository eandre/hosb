import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The build goes to dist/app, which the web service embeds (main.go).
// `bun run dev` serves the app alone; it passes /api on to an `encore run`
// session's gateway, on the app port (ENCORE_GATEWAY_URL to name another).
const gateway = process.env.ENCORE_GATEWAY_URL ?? "http://api.localhost:4000"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  build: {
    outDir: "dist/app",
    emptyOutDir: true,
  },
  server: {
    proxy: { "/api": { target: gateway, changeOrigin: true } },
  },
})
