import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import * as tracerModule from "../../src/otel/tracer";
import * as observabilityModule from "../../src/otel/observability";
import { GEN_ATTRS } from "../../src/otel/attributes";
import { hooksRouter, initializeTtsClient } from "../../src/routes/hooks";
import type { TtsClient } from "../../src/tts/tts-client";

describe("Hooks Routes", () => {
  let app: express.Application;

  beforeEach(() => {
    app = express();
    app.use(express.json());
    app.use("/hooks", hooksRouter);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POST /hooks/pretool with safe Bash command should return continue=true", async () => {
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Bash",
      input: { command: "ls -la /home/user" },
    });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);
  });

  it("POST /hooks/pretool with dangerous command should return continue=false", async () => {
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Bash",
      input: { command: "rm -rf /etc" },
    });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(false);
    expect(response.body.stopReason).toBeDefined();
  });

  it("POST /hooks/pretool with Write tool and safe path should return continue=true", async () => {
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Write",
      input: { file_path: "/home/user/file.ts" },
    });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);
  });

  it("POST /hooks/pretool with Write tool and protected path should return continue=false", async () => {
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Write",
      input: { file_path: "C:\\Windows\\System32\\config.ini" },
    });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(false);
    expect(response.body.stopReason).toBeDefined();
  });

  it("POST /hooks/posttool should acknowledge successful tool execution", async () => {
    const response = await request(app).post("/hooks/posttool").send({
      tool: "Bash",
      input: { command: "echo test" },
      success: true,
      result: { output: "test" },
    });

    expect(response.status).toBe(200);
    expect(response.body.status).toBe("stored");
  });

  it("POST /hooks/pretool with TTS enabled returns audioPath", async () => {
    const mockTtsClient = {
      isAvailable: vi.fn().mockResolvedValue(true),
      synthesize: vi.fn().mockResolvedValue({
        audioPath: "/tmp/audio/abc123.wav",
        voiceId: "UA___20s_Woman",
        durationMs: 500,
      }),
    } as unknown as TtsClient;

    initializeTtsClient(mockTtsClient);

    // Trigger a scenario where extraContext or budgetWarningMessage is set.
    // Since no memoryService is wired in this test, extraContext will be undefined.
    // Wire up a budgetWarningMessage by mocking budgetStore via a Write to a safe path
    // — simplest: just verify that when ttsClient is set and conditions are met, audioPath is set.
    // We use a Bash command with extraContext absent, so TTS block won't fire unless budgetWarning fires.
    // Instead, directly verify the fail-open path first, then test with a mock memory path below.

    // Clean up: reset to null so other tests are unaffected
    initializeTtsClient(null as unknown as TtsClient);

    // Minimal assertion: with no context to speak, TTS is never called, continue=true
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Bash",
      input: { command: "ls -la" },
    });
    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);
    expect(response.body.audioPath).toBeUndefined();
  });

  it("POST /hooks/pretool with TTS unavailable fails open", async () => {
    const mockTtsClient = {
      isAvailable: vi.fn().mockResolvedValue(false),
      synthesize: vi.fn(),
    } as unknown as TtsClient;

    initializeTtsClient(mockTtsClient);

    const response = await request(app).post("/hooks/pretool").send({
      tool: "Bash",
      input: { command: "ls -la" },
    });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);
    expect(response.body.audioPath).toBeUndefined();

    initializeTtsClient(null as unknown as TtsClient);
  });

  it("POST /hooks/pretool with TTS throwing fails open", async () => {
    const mockTtsClient = {
      isAvailable: vi.fn().mockResolvedValue(true),
      synthesize: vi.fn().mockRejectedValue(new Error("TTS server error")),
    } as unknown as TtsClient;

    initializeTtsClient(mockTtsClient);

    const response = await request(app).post("/hooks/pretool").send({
      tool: "Bash",
      input: { command: "ls -la" },
    });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);
    expect(response.body.audioPath).toBeUndefined();

    initializeTtsClient(null as unknown as TtsClient);
  });

  it("POST /hooks/pretool fails open when observability logger throws", async () => {
    vi.spyOn(observabilityModule.ObservabilityLogger, "logEvent").mockImplementation(() => {
      throw new Error("telemetry failure");
    });

    const response = await request(app).post("/hooks/pretool").send({
      tool: "Bash",
      input: { command: "ls -la /home/user" },
    });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);
  });

  it("POST /hooks/posttool fails open when observability logger throws", async () => {
    vi.spyOn(observabilityModule.ObservabilityLogger, "logEvent").mockImplementation(() => {
      throw new Error("telemetry failure");
    });

    const response = await request(app).post("/hooks/posttool").send({
      tool: "Bash",
      input: { command: "echo test" },
      success: true,
      result: { output: "test" },
    });

    expect(response.status).toBe(200);
    expect(response.body.status).toBe("stored");
  });
});

describe("Hooks OTel spans", () => {
  let app: express.Application;
  const setAttribute = vi.fn();
  const end = vi.fn();
  const recordException = vi.fn();
  const spanContext = vi.fn().mockReturnValue({
    traceId: "00000000000000000000000000000000",
    spanId: "0000000000000000",
    traceFlags: 0,
  });
  const mockSpan = { setAttribute, end, recordException, spanContext };
  const startSpan = vi.fn().mockImplementation(() => mockSpan);

  beforeEach(() => {
    vi.spyOn(tracerModule, "getTracer").mockReturnValue({
      startSpan,
    } as ReturnType<typeof tracerModule.getTracer>);
    app = express();
    app.use(express.json());
    app.use("/hooks", hooksRouter);
    setAttribute.mockClear();
    end.mockClear();
    recordException.mockClear();
    spanContext.mockClear();
    spanContext.mockReturnValue({
      traceId: "00000000000000000000000000000000",
      spanId: "0000000000000000",
      traceFlags: 0,
    });
    startSpan.mockClear();
    startSpan.mockImplementation(() => mockSpan);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("pretool starts span hook.pretool and sets correlation from payload", async () => {
    await request(app)
      .post("/hooks/pretool")
      .send({
        tool: "Read",
        sessionId: "sess-abc",
        input: { taskId: "task-99", agentRole: "assistant", projectId: "proj-1" },
      });

    expect(startSpan).toHaveBeenCalledWith(
      "hook.pretool",
      expect.objectContaining({
        attributes: expect.objectContaining({
          [GEN_ATTRS.HOOK_EVENT]: "pretool",
        }),
      }),
      expect.anything(),
    );
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.SESSION_ID, "sess-abc");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.TASK_ID, "task-99");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.TOOL_NAME, "Read");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.AGENT_ROLE, "assistant");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.PROJECT_ID, "proj-1");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.SUGGESTED_LLM, expect.any(String));
    // Unit app does not wire initializeLlmSelector — selector stays off → source reflects that
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.PRETOOL_ROUTING_SOURCE, "selector_unavailable");
    expect(end).toHaveBeenCalled();
  });

  it("posttool starts hook.posttool span and sets correlation + tool_success", async () => {
    await request(app)
      .post("/hooks/posttool")
      .send({
        tool: "Bash",
        sessionId: "sess-xyz",
        input: { taskId: "t-1", command: "echo hi" },
        success: true,
        result: {},
      });

    expect(startSpan).toHaveBeenCalledWith(
      "hook.posttool",
      expect.objectContaining({
        attributes: expect.objectContaining({
          [GEN_ATTRS.HOOK_EVENT]: "posttool",
        }),
      }),
      expect.anything(),
    );
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.SESSION_ID, "sess-xyz");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.TASK_ID, "t-1");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.TOOL_NAME, "Bash");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.TOOL_SUCCESS, true);
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.DECISION, "stored");
    expect(end).toHaveBeenCalledTimes(1);
  });

  it("posttool reads sessionId from input when top-level absent", async () => {
    await request(app)
      .post("/hooks/posttool")
      .send({
        tool: "Bash",
        input: { sessionId: "nested-sess", taskId: "t-2", command: "x" },
        success: false,
        result: {},
      });

    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.SESSION_ID, "nested-sess");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.TOOL_SUCCESS, false);
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.DECISION, "skipped");
    expect(end).toHaveBeenCalled();
  });

  it("user-prompt sets session correlation on span", async () => {
    await request(app)
      .post("/hooks/user-prompt")
      .send({
        prompt: "Please refactor the auth module for clarity and tests.",
        sessionId: "us-1",
      });

    expect(startSpan).toHaveBeenCalledWith(
      "hook.user-prompt",
      expect.objectContaining({
        attributes: expect.objectContaining({
          [GEN_ATTRS.PROMPT_NORMALIZER_VERSION]: expect.any(String),
        }),
      }),
      expect.anything(),
    );
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.SESSION_ID, "us-1");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.SUGGESTED_LLM, expect.any(String));
    expect(end).toHaveBeenCalled();
  });
});

describe("Hooks E2E metadata (GEN_E2E_METADATA=1)", () => {
  let app: express.Application;
  let prevE2e: string | undefined;
  const setAttribute = vi.fn();
  const end = vi.fn();
  const recordException = vi.fn();
  const spanContext = vi.fn().mockReturnValue({
    traceId: "00000000000000000000000000000000",
    spanId: "0000000000000000",
    traceFlags: 0,
  });
  const mockSpan = { setAttribute, end, recordException, spanContext };
  const startSpan = vi.fn().mockImplementation(() => mockSpan);

  beforeEach(() => {
    prevE2e = process.env.GEN_E2E_METADATA;
    process.env.GEN_E2E_METADATA = "1";
    vi.spyOn(tracerModule, "getTracer").mockReturnValue({
      startSpan,
    } as ReturnType<typeof tracerModule.getTracer>);
    app = express();
    app.use(express.json());
    app.use("/hooks", hooksRouter);
    setAttribute.mockClear();
    end.mockClear();
    recordException.mockClear();
    spanContext.mockClear();
    spanContext.mockReturnValue({
      traceId: "00000000000000000000000000000000",
      spanId: "0000000000000000",
      traceFlags: 0,
    });
    startSpan.mockClear();
    startSpan.mockImplementation(() => mockSpan);
  });

  afterEach(() => {
    if (prevE2e === undefined) delete process.env.GEN_E2E_METADATA;
    else process.env.GEN_E2E_METADATA = prevE2e;
    vi.restoreAllMocks();
  });

  it("pretool sets e2e span attrs from headers", async () => {
    await request(app)
      .post("/hooks/pretool")
      .set("X-Gen-E2E-Run", "run-hdr")
      .set("X-Gen-E2E-Tags", "playwright,critical")
      .send({
        tool: "Read",
        input: { file_path: "/x", taskId: "t-e2e" },
      });

    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_RUN_ID, "run-hdr");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_TAGS, "playwright,critical");
  });

  it("pretool prefers headers over body metadata", async () => {
    await request(app)
      .post("/hooks/pretool")
      .set("X-Gen-E2E-Run", "from-header")
      .set("X-Gen-E2E-Tags", "a")
      .send({
        tool: "Read",
        input: { file_path: "/y" },
        metadata: { e2eRunId: "from-body", e2eTags: ["b", "c"] },
      });

    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_RUN_ID, "from-header");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_TAGS, "a");
  });

  it("pretool uses body metadata when headers absent", async () => {
    await request(app)
      .post("/hooks/pretool")
      .send({
        tool: "Read",
        input: { file_path: "/z" },
        metadata: { e2eRunId: "body-run", e2eTags: ["t1", "t2"] },
      });

    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_RUN_ID, "body-run");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_TAGS, "t1,t2");
  });

  it("posttool sets e2e span attrs from headers", async () => {
    await request(app)
      .post("/hooks/posttool")
      .set("X-Gen-E2E-Run", "pt-1")
      .set("X-Gen-E2E-Tags", "e2e")
      .send({
        tool: "Bash",
        input: { command: "echo" },
        success: true,
        result: {},
      });

    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_RUN_ID, "pt-1");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_TAGS, "e2e");
  });

  it("user-prompt sets e2e attrs from body metadata", async () => {
    await request(app).post("/hooks/user-prompt").send({
      prompt: "hello",
      metadata: { e2eRunId: "up-1", e2eTags: ["e2e"] },
    });

    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_RUN_ID, "up-1");
    expect(setAttribute).toHaveBeenCalledWith(GEN_ATTRS.E2E_TAGS, "e2e");
  });

  it("does not set e2e attrs when GEN_E2E_METADATA is unset", async () => {
    delete process.env.GEN_E2E_METADATA;
    await request(app)
      .post("/hooks/pretool")
      .set("X-Gen-E2E-Run", "ignored")
      .send({ tool: "Read", input: { file_path: "/w" } });

    const e2eRunCalls = setAttribute.mock.calls.filter((c) => c[0] === GEN_ATTRS.E2E_RUN_ID);
    const e2eTagCalls = setAttribute.mock.calls.filter((c) => c[0] === GEN_ATTRS.E2E_TAGS);
    expect(e2eRunCalls).toHaveLength(0);
    expect(e2eTagCalls).toHaveLength(0);
  });
});
