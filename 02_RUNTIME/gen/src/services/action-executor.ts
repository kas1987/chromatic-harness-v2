import fs from 'fs';
import path from 'path';
import type { PrismEvent } from '../types/prism-event';

export interface ActionConfig {
  autoArchive: boolean;
  createTasksForActions: boolean;
  tasksOutputPath: string;
}

export interface ActionResult {
  acted: boolean;
  action: 'archived' | 'flagged-urgent' | 'task-created' | 'fyi-logged' | 'none';
  reason: string;
}

export class ActionExecutor {
  constructor(private config: ActionConfig) {}

  execute(event: PrismEvent, classification: string): ActionResult {
    // Rule 1 — archive
    if (classification === 'archive' && this.config.autoArchive) {
      return { acted: true, action: 'archived', reason: 'auto-archive classification' };
    }

    // Rule 2 — urgent
    if (classification === 'urgent') {
      return { acted: true, action: 'flagged-urgent', reason: 'urgent classification — surface in brief' };
    }

    // Rule 3 — action-needed + linear or github
    if (classification === 'action-needed' && (event.source === 'linear' || event.source === 'github')) {
      if (this.config.createTasksForActions) {
        const record = {
          id: event.id,
          source: event.source,
          subject: event.subject,
          url: event.url,
          created_at: new Date().toISOString(),
        };
        fs.mkdirSync(path.dirname(this.config.tasksOutputPath), { recursive: true });
        fs.appendFileSync(this.config.tasksOutputPath, JSON.stringify(record) + '\n');
      }
      return { acted: true, action: 'task-created', reason: 'action-needed from linear/github' };
    }

    // Rule 4 — fyi (default)
    return { acted: false, action: 'fyi-logged', reason: 'fyi — include in next brief' };
  }
}
