import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: ["frontend"],
    proxy: {
      "/api": { target: "http://backend:8000", changeOrigin: true },
      "/ws": { target: "ws://backend:8000", ws: true, changeOrigin: true },
    },
  },
});
