import type { Request } from "express";
import { context, propagation, ROOT_CONTEXT, type Context } from "@opentelemetry/api";

/**
 * Extract W3C traceparent/tracestate from incoming hook requests so hook spans
 * link to the client trace when the hook runner propagates headers.
 */
export function extractIncomingContext(req: Request): Context {
  return propagation.extract(ROOT_CONTEXT, req.headers);
}
