import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
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
  // Base path for built assets. Defaults to '/' for production (Caddy serves at root).
  // Set VITE_BASE_PATH='/dashboard/' for dev docker-compose (API serves at /dashboard/).
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [
    tailwindcss(),  // Must be before react() for optimal performance
    react(),
  ],
  server: {
    proxy: {
      // Forward all /api/* requests to the FastAPI backend.
      // VITE_API_TARGET overrides the target when running inside Docker
      // (where the API is at http://api:8000, not localhost:8000).
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
      // Forward health check endpoint too
      '/health': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
