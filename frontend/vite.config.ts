import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api/auth": {
        target: process.env.AUTH_UPSTREAM || "http://127.0.0.1:8001",
      },
      "/api/accounts": {
        target: process.env.PAYMENT_UPSTREAM || "http://127.0.0.1:8000",
      },
      "/api/payments": {
        target: process.env.PAYMENT_UPSTREAM || "http://127.0.0.1:8000",
      },
      "/status/auth": {
        target: process.env.AUTH_UPSTREAM || "http://127.0.0.1:8001",
        rewrite: () => "/health",
      },
      "/status/payment": {
        target: process.env.PAYMENT_UPSTREAM || "http://127.0.0.1:8000",
        rewrite: () => "/health/ready",
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
  build: {
    rollupOptions: { output: { manualChunks: { charts: ["recharts"] } } },
  },
});
