import Database from "better-sqlite3";
import { randomUUID } from "crypto";
import type { WebhookEvent, WebhookSource } from "./webhook-types";

export class WebhookStore {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
    this.initialize();
  }

  private initialize(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS webhook_events (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        received_at TEXT NOT NULL,
        processed INTEGER DEFAULT 0,
        task_created TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_webhook_events_source ON webhook_events(source);
      CREATE INDEX IF NOT EXISTS idx_webhook_events_received ON webhook_events(received_at);
    `);
  }

  recordEvent(event: Omit<WebhookEvent, "id" | "receivedAt">): WebhookEvent {
    const id = randomUUID();
    const receivedAt = new Date().toISOString();

    this.db
      .prepare(
        `INSERT INTO webhook_events (id, source, event_type, payload, received_at, processed, task_created)
         VALUES (?, ?, ?, ?, ?, ?, ?)`
      )
      .run(
        id,
        event.source,
        event.eventType,
        JSON.stringify(event.payload),
        receivedAt,
        event.processed ? 1 : 0,
        event.taskCreated ?? null
      );

    return { ...event, id, receivedAt };
  }

  markProcessed(id: string, taskCreated?: string): void {
    this.db
      .prepare(
        `UPDATE webhook_events SET processed = 1, task_created = ? WHERE id = ?`
      )
      .run(taskCreated ?? null, id);
  }

  getRecentEvents(source?: WebhookSource, limit = 50): WebhookEvent[] {
    let rows: any[];
    if (source) {
      rows = this.db
        .prepare(
          `SELECT * FROM webhook_events WHERE source = ? ORDER BY received_at DESC LIMIT ?`
        )
        .all(source, limit);
    } else {
      rows = this.db
        .prepare(
          `SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT ?`
        )
        .all(limit);
    }
    return rows.map(this.rowToEvent);
  }

  getUnprocessed(limit = 100): WebhookEvent[] {
    const rows = this.db
      .prepare(
        `SELECT * FROM webhook_events WHERE processed = 0 ORDER BY received_at ASC LIMIT ?`
      )
      .all(limit) as any[];
    return rows.map(this.rowToEvent);
  }

  private rowToEvent(row: any): WebhookEvent {
    return {
      id: row.id,
      source: row.source as WebhookSource,
      eventType: row.event_type,
      payload: JSON.parse(row.payload) as Record<string, unknown>,
      receivedAt: row.received_at,
      processed: row.processed === 1,
      taskCreated: row.task_created ?? undefined,
    };
  }
}
