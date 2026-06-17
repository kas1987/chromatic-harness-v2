import { Request, Response, NextFunction } from "express";
import { config } from "../config";

export function adminAuthMiddleware(req: Request, res: Response, next: NextFunction): void {
  const authHeader = req.headers["x-admin-token"];

  if (!authHeader || authHeader !== config.adminToken) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }

  next();
}
