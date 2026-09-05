import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import gitInfo from './vite-plugin-git-info.js'

export default defineConfig({
  plugins: [react(), gitInfo()],
  // Keep Vite's dep-optimizer cache OUT of the repo. The default is
  // node_modules/.vite, which lives in Dropbox here: Dropbox locks files
  // while syncing, the optimizer's atomic rename of deps_temp_* -> deps
  // fails, and the server is left serving ?v= hashes for a deps folder
  // that no longer exists (blank page, 504 'Outdated Optimize Dep').
  cacheDir: join(process.env.LOCALAPPDATA || tmpdir(), 'rc_agent', 'vite-cache'),
  server: {
    // 5173 (Vite's default) is used by another app on this machine.
    // strictPort makes a conflict fail loudly instead of silently hopping ports.
    port: 5273,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
