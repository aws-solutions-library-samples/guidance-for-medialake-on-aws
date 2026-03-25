import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  define: {
    global: "globalThis",
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "./runtimeConfig": "./runtimeConfig.browser",
    },
  },
  build: {
    target: "esnext",
    // Raise the warning threshold so noisy warnings don't hide real issues
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Core React runtime — must load first, everything depends on it
          if (
            id.includes("node_modules/react/") ||
            id.includes("node_modules/react-dom/") ||
            id.includes("node_modules/react-router/") ||
            id.includes("node_modules/react-i18next/") ||
            id.includes("node_modules/react-error-boundary/")
          ) {
            return "vendor-react";
          }
          // MUI — heaviest dep, cached long-term
          if (id.includes("node_modules/@mui/")) {
            return "vendor-mui";
          }
          // Data layer
          if (id.includes("node_modules/@tanstack/")) {
            return "vendor-data";
          }
          // AWS Amplify + Cognito
          if (
            id.includes("node_modules/aws-amplify/") ||
            id.includes("node_modules/@aws-amplify/") ||
            id.includes("node_modules/amazon-cognito-identity-js/")
          ) {
            return "vendor-aws";
          }
          // Pipeline editor
          if (id.includes("node_modules/@xyflow/")) {
            return "vendor-xyflow";
          }
          // i18n core (no React dependency)
          if (
            id.includes("node_modules/i18next/") ||
            id.includes("node_modules/i18next-browser-languagedetector/")
          ) {
            return "vendor-i18n";
          }
          // Forms
          if (
            id.includes("node_modules/react-hook-form/") ||
            id.includes("node_modules/@hookform/") ||
            id.includes("node_modules/zod/")
          ) {
            return "vendor-forms";
          }
        },
      },
    },
    // Enable CSS code splitting so each lazy route only loads its styles
    cssCodeSplit: true,
    // Use esbuild minification (faster than terser, good enough output)
    minify: "esbuild",
    // Generate source maps for production debugging but keep them external
    sourcemap: "hidden",
  },
  // Optimize dependency pre-bundling for dev server cold start
  optimizeDeps: {
    include: [
      "react",
      "react-dom",
      "react-router",
      "@mui/material",
      "@mui/icons-material",
      "@tanstack/react-query",
      "aws-amplify",
      "i18next",
      "react-i18next",
      "zustand",
      "axios",
      "date-fns",
    ],
  },
  css: {
    // Enable CSS modules source maps in dev for easier debugging
    devSourcemap: true,
  },
});
