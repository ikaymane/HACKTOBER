import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";

// maplibre-gl 6 loads its worker from a sibling .mjs next to the bundle, which the bundler can't see.
const maplibreWorker = (): Plugin => ({
  name: "maplibre-worker",
  apply: "build",
  generateBundle() {
    for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
      const source = readFileSync(new URL(`./node_modules/maplibre-gl/dist/${file}`, import.meta.url));
      this.emitFile({ type: "asset", fileName: `assets/${file}`, source });
    }
  },
});

export default defineConfig({
  plugins: [react(), tailwindcss(), maplibreWorker()],
  resolve: {
    alias: {
      "@shared": fileURLToPath(new URL("../shared", import.meta.url)),
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  // maplibre-gl 6 spawns its worker from a sibling .mjs; pre-bundling breaks that path.
  optimizeDeps: { exclude: ["maplibre-gl"] },
  server: {
    port: 5173,
    host: "127.0.0.1", // "localhost" tries IPv6 first on Windows: 200 ms lost on each connection
    fs: { allow: [".."] },
    proxy: {
      "/api": {
        target: process.env.API_TARGET ?? "http://127.0.0.1:8000", // override to run against another backend
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
