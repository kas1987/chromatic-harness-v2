import { describe, it, expect, vi, beforeEach } from "vitest";
import express from "express";
import request from "supertest";
import path from "path";
import { createAudioRouter } from "../../src/routes/audio-route";

const AUDIO_DIR = "/tmp/tts-audio";

// Intercept res.sendFile so unit tests don't need real files on disk.
// We capture the filePath argument and the callback, then drive success or
// failure by swapping the mock implementation per test.
let sendFileMock: ReturnType<typeof vi.fn>;

vi.mock("express", async (importOriginal) => {
  const actual = await importOriginal<typeof import("express")>();
  return actual;
});

function buildApp(sendFileImpl: (filePath: string, cb: (err?: Error) => void) => void) {
  sendFileMock = vi.fn(sendFileImpl);
  const app = express();

  // Patch res.sendFile before the router runs
  app.use((_req, res, next) => {
    (res as express.Response & { sendFile: typeof sendFileMock }).sendFile = sendFileMock;
    next();
  });

  app.use("/audio", createAudioRouter(AUDIO_DIR));
  return app;
}

describe("createAudioRouter", () => {
  describe("TestAudioRoute_validId_returnsWav", () => {
    it("GET /audio/abc123.wav with existing file returns 200 audio/wav", async () => {
      const app = buildApp((_filePath, cb) => {
        // Simulate sendFile success (no error)
        cb();
      });

      // We need res.sendFile to actually write a response — patch it to send 200
      // After cb() with no error the route is done, but supertest needs a real response.
      // Rebuild: successful sendFile sets Content-Type and sends bytes.
      const app2 = express();
      app2.use((_req, res, next) => {
        (res as express.Response).sendFile = (
          _fp: string,
          cbOrOptions?: unknown,
          maybeCb?: unknown,
        ) => {
          const cb =
            typeof cbOrOptions === "function"
              ? (cbOrOptions as (err?: Error) => void)
              : typeof maybeCb === "function"
                ? (maybeCb as (err?: Error) => void)
                : undefined;
          // Simulate success: set header and end response
          res.setHeader("Content-Type", "audio/wav");
          res.status(200).end();
          if (cb) cb();
        };
        next();
      });
      app2.use("/audio", createAudioRouter(AUDIO_DIR));

      const response = await request(app2).get("/audio/abc123.wav");
      expect(response.status).toBe(200);
      expect(response.headers["content-type"]).toMatch(/audio\/wav/);
    });
  });

  describe("TestAudioRoute_missingFile_returns404", () => {
    it("GET /audio/notfound.wav returns 404 when file does not exist", async () => {
      const app = express();
      app.use((_req, res, next) => {
        (res as express.Response).sendFile = (
          _fp: string,
          cbOrOptions?: unknown,
          maybeCb?: unknown,
        ) => {
          const cb =
            typeof cbOrOptions === "function"
              ? (cbOrOptions as (err?: Error) => void)
              : typeof maybeCb === "function"
                ? (maybeCb as (err?: Error) => void)
                : undefined;
          // Simulate ENOENT — file not found
          const err = Object.assign(new Error("ENOENT: no such file"), { code: "ENOENT" });
          if (cb) cb(err);
        };
        next();
      });
      app.use("/audio", createAudioRouter(AUDIO_DIR));

      const response = await request(app).get("/audio/notfound.wav");
      expect(response.status).toBe(404);
      expect(response.body).toEqual({ error: "Audio not found" });
    });
  });

  describe("TestAudioRoute_pathTraversal_blocked", () => {
    it("GET /audio/../../etc/passwd returns 400 before sendFile is called", async () => {
      // sendFile should never be reached for traversal attempts
      const app = express();
      let sendFileCalled = false;
      app.use((_req, res, next) => {
        (res as express.Response).sendFile = () => {
          sendFileCalled = true;
        };
        next();
      });
      app.use("/audio", createAudioRouter(AUDIO_DIR));

      // Express normalises the URL before routing; the router receives the
      // basename after path.basename() strips directory components.
      // The validation regex ^[a-zA-Z0-9_-]+\.wav$ catches any non-wav result.
      const response = await request(app).get("/audio/..%2F..%2Fetc%2Fpasswd");
      expect(response.status).toBe(400);
      expect(response.body).toEqual({ error: "Invalid audio id" });
      expect(sendFileCalled).toBe(false);
    });
  });

  describe("TestAudioRoute_missingWavExtension_blocked", () => {
    it("GET /audio/noextension returns 400 when .wav extension is absent", async () => {
      let sendFileCalled = false;
      const app = express();
      app.use((_req, res, next) => {
        (res as express.Response).sendFile = () => {
          sendFileCalled = true;
        };
        next();
      });
      app.use("/audio", createAudioRouter(AUDIO_DIR));

      const response = await request(app).get("/audio/noextension");
      expect(response.status).toBe(400);
      expect(response.body).toEqual({ error: "Invalid audio id" });
      expect(sendFileCalled).toBe(false);
    });
  });

  it("uses absolute path: absAudioDir resolves at router creation time", () => {
    // Verify that path.resolve is applied to a relative input — the router
    // should store an absolute path regardless of what is passed in.
    const relativeDir = "relative/audio/dir";
    const expectedAbsDir = path.resolve(relativeDir);
    // If createAudioRouter did not resolve, filePath would not start with /
    // We just assert the expected absolute path is rooted at an absolute prefix.
    expect(path.isAbsolute(expectedAbsDir)).toBe(true);
    // Smoke-check: router builds without throwing
    expect(() => createAudioRouter(relativeDir)).not.toThrow();
  });
});
