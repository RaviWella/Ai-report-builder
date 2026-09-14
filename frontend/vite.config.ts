import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
  plugins: [react(), tailwindcss()],
  define: {
    "process.env.REACT_APP_API_BASE_URL": JSON.stringify(
      env.REACT_APP_API_BASE_URL || "/api/v1"
    ),
    "process.env.REACT_APP_API_KEY": JSON.stringify(
      env.REACT_APP_API_KEY || "hrm-dev-api-key"
    ),
    "process.env.REACT_APP_TENANT_ID": JSON.stringify(
      env.REACT_APP_TENANT_ID || "demo_tenant"
    ),
    "process.env.REACT_APP_USER_ID": JSON.stringify(
      env.REACT_APP_USER_ID || "default-user"
    ),
    "process.env.REACT_APP_AUTH_TOKEN": JSON.stringify(
      env.REACT_APP_AUTH_TOKEN || ""
    ),
    "process.env.REACT_APP_SKIP_AUTH": JSON.stringify(
      env.REACT_APP_SKIP_AUTH || (mode === "development" ? "true" : "")
    ),
    "process.env.REACT_APP_HR_CURRENCY": JSON.stringify(
      env.REACT_APP_HR_CURRENCY || "LKR"
    ),
    "process.env.NODE_ENV": JSON.stringify(mode),
  },
  build: {
    target: "esnext",
  },
  server: {
    port: 5174,
    cors: true,
    proxy: {
      "/api": {
        target: env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
};
});
