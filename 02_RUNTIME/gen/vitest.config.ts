import { defineConfig, defaultExclude } from "vitest/config";

/**
 * Playwright browser tests are opt-in: install browsers with `npx playwright install chromium`.
 * Default `npm test` / `npm run test:run` excludes them. Use `npm run test:dispatch-ui`.
 */
export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    setupFiles: [],
    exclude: [...defaultExclude, "**/tests/integration/dispatch-ui.test.ts"],
    // Match production-safe pretool semantics in unit tests (bash/file guard blocks).
    env: {
      GEN_FORCE_FAIL_OPEN_PRETOOL_STOPS: "false",
      GEN_ENABLE_PRETOOL_STOPS: "true",
    },
  },
});
