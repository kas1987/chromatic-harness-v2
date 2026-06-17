import { defineConfig } from "vitest/config";

/** Runs only `dispatch-ui` Playwright smoke tests (see `npm run test:dispatch-ui`). */
export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["tests/integration/dispatch-ui.test.ts"],
  },
});
