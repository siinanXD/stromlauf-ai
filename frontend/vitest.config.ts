import { defineConfig } from "vitest/config";

/** Unit-Tests nur unter src/; e2e/ gehoert Playwright. */
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
