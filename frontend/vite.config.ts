import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Servi en production par FastAPI (atc_app.py monte frontend/dist sur "/").
// En dev (`npm run dev`), /api et /ws sont proxifies vers le serveur local.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "dist", chunkSizeWarningLimit: 900 },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
