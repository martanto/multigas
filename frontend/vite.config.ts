import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
export default defineConfig(({ mode }) => {
  const root = path.resolve(import.meta.dirname, "..");
  const env = loadEnv(mode, root, "MULTIGAS_");
  return {
    envDir: root,
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
    server: {
      proxy: {
        "/api":
          process.env.MULTIGAS_API_TARGET ||
          env.MULTIGAS_API_TARGET ||
          "http://127.0.0.1:8001",
      },
    },
  };
});
