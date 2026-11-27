/* global process */
export default {
  root: process.env.ADMIN_ROOT,
  define: { "import.meta.env.VITE_API_URL": JSON.stringify("/api") },

  server: {
    port: 19173,
    strictPort: true,
    fs: { strict: false },
    proxy: {
      "/api": {
        target: "http://localhost:18000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
};
