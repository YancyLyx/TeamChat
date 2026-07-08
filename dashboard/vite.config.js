import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiPort = env.VITE_API_PORT || '8000'
  const apiOrigin = `http://127.0.0.1:${apiPort}`

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        '/api': apiOrigin,
        '/ws': {
          target: apiOrigin.replace('http', 'ws'),
          ws: true,
        },
      },
    },
  }
})
