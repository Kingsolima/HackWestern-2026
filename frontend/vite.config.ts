import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, /api and /health are proxied to the FastAPI orchestrator, and /cad to the CAD worker.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/cad': { target: 'http://localhost:8001', rewrite: (p) => p.replace(/^\/cad/, '') },
    },
  },
})
