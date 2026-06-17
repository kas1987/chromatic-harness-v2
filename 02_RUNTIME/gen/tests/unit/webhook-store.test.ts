import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { WebhookStore } from "../../src/webhooks/webhook-store";

function makeDb(): Database.Database {
  return new Database(":memory:");
}

describe("WebhookStore", () => {
  let db: Database.Database;
  let store: WebhookStore;

  beforeEach(() => {
    db = makeDb();
    store = new WebhookStore(db);
  });

  describe("recordEvent", () => {
    it("creates record with auto-generated id and receivedAt", () => {
      const event = store.recordEvent({
        source: "github",
        eventType: "push",
        payload: { ref: "refs/heads/main" },
        processed: false,
      });

      expect(event.id).toBeTruthy();
      expect(typeof event.id).toBe("string");
      expect(event.receivedAt).toBeTruthy();
      expect(event.source).toBe("github");
      expect(event.eventType).toBe("push");
      expect(event.processed).toBe(false);
    });

    it("stores payload correctly", () => {
      const payload = { foo: "bar", nested: { x: 1 } };
      const event = store.recordEvent({
        source: "ci",
        eventType: "build",
        payload,
        processed: false,
      });

      const retrieved = store.getRecentEvents("ci", 1);
      expect(retrieved[0].payload).toEqual(payload);
    });

    it("generates unique ids for each event", () => {
      const e1 = store.recordEvent({ source: "github", eventType: "push", payload: {}, processed: false });
      const e2 = store.recordEvent({ source: "github", eventType: "push", payload: {}, processed: false });
      expect(e1.id).not.toBe(e2.id);
    });
  });

  describe("getRecentEvents", () => {
    beforeEach(() => {
      store.recordEvent({ source: "github", eventType: "push", payload: {}, processed: false });
      store.recordEvent({ source: "github", eventType: "pull_request", payload: {}, processed: false });
      store.recordEvent({ source: "ci", eventType: "build", payload: {}, processed: false });
      store.recordEvent({ source: "slack", eventType: "message", payload: {}, processed: false });
    });

    it("returns all events when no source filter given", () => {
      const events = store.getRecentEvents(undefined, 100);
      expect(events.length).toBe(4);
    });

    it("filters by source", () => {
      const githubEvents = store.getRecentEvents("github", 100);
      expect(githubEvents.length).toBe(2);
      expect(githubEvents.every((e) => e.source === "github")).toBe(true);
    });

    it("filters ci events separately", () => {
      const ciEvents = store.getRecentEvents("ci", 100);
      expect(ciEvents.length).toBe(1);
      expect(ciEvents[0].source).toBe("ci");
    });

    it("respects limit parameter", () => {
      const limited = store.getRecentEvents(undefined, 2);
      expect(limited.length).toBe(2);
    });

    it("returns events in reverse chronological order (most recent first)", () => {
      const events = store.getRecentEvents(undefined, 100);
      for (let i = 1; i < events.length; i++) {
        expect(events[i - 1].receivedAt >= events[i].receivedAt).toBe(true);
      }
    });
  });

  describe("markProcessed", () => {
    it("sets processed=true and leaves taskCreated undefined when not provided", () => {
      const event = store.recordEvent({
        source: "github",
        eventType: "push",
        payload: {},
        processed: false,
      });

      store.markProcessed(event.id);

      const events = store.getRecentEvents("github", 1);
      expect(events[0].processed).toBe(true);
      expect(events[0].taskCreated).toBeUndefined();
    });

    it("sets processed=true and stores taskCreated when provided", () => {
      const event = store.recordEvent({
        source: "github",
        eventType: "pull_request",
        payload: {},
        processed: false,
      });

      store.markProcessed(event.id, "task-abc-123");

      const events = store.getRecentEvents("github", 1);
      expect(events[0].processed).toBe(true);
      expect(events[0].taskCreated).toBe("task-abc-123");
    });
  });

  describe("getUnprocessed", () => {
    it("returns only unprocessed events", () => {
      const e1 = store.recordEvent({ source: "github", eventType: "push", payload: {}, processed: false });
      const e2 = store.recordEvent({ source: "ci", eventType: "build", payload: {}, processed: false });
      store.recordEvent({ source: "slack", eventType: "message", payload: {}, processed: false });

      store.markProcessed(e1.id);
      store.markProcessed(e2.id, "task-99");

      const unprocessed = store.getUnprocessed(100);
      expect(unprocessed.length).toBe(1);
      expect(unprocessed[0].source).toBe("slack");
    });

    it("returns empty array when all processed", () => {
      const e = store.recordEvent({ source: "github", eventType: "push", payload: {}, processed: false });
      store.markProcessed(e.id);
      expect(store.getUnprocessed()).toHaveLength(0);
    });

    it("returns empty array when no events exist", () => {
      expect(store.getUnprocessed()).toHaveLength(0);
    });

    it("respects limit parameter", () => {
      for (let i = 0; i < 5; i++) {
        store.recordEvent({ source: "generic", eventType: "generic", payload: {}, processed: false });
      }
      expect(store.getUnprocessed(3)).toHaveLength(3);
    });
  });
});
