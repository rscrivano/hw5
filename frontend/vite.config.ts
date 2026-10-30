import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The desk talks straight to the FastAPI backend at http://localhost:8000 (CORS allows :5173).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
