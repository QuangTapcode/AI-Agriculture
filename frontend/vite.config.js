import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    css: true,
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    exclude: ['node_modules/**', 'dist/**', 'tests/e2e/**', 'prototypes/**'],
  },
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true
    }
  }
})
