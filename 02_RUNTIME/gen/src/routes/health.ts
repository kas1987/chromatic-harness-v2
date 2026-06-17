import { Router, Request, Response } from "express";

export function createHealthRouter(): Router {
  const router = Router();
  router.get("/", (req: Request, res: Response) => {
    res.json({ status: "ok", timestamp: new Date().toISOString(), uptime: process.uptime() });
  });
  return router;
}
