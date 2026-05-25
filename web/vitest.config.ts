import { defineConfig, configDefaults } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    // public/ holds build-copied admin assets (incl. node:test .mjs files that
    // aren't vitest suites) — keep them out of the React test run.
    exclude: [...configDefaults.exclude, 'public/**'],
  },
});
