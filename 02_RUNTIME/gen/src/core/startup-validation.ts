/**
 * Startup validation — enforced in ALL environments.
 *
 * Gen is the only safety net when Claude Code bypassPermissions=true.
 * A missing or dev-placeholder token leaves every tool call unguarded.
 * This check runs before any route is registered.
 */

const DEV_TOKENS = new Set(["test-token-dev-only", "dev-token", ""]);

export function validateStartup(): void {
  const nodeEnv = process.env.NODE_ENV ?? "development";
  const genToken = process.env.GEN_TOKEN;

  if (!genToken) {
    console.error("FATAL: GEN_TOKEN env var is not set.");
    console.error("Gen is the hook pipeline safety net — it must not start without a secure token.");
    console.error("Set GEN_TOKEN in gen/.env and restart.");
    process.exit(1);
  }

  if (DEV_TOKENS.has(genToken)) {
    console.error(`FATAL: GEN_TOKEN is set to a known dev placeholder ("${genToken}").`);
    console.error("Generate a secure random token: node -e \"console.log(require('crypto').randomBytes(32).toString('hex'))\"");
    process.exit(1);
  }

  if (genToken.length < 16) {
    console.error(`FATAL: GEN_TOKEN is too short (${genToken.length} chars). Minimum 16 characters.`);
    process.exit(1);
  }

  console.log(`[startup] Auth validated (NODE_ENV=${nodeEnv}, token length=${genToken.length})`);
}
