import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { sessionRoutingStore } from "../session-routing-store.js";

describe("SessionRoutingStore", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("set() and get() round-trip returns stored hint", () => {
    sessionRoutingStore.set("sess-1", "ollama", "explore", "simple");
    const hint = sessionRoutingStore.get("sess-1");
    expect(hint).not.toBeNull();
    expect(hint!.provider).toBe("ollama");
    expect(hint!.intent).toBe("explore");
    expect(hint!.scope).toBe("simple");
  });

  it("get() returns null for unknown sessionId", () => {
    const hint = sessionRoutingStore.get("unknown-session-xyz");
    expect(hint).toBeNull();
  });

  it("expired entries return null", () => {
    sessionRoutingStore.set("sess-expire", "claude", "code", "medium");

    // Advance time past 5-minute TTL
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);

    const hint = sessionRoutingStore.get("sess-expire");
    expect(hint).toBeNull();
  });

  it("entry within TTL is still valid", () => {
    sessionRoutingStore.set("sess-valid", "claude", "code", "complex");

    // Advance time to just before expiry
    vi.advanceTimersByTime(5 * 60 * 1000 - 1000);

    const hint = sessionRoutingStore.get("sess-valid");
    expect(hint).not.toBeNull();
    expect(hint!.provider).toBe("claude");
  });

  it("eviction happens on set() — expired entries are removed", () => {
    sessionRoutingStore.set("sess-old", "ollama", "status", "simple");

    // Advance past TTL
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);

    // Trigger eviction by setting a new entry
    sessionRoutingStore.set("sess-new", "claude", "code", "medium");

    // The expired entry should be gone (evicted)
    const oldHint = sessionRoutingStore.get("sess-old");
    expect(oldHint).toBeNull();

    // The new entry should be accessible
    const newHint = sessionRoutingStore.get("sess-new");
    expect(newHint).not.toBeNull();
    expect(newHint!.provider).toBe("claude");
  });

  it("overwriting a sessionId updates the stored hint", () => {
    sessionRoutingStore.set("sess-overwrite", "ollama", "explore", "simple");
    sessionRoutingStore.set("sess-overwrite", "claude", "code", "complex");

    const hint = sessionRoutingStore.get("sess-overwrite");
    expect(hint).not.toBeNull();
    expect(hint!.provider).toBe("claude");
    expect(hint!.intent).toBe("code");
    expect(hint!.scope).toBe("complex");
  });
});
