import { defineConfig } from "vitest/config";

/** Unit-Tests nur unter src/; e2e/ gehoert Playwright. Komponenten-Tests importieren ueber "@/" wie der App-Code. */
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
