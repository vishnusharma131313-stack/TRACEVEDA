import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    /*
     * Dev proxy. Only used when VITE_API_URL is EMPTY — with it set to an
     * absolute URL (see .env) axios calls the API directly and this proxy is
     * bypassed, which is why the backend's CORS list has to include
     * http://localhost:5173. Both routes work; leave .env alone unless you
     * want same-origin dev requests, in which case blank VITE_API_URL.
     */
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  build: {
    rollupOptions: {
      output: {
        /*
         * Everything used to land in one 830 kB chunk, most of it recharts
         * and framer-motion, which the login and consumer-QR screens never
         * touch. Splitting the two heavy libraries out lets a first-time
         * visitor's browser cache them separately from app code that changes
         * every deploy.
         */
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
          motion: ['framer-motion'],
        },
      },
    },
  },
})
