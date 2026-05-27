import { defineConfig, configDefaults } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Force the automatic JSX runtime for the test transform so test files need no
  // `import React` (plugin-react's automatic runtime isn't applied to the vitest
  // transform under vite 8). Without this, JSX compiles to React.createElement.
  esbuild: { jsx: 'automatic', jsxImportSource: 'react' },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    // public/ holds build-copied admin assets (incl. node:test .mjs files that
    // aren't vitest suites) — keep them out of the React test run.
    exclude: [...configDefaults.exclude, 'public/**'],
  },
});
