export type WebhookSource = "github" | "ci" | "slack" | "generic";

export interface WebhookEvent {
  id: string;
  source: WebhookSource;
  eventType: string;
  payload: Record<string, unknown>;
  receivedAt: string;
  processed: boolean;
  taskCreated?: string;
}

export interface ParsedWebhookEvent {
  source: WebhookSource;
  eventType: string;
  title: string;
  severity: "info" | "warn" | "error";
  projectId?: string;
  triggerTask: boolean;
  taskDescription?: string;
}
