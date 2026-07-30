import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { EventEmitter } from "events";
import { ComfyEventBridge } from "../../src/core/comfy-event-bridge";
import { ChannelBroadcaster } from "../../src/channels/channel-broadcaster";

// Mock the ws module
vi.mock("ws", () => {
  const MockWS = vi.fn(function () {
    const emitter = new EventEmitter();
    (emitter as any).removeAllListeners = emitter.removeAllListeners.bind(emitter);
    (emitter as any).close = vi.fn();
    return emitter;
  });
  return { default: MockWS };
});

import WebSocket from "ws";

function makeBroadcaster(): ChannelBroadcaster {
  const bc = new ChannelBroadcaster();
  vi.spyOn(bc, "broadcast");
  vi.spyOn(bc, "makeChannelEvent").mockImplementation(
    (channelId, eventType, payload) => ({
      id: "test-id",
      channelId,
      eventType,
      payload,
      sentAt: new Date().toISOString(),
      source: "internal" as const,
    })
  );
  return bc;
}

describe("ComfyEventBridge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("routes job events to comfyui-jobs channel", () => {
    const bc = makeBroadcaster();
    const bridge = new ComfyEventBridge("ws://127.0.0.1:8188/ws", bc);
    bridge.start();

    const ws = (WebSocket as unknown as ReturnType<typeof vi.fn>).mock.results[0].value;
    ws.emit("message", JSON.stringify({ type: "execution_start", data: { prompt_id: "abc" } }), false);

    expect(bc.makeChannelEvent).toHaveBeenCalledWith(
      "comfyui-jobs",
      "execution_start",
      { job_id: "abc", prompt_id: "abc" },
      "internal"
    );
    expect(bc.broadcast).toHaveBeenCalledWith("comfyui-jobs", expect.any(Object));

    bridge.stop();
  });

  it("routes status events to comfyui-queue channel", () => {
    const bc = makeBroadcaster();
    const bridge = new ComfyEventBridge("ws://127.0.0.1:8188/ws", bc);
    bridge.start();

    const ws = (WebSocket as unknown as ReturnType<typeof vi.fn>).mock.results[0].value;
    ws.emit("message", JSON.stringify({ type: "status", data: { exec_info: { queue_remaining: 3 } } }), false);

    expect(bc.makeChannelEvent).toHaveBeenCalledWith(
      "comfyui-queue",
      "status",
      { job_id: "", exec_info: { queue_remaining: 3 } },
      "internal"
    );
    expect(bc.broadcast).toHaveBeenCalledWith("comfyui-queue", expect.any(Object));

    bridge.stop();
  });

  it("skips binary frames without calling broadcaster", () => {
    const bc = makeBroadcaster();
    const bridge = new ComfyEventBridge("ws://127.0.0.1:8188/ws", bc);
    bridge.start();

    const ws = (WebSocket as unknown as ReturnType<typeof vi.fn>).mock.results[0].value;
    ws.emit("message", Buffer.from([0xff, 0xd8, 0xff]), true); // JPEG-like binary

    expect(bc.broadcast).not.toHaveBeenCalled();

    bridge.stop();
  });

  it("reconnects after WS close when not stopped", () => {
    vi.useFakeTimers();
    const bc = makeBroadcaster();
    const bridge = new ComfyEventBridge("ws://127.0.0.1:8188/ws", bc);
    bridge.start();

    const firstCallCount = (WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length;
    const ws = (WebSocket as unknown as ReturnType<typeof vi.fn>).mock.results[0].value;
    ws.emit("close");

    vi.advanceTimersByTime(2000);

    expect((WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBe(firstCallCount + 1);

    bridge.stop();
  });

  it("does not reconnect after stop()", () => {
    vi.useFakeTimers();
    const bc = makeBroadcaster();
    const bridge = new ComfyEventBridge("ws://127.0.0.1:8188/ws", bc);
    bridge.start();

    const callsBefore = (WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length;
    bridge.stop();

    // Simulate close event after stop
    const ws = (WebSocket as unknown as ReturnType<typeof vi.fn>).mock.results[0].value;
    ws.emit("close");

    vi.advanceTimersByTime(5000);

    expect((WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBe(callsBefore);
  });
});
