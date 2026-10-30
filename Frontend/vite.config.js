import { defineConfig } from 'vite'

export default defineConfig({
  // The app's existing HTML uses inline onclick handlers and shared global
  // functions. Serve src/ as static classic scripts so those contracts remain
  // intact while the code is split into role-based folders.
  publicDir: 'src',
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
