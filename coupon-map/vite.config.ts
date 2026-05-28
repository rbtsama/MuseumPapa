import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5174, strictPort: false },
  // Data files in public/data are large (passes.json ~5.4MB). Disable HTTP cache
  // so a stale browser copy can never make correct data look wrong.
  preview: { headers: { "Cache-Control": "no-store" } },
});
