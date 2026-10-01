import { defineConfig } from "vitest/config";

/** Unit-Tests nur unter src/; e2e/ gehoert Playwright. "@/..." wie in tsconfig, damit Komponenten-Tests laufen. */
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
