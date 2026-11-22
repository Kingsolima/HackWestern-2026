import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, /api and /health are proxied to the FastAPI orchestrator, and /cad to the CAD worker.
export default defineConfig({
  plugins: [react()],
  // The lazy CadViewer chunk is three.js itself (~585 kB) and cannot be split further.
  build: { chunkSizeWarningLimit: 650 },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/cad': { target: 'http://localhost:8001', rewrite: (p) => p.replace(/^\/cad/, '') },
    },
  },
})
