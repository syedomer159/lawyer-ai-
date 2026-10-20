import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Same-origin /api in dev and prod, so the client never hardcodes a backend URL.
    proxy: { '/api': 'http://localhost:8010' },
  },
})
