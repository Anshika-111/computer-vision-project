import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API runs on :8000 (uvicorn server.main:app). Proxying /api keeps the
// frontend on one origin, so the server needs no CORS setup.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
