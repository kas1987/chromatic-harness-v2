/**
 * Structured Logging Middleware
 *
 * Logs all HTTP requests as JSON with request IDs, duration, and status codes.
 * Maps status codes to log levels (5xx=error, 4xx=warn, 2xx=info).
 */

import { Request, Response, NextFunction } from 'express';
import { v4 as uuidv4 } from 'uuid';

export interface StructuredLog {
  timestamp: string;
  requestId: string;
  method: string;
  path: string;
  status: number;
  duration_ms: number;
  level: 'debug' | 'info' | 'warn' | 'error';
  message?: string;
  error?: string;
}

// In-memory log buffer for /metrics/logs endpoint
export const logBuffer: StructuredLog[] = [];

/**
 * Structured logging middleware.
 * Logs all requests (JSON, form, etc) in JSON format with request ID.
 *
 * @param req - Express Request
 * @param res - Express Response
 * @param next - Express NextFunction
 */
export function structuredLoggingMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const requestId = req.get('x-request-id') || uuidv4();
  const startTime = Date.now();

  // Override res.send to log response
  const originalSend = res.send;
  const originalJson = res.json;

  res.send = function (data: any) {
    logRequest(requestId, req, res, startTime);
    return originalSend.call(this, data);
  };

  res.json = function (data: any) {
    logRequest(requestId, req, res, startTime);
    return originalJson.call(this, data);
  };

  // Handle response errors
  res.on('error', (err) => {
    const log: StructuredLog = {
      timestamp: new Date().toISOString(),
      requestId,
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_ms: Date.now() - startTime,
      level: 'error',
      error: err.message,
    };
    console.log(JSON.stringify(log));
    logBuffer.push(log);
  });

  next();
}

/**
 * Log a single request/response pair.
 * Maps status code to log level and writes to console + buffer.
 *
 * @param requestId - Unique request identifier
 * @param req - Express Request
 * @param res - Express Response
 * @param startTime - Request start timestamp
 */
function logRequest(
  requestId: string,
  req: Request,
  res: Response,
  startTime: number
): void {
  const duration = Date.now() - startTime;
  const level = determineLogLevel(res.statusCode);

  const log: StructuredLog = {
    timestamp: new Date().toISOString(),
    requestId,
    method: req.method,
    path: req.path,
    status: res.statusCode,
    duration_ms: duration,
    level,
  };

  // Log to console (JSON format for parsing)
  console.log(JSON.stringify(log));

  // Add to in-memory buffer (for /metrics/logs endpoint)
  logBuffer.push(log);

  // Keep buffer size bounded (max 1000 entries)
  if (logBuffer.length > 1000) {
    logBuffer.shift();
  }
}

/**
 * Determine log level based on HTTP status code.
 * @param statusCode - HTTP status code
 * @returns Log level (debug, info, warn, error)
 */
function determineLogLevel(statusCode: number): StructuredLog['level'] {
  if (statusCode >= 500) return 'error';
  if (statusCode >= 400) return 'warn';
  if (statusCode >= 200 && statusCode < 300) return 'info';
  return 'debug';
}
