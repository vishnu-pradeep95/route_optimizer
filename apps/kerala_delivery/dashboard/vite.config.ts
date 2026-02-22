import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite configuration for the Kerala LPG Delivery Ops Dashboard.
 *
 * Why proxy /api and /health to localhost:8000 in dev:
 * The FastAPI backend runs on port 8000 while Vite dev server runs
 * on port 5173. The proxy avoids CORS issues during development
 * and mirrors the production setup where both are served from
 * the same origin (or behind a reverse proxy like nginx).
 *
 * See: https://vite.dev/config/server-options.html#server-proxy
 */
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forward all /api/* requests to the FastAPI backend
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Forward health check endpoint too
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
