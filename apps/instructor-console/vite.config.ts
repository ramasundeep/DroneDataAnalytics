/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The console talks to the CD Sim API only through the relative path `/api`.
// In dev, Vite proxies `/api/*` to the API service and strips the `/api`
// prefix; in production the bundled nginx does exactly the same.
const apiTarget = process.env.CDSIM_API_URL ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
  },
});
