import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// Build straight into the backend's static dir so FastAPI serves the app.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL("../soma/static", import.meta.url)),
    emptyOutDir: true,
  },
  server: {
    // In dev, proxy API calls to the FastAPI backend on :8000.
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
