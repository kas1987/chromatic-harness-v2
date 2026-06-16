import { describe, it, expect } from "vitest";
import {
  parseGitHubWebhook,
  parseCIWebhook,
  parseSlackWebhook,
  parseGenericWebhook,
} from "../../src/webhooks/webhook-parsers";

describe("parseGitHubWebhook", () => {
  it("push event — triggerTask=false", () => {
    const result = parseGitHubWebhook("push", {
      ref: "refs/heads/main",
      repository: { full_name: "acme/repo" },
    });
    expect(result.triggerTask).toBe(false);
    expect(result.severity).toBe("info");
    expect(result.title).toBe("Push to acme/repo on main");
  });

  it("PR opened — triggerTask=true with correct description", () => {
    const result = parseGitHubWebhook("pull_request", {
      action: "opened",
      pull_request: { number: 42, title: "Add feature X", merged: false },
      repository: { full_name: "acme/repo" },
    });
    expect(result.triggerTask).toBe(true);
    expect(result.taskDescription).toBe("Review PR #42: Add feature X");
    expect(result.title).toBe("PR #42: Add feature X");
    expect(result.severity).toBe("info");
  });

  it("PR reopened — triggerTask=true", () => {
    const result = parseGitHubWebhook("pull_request", {
      action: "reopened",
      pull_request: { number: 7, title: "Fix bug", merged: false },
    });
    expect(result.triggerTask).toBe(true);
    expect(result.taskDescription).toBe("Review PR #7: Fix bug");
  });

  it("PR closed + merged — triggerTask=false", () => {
    const result = parseGitHubWebhook("pull_request", {
      action: "closed",
      pull_request: { number: 42, title: "Add feature X", merged: true },
    });
    expect(result.triggerTask).toBe(false);
    expect(result.title).toBe("PR #42 merged");
  });

  it("workflow_run failure — severity=error, triggerTask=true", () => {
    const result = parseGitHubWebhook("workflow_run", {
      conclusion: "failure",
      workflow_run: { name: "CI / Build" },
    });
    expect(result.severity).toBe("error");
    expect(result.triggerTask).toBe(true);
    expect(result.taskDescription).toBe("Investigate CI failure: CI / Build");
    expect(result.title).toBe("CI failed: CI / Build");
  });

  it("workflow_run success — triggerTask=false", () => {
    const result = parseGitHubWebhook("workflow_run", {
      conclusion: "success",
      workflow_run: { name: "CI / Build" },
    });
    expect(result.triggerTask).toBe(false);
  });

  it("unknown event type — returns default info", () => {
    const result = parseGitHubWebhook("release", {});
    expect(result.title).toBe("GitHub release");
    expect(result.severity).toBe("info");
    expect(result.triggerTask).toBe(false);
  });
});

describe("parseCIWebhook", () => {
  it("failure status — triggerTask=true, severity=error", () => {
    const result = parseCIWebhook({ status: "failure", job: "test-suite" });
    expect(result.triggerTask).toBe(true);
    expect(result.severity).toBe("error");
    expect(result.title).toBe("Build failed: test-suite");
    expect(result.taskDescription).toBe(
      "Investigate build failure: test-suite"
    );
  });

  it("success status — triggerTask=false, severity=info", () => {
    const result = parseCIWebhook({ status: "success", job: "test-suite" });
    expect(result.triggerTask).toBe(false);
    expect(result.severity).toBe("info");
    expect(result.title).toBe("Build passed: test-suite");
  });

  it("unknown status — returns generic CI event", () => {
    const result = parseCIWebhook({ status: "pending", job: "build" });
    expect(result.title).toBe("CI event");
    expect(result.triggerTask).toBe(false);
  });
});

describe("parseSlackWebhook", () => {
  it("message containing 'urgent' — triggerTask=true, severity=warn", () => {
    const result = parseSlackWebhook({
      text: "This is urgent! Please fix the server.",
      channel: "incidents",
    });
    expect(result.triggerTask).toBe(true);
    expect(result.severity).toBe("warn");
    expect(result.taskDescription).toContain("Urgent Slack message:");
  });

  it("message containing 'critical' — triggerTask=true", () => {
    const result = parseSlackWebhook({
      text: "critical outage in prod",
      channel: "ops",
    });
    expect(result.triggerTask).toBe(true);
    expect(result.severity).toBe("warn");
  });

  it("normal message — triggerTask=false, severity=info", () => {
    const result = parseSlackWebhook({
      text: "Hey team, standup in 5 minutes",
      channel: "general",
    });
    expect(result.triggerTask).toBe(false);
    expect(result.severity).toBe("info");
    expect(result.title).toBe("Slack message in #general");
  });

  it("urgent text truncated to 100 chars in taskDescription", () => {
    const longText = "urgent " + "x".repeat(200);
    const result = parseSlackWebhook({ text: longText, channel: "test" });
    expect(result.taskDescription).toBeDefined();
    // "Urgent Slack message: " prefix + up to 100 chars of text
    const descBody = result.taskDescription!.slice(
      "Urgent Slack message: ".length
    );
    expect(descBody.length).toBeLessThanOrEqual(100);
  });
});

describe("parseGenericWebhook", () => {
  it("includes source from payload", () => {
    const result = parseGenericWebhook({ source: "my-service" });
    expect(result.title).toBe("Webhook from my-service");
    expect(result.triggerTask).toBe(false);
    expect(result.severity).toBe("info");
  });

  it("falls back to 'unknown' when source absent", () => {
    const result = parseGenericWebhook({});
    expect(result.title).toBe("Webhook from unknown");
  });
});
