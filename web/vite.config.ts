import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('/node_modules/')) return
          if (/\/(?:@react-three|three|three-stdlib|camera-controls)\//.test(id)) return 'three-runtime'
          if (/\/(?:recharts|d3-[^/]+)\//.test(id)) return 'charts'
          if (/\/(?:framer-motion|motion-dom|motion-utils)\//.test(id)) return 'motion'
          if (/\/(?:react|react-dom|scheduler)\//.test(id)) return 'react-vendor'
        },
      },
    },
  },
})
