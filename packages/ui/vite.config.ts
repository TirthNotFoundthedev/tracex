import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Serves the component gallery (`npm run gallery`) and runs the tests.
export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", css: true },
});
