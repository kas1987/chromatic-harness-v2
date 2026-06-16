import { Request, Response, NextFunction } from "express";
import { config } from "../config";

export function adminAuthMiddleware(req: Request, res: Response, next: NextFunction): void {
  const token = req.headers["x-admin-token"];

  if (!token || token !== config.adminToken) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }

  next();
}
