import { describe, it, expect } from "vitest";
import { Request, Response, NextFunction } from "express";
import { authMiddleware } from "../../src/middleware/auth";

describe("Auth Middleware", () => {
  it("authMiddleware should block requests without token", () => {
    process.env["GEN_TOKEN"] = "secret-token";

    const mockReq = {
      headers: {},
      path: "/protected",
    } as unknown as Request;

    let statusCode = 0;
    const mockRes = {
      status: (code: number) => {
        statusCode = code;
        return {
          json: () => {},
        };
      },
    } as unknown as Response;

    const mockNext = () => {};

    authMiddleware(mockReq, mockRes, mockNext as NextFunction);

    expect(statusCode).toBe(401);
  });

  it("authMiddleware should block requests with wrong token", () => {
    process.env["GEN_TOKEN"] = "secret-token";

    const mockReq = {
      headers: { authorization: "Bearer wrong-token" },
      path: "/protected",
    } as unknown as Request;

    let statusCode = 0;
    const mockRes = {
      status: (code: number) => {
        statusCode = code;
        return {
          json: () => {},
        };
      },
    } as unknown as Response;

    const mockNext = () => {};

    authMiddleware(mockReq, mockRes, mockNext as NextFunction);

    expect(statusCode).toBe(401);
  });
});
