import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built UI is served by the Python app (`eacr serve`), so it is written into the package.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../src/evidence_aware_crypto_call_recognition/web/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
