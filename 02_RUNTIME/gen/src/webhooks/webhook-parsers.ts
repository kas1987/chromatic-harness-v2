import type { ParsedWebhookEvent } from "./webhook-types";

export function parseGitHubWebhook(
  eventType: string,
  payload: Record<string, unknown>
): ParsedWebhookEvent {
  const repo =
    (payload.repository as Record<string, unknown> | undefined)?.full_name ??
    "unknown";

  if (eventType === "push") {
    const ref = (payload.ref as string | undefined) ?? "";
    const branch = ref.startsWith("refs/heads/") ? ref.slice(11) : ref;
    return {
      source: "github",
      eventType,
      title: `Push to ${repo} on ${branch}`,
      severity: "info",
      triggerTask: false,
    };
  }

  if (eventType === "pull_request") {
    const action = payload.action as string | undefined;
    const pr = payload.pull_request as Record<string, unknown> | undefined;
    const number = pr?.number ?? "?";
    const prTitle = (pr?.title as string | undefined) ?? "";
    const merged = pr?.merged as boolean | undefined;

    if (action === "opened" || action === "reopened") {
      return {
        source: "github",
        eventType,
        title: `PR #${number}: ${prTitle}`,
        severity: "info",
        triggerTask: true,
        taskDescription: `Review PR #${number}: ${prTitle}`,
      };
    }

    if (action === "closed" && merged === true) {
      return {
        source: "github",
        eventType,
        title: `PR #${number} merged`,
        severity: "info",
        triggerTask: false,
      };
    }
  }

  if (eventType === "workflow_run") {
    const conclusion = payload.conclusion as string | undefined;
    const workflow =
      (payload.workflow_run as Record<string, unknown> | undefined)?.name ??
      (payload.name as string | undefined) ??
      "unknown";

    if (conclusion === "failure") {
      return {
        source: "github",
        eventType,
        title: `CI failed: ${workflow}`,
        severity: "error",
        triggerTask: true,
        taskDescription: `Investigate CI failure: ${workflow}`,
      };
    }
  }

  return {
    source: "github",
    eventType,
    title: `GitHub ${eventType}`,
    severity: "info",
    triggerTask: false,
  };
}

export function parseCIWebhook(
  payload: Record<string, unknown>
): ParsedWebhookEvent {
  const status = payload.status as string | undefined;
  const job = (payload.job as string | undefined) ?? "unknown";

  if (status === "success") {
    return {
      source: "ci",
      eventType: "build",
      title: `Build passed: ${job}`,
      severity: "info",
      triggerTask: false,
    };
  }

  if (status === "failure") {
    return {
      source: "ci",
      eventType: "build",
      title: `Build failed: ${job}`,
      severity: "error",
      triggerTask: true,
      taskDescription: `Investigate build failure: ${job}`,
    };
  }

  return {
    source: "ci",
    eventType: "build",
    title: "CI event",
    severity: "info",
    triggerTask: false,
  };
}

export function parseSlackWebhook(
  payload: Record<string, unknown>
): ParsedWebhookEvent {
  const text = (payload.text as string | undefined) ?? "";
  const channel = (payload.channel as string | undefined) ?? "unknown";

  const lower = text.toLowerCase();
  if (lower.includes("urgent") || lower.includes("critical")) {
    const truncated = text.length > 100 ? text.slice(0, 100) : text;
    return {
      source: "slack",
      eventType: "message",
      title: `Urgent Slack message in #${channel}`,
      severity: "warn",
      triggerTask: true,
      taskDescription: `Urgent Slack message: ${truncated}`,
    };
  }

  return {
    source: "slack",
    eventType: "message",
    title: `Slack message in #${channel}`,
    severity: "info",
    triggerTask: false,
  };
}

export function parseGenericWebhook(
  payload: Record<string, unknown>
): ParsedWebhookEvent {
  const source = (payload.source as string | undefined) ?? "unknown";
  return {
    source: "generic",
    eventType: "generic",
    title: `Webhook from ${source}`,
    severity: "info",
    triggerTask: false,
  };
}
