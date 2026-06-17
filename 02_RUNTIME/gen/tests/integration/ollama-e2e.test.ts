/**
 * E2E integration tests: Ollama layer
 *
 * Spins up a lightweight mock Ollama HTTP server on a random port,
 * then exercises the full stack:
 *   OllamaClient → OllamaEnricher → OllamaTriage
 *   and the Express /ollama/* route via supertest.
 */

import { describe, it, expect, beforeAll, afterAll } from "vitest";
import http from "http";
import express from "express";
import type { AddressInfo } from "net";
import request from "supertest";
import { OllamaClient } from "../../src/ollama/ollama-client";
import { OllamaEnricher } from "../../src/ollama/ollama-enricher";
import { OllamaTriage } from "../../src/ollama/ollama-triage";
import { ollamaRouter, initializeOllamaRouter } from "../../src/routes/ollama-route";

// ---------------------------------------------------------------------------
// Mock Ollama server
// ---------------------------------------------------------------------------

interface MockOllamaScenario {
  generateResponse: string;
  modelsResponse: Array<{ name: string }>;
}

let mockScenario: MockOllamaScenario = {
  generateResponse: '{"intent":"bash_command","category":"execution","risk_level":"low","summary":"Listed directory"}',
  modelsResponse: [{ name: "mistral:7b" }, { name: "llava:13b" }],
};

function createMockOllamaServer(): http.Server {
  const app = express();
  app.use(express.json());

  app.get("/api/tags", (_req, res) => {
    res.json({ models: mockScenario.modelsResponse });
  });

  app.post("/api/generate", (_req, res) => {
    res.json({
      model: "mistral:7b",
      response: mockScenario.generateResponse,
      done: true,
    });
  });

  return http.createServer(app);
}

// ---------------------------------------------------------------------------
// Test app (Gen /ollama routes only)
// ---------------------------------------------------------------------------

function createTestApp(ollamaBaseUrl: string) {
  const app = express();
  app.use(express.json());

  const client = new OllamaClient(ollamaBaseUrl, 5_000);
  const triage = new OllamaTriage(client, "mistral:7b", 0.7);
  initializeOllamaRouter(client, triage);

  app.use("/ollama", ollamaRouter);
  return app;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Ollama E2E", () => {
  let mockServer: http.Server;
  let ollamaBaseUrl: string;
  let testApp: ReturnType<typeof express>;

  beforeAll(async () => {
    mockServer = createMockOllamaServer();
    await new Promise<void>((resolve) => mockServer.listen(0, resolve));
    const port = (mockServer.address() as AddressInfo).port;
    ollamaBaseUrl = `http://127.0.0.1:${port}`;
    testApp = createTestApp(ollamaBaseUrl);
  });

  afterAll(() => {
    mockServer.close();
  });

  // --- OllamaClient against mock server ---

  describe("OllamaClient (live mock server)", () => {
    it("isAvailable returns true when mock server is up", async () => {
      const client = new OllamaClient(ollamaBaseUrl);
      expect(await client.isAvailable()).toBe(true);
    });

    it("listModels returns mock models", async () => {
      const client = new OllamaClient(ollamaBaseUrl);
      const models = await client.listModels();
      expect(models).toContain("mistral:7b");
      expect(models).toContain("llava:13b");
    });

    it("generate returns response from mock server", async () => {
      const client = new OllamaClient(ollamaBaseUrl);
      const result = await client.generate("mistral:7b", "classify this");
      expect(result).toContain("bash_command");
    });

    it("generateJSON parses JSON from mock response", async () => {
      const client = new OllamaClient(ollamaBaseUrl);
      const result = await client.generateJSON<{ intent: string }>("mistral:7b", "classify");
      expect(result?.intent).toBe("bash_command");
    });
  });

  // --- OllamaEnricher against mock server ---

  describe("OllamaEnricher (live mock server)", () => {
    it("enriches a Bash event with tags from mock Ollama", async () => {
      const client = new OllamaClient(ollamaBaseUrl);
      const enricher = new OllamaEnricher(client, "mistral:7b");
      const tags = await enricher.enrichEvent("Bash", { command: "ls -la" }, true);

      expect(tags).not.toBeNull();
      expect(tags?.intent).toBe("bash_command");
      expect(tags?.category).toBe("execution");
      expect(tags?.risk_level).toBe("low");
    });

    it("enriches a Write event without throwing", async () => {
      const client = new OllamaClient(ollamaBaseUrl);
      const enricher = new OllamaEnricher(client, "mistral:7b");
      mockScenario.generateResponse = '{"intent":"write_file","category":"code_change","risk_level":"low","summary":"Wrote a TypeScript file"}';

      const tags = await enricher.enrichEvent("Write", { file_path: "src/foo.ts" }, true);
      expect(tags?.intent).toBe("write_file");
    });
  });

  // --- OllamaTriage against mock server ---

  describe("OllamaTriage (live mock server)", () => {
    it("handles an explore task with high-confidence response", async () => {
      mockScenario.generateResponse = "Paris is the capital of France.\nCONFIDENCE: 0.98";
      const client = new OllamaClient(ollamaBaseUrl);
      const triageService = new OllamaTriage(client, "mistral:7b", 0.7);
      const result = await triageService.triageExploreTask("What is the capital of France?");

      expect(result.canHandle).toBe(true);
      expect(result.confidence).toBeGreaterThanOrEqual(0.7);
      expect(result.result).toContain("Paris");
    });

    it("returns canHandle=false when mock returns low confidence", async () => {
      mockScenario.generateResponse = "I don't know.\nCONFIDENCE: 0.1";
      const client = new OllamaClient(ollamaBaseUrl);
      const triageService = new OllamaTriage(client, "mistral:7b", 0.7);
      const result = await triageService.triageExploreTask("predict the future");

      expect(result.canHandle).toBe(false);
      expect(result.confidence).toBeLessThan(0.7);
    });
  });

  // --- /ollama route via supertest ---

  describe("GET /ollama/status", () => {
    it("returns available=true and model list from mock Ollama", async () => {
      mockScenario.modelsResponse = [{ name: "mistral:7b" }, { name: "llava:13b" }];
      const res = await request(testApp).get("/ollama/status");
      expect(res.status).toBe(200);
      expect(res.body.available).toBe(true);
      expect(res.body.models).toContain("mistral:7b");
    });
  });

  describe("POST /ollama/triage", () => {
    it("returns triage result for a valid query", async () => {
      mockScenario.generateResponse = "TypeScript is a superset of JavaScript.\nCONFIDENCE: 0.92";
      const res = await request(testApp)
        .post("/ollama/triage")
        .send({ query: "What is TypeScript?" });

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty("canHandle");
      expect(res.body).toHaveProperty("confidence");
      expect(res.body).toHaveProperty("model");
    });

    it("returns 400 when query is missing", async () => {
      const res = await request(testApp).post("/ollama/triage").send({});
      expect(res.status).toBe(400);
    });

    it("returns canHandle=true for high-confidence mock response", async () => {
      mockScenario.generateResponse = "Node.js is a JavaScript runtime.\nCONFIDENCE: 0.95";
      const res = await request(testApp)
        .post("/ollama/triage")
        .send({ query: "What is Node.js?" });

      expect(res.status).toBe(200);
      expect(res.body.canHandle).toBe(true);
    });
  });
});
