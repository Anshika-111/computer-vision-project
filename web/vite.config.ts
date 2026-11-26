import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API runs on :8000 (uvicorn server.main:app). Proxying /api keeps the
// frontend on one origin, so the server needs no CORS setup.
// If :8000 is taken, run the API elsewhere and set API_PORT, e.g. API_PORT=8001 npm run dev.
const apiPort = process.env.API_PORT ?? "8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": `http://localhost:${apiPort}`,
    },
  },
});
