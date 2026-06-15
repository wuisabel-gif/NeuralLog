import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// A relative base lets the same build run from a domain root (when served by the
// NeuralLog API) and from a project subpath (GitHub Pages, e.g. /NeuralLog/).
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});
