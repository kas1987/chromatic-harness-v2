import { Router, Request, Response } from 'express';
import type { PrismEvent } from '../types/prism-event';
import type { EventStore } from '../services/event-store';
import type { OllamaTriage } from '../ollama/ollama-triage';
import type { ActionExecutor } from '../services/action-executor';

export { PrismEvent };  // re-export for consumers

export const ingestRouter = Router();

const VALID_SOURCES = new Set([
  'gmail','gcal','slack','discord','linear','github','substack'
]);

let eventStore: EventStore | null = null;
let ollamaTriage: OllamaTriage | null = null;
let actionExecutor: ActionExecutor | null = null;

export function initializeIngestRouter(
  store: EventStore,
  triage: OllamaTriage | null,
  executor: ActionExecutor,
): void {
  eventStore = store;
  ollamaTriage = triage;
  actionExecutor = executor;
}

function validateEvent(evt: unknown): evt is PrismEvent {
  if (!evt || typeof evt !== 'object') return false;
  const e = evt as Record<string, unknown>;
  return (
    typeof e.source === 'string' && VALID_SOURCES.has(e.source) &&
    typeof e.subject === 'string' && e.subject.length > 0 &&
    typeof e.body_text === 'string'
  );
}

// POST /ingest — accepts PrismEvent | PrismEvent[]
ingestRouter.post('/', async (req: Request, res: Response) => {
  if (!eventStore) {
    return res.status(503).json({ error: 'EventStore not initialized' });
  }
  const raw: unknown[] = Array.isArray(req.body) ? req.body : [req.body];
  for (const evt of raw) {
    if (!validateEvent(evt)) {
      return res.status(400).json({
        error: `Invalid event: source must be one of [${[...VALID_SOURCES].join(', ')}] and subject/body_text are required`,
      });
    }
  }

  const events = raw as PrismEvent[];
  const classified: Record<string, number> = { urgent: 0, 'action-needed': 0, fyi: 0, archive: 0 };
  let ingested = 0;

  for (const event of events) {
    let classification = 'fyi';
    if (ollamaTriage) {
      try {
        const result = await ollamaTriage.classifyEvent(event);
        classification = result.intent;
      } catch {
        // fail open — store as fyi
      }
    }
    eventStore.insert(event, classification);
    classified[classification] = (classified[classification] ?? 0) + 1;
    ingested++;
  }

  void actionExecutor; // used in Wave 3

  return res.json({ ingested, classified });
});

// GET /ingest/health
ingestRouter.get('/health', (_req: Request, res: Response) => {
  if (!eventStore) {
    return res.status(503).json({ status: 'not_initialized' });
  }
  return res.json({ status: 'ok', events_stored: eventStore.count() });
});
