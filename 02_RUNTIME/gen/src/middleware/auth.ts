import { Request, Response, NextFunction } from "express";

const DEV_TOKENS = new Set(["test-token-dev-only", "dev-token", ""]); // pragma: allowlist secret

export function authMiddleware(req: Request, res: Response, next: NextFunction): void {
  const expectedToken = process.env.GEN_TOKEN; // pragma: allowlist secret

  // Hard fail — never allow requests when the token is absent or a known dev placeholder.
  // The Gen hook pipeline is the only safety net when bypassPermissions=true.
  // Silent open-door behaviour is not acceptable.
  if (!expectedToken || DEV_TOKENS.has(expectedToken)) {
    console.error(
      "[auth] FATAL: GEN_TOKEN is not set or is a known dev placeholder. " +
        "Set a secure random token in your .env and restart Gen."
    );
    res.status(503).json({
      error: "Service unavailable — GEN_TOKEN not configured. Set a secure token and restart.",
    });
    return;
  }

  const token = req.headers.authorization?.replace("Bearer ", ""); // pragma: allowlist secret
  if (!token || token !== expectedToken) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }

  next();
}
