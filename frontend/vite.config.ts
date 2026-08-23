import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/static/app/",
  plugins: [react()],
  build: {
    outDir: "../src/nfl_dfs/app/static/app",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8080",
      "/chat": "http://127.0.0.1:8080",
      "/prefs": "http://127.0.0.1:8080",
      "/results": "http://127.0.0.1:8080",
      "/players": "http://127.0.0.1:8080",
      "/entries": "http://127.0.0.1:8080",
      "/defense": "http://127.0.0.1:8080",
      "/classic": "http://127.0.0.1:8080",
      "/showdown": "http://127.0.0.1:8080",
      "/slates": "http://127.0.0.1:8080",
      "/contests": "http://127.0.0.1:8080",
      "/lineups": "http://127.0.0.1:8080",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});
