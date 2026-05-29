/**
 * Mission event persistence (JSONL) for WebSocket replay.
 */

import * as fs from 'fs';
import * as path from 'path';
import { EventEmitter } from 'events';
export interface MagnetEventMessage {
  type: 'magnet_event' | 'magnet_synthesis' | 'gate_decision' | 'bead_created' | 'replay_marker';
  mission_id: string;
  timestamp: number;
  data: Record<string, unknown>;
}

function repoRoot(): string {
  let here = path.resolve(__dirname);
  for (let i = 0; i < 10; i++) {
    if (
      fs.existsSync(path.join(here, '00_SOURCE_OF_TRUTH')) ||
      fs.existsSync(path.join(here, '.git'))
    ) {
      return here;
    }
    const parent = path.dirname(here);
    if (parent === here) break;
    here = parent;
  }
  return process.cwd();
}

function safeId(missionId: string): string {
  return missionId.replace(/[^a-zA-Z0-9_-]/g, '_');
}

export class FileEventStore {
  private dir: string;

  constructor(root?: string) {
    const base = root || repoRoot();
    this.dir = path.join(base, '07_LOGS_AND_AUDIT', 'ws_events');
    fs.mkdirSync(this.dir, { recursive: true });
  }

  private filePath(missionId: string): string {
    return path.join(this.dir, `${safeId(missionId)}.jsonl`);
  }

  append(missionId: string, event: MagnetEventMessage): void {
    const line = JSON.stringify(event) + '\n';
    fs.appendFileSync(this.filePath(missionId), line, 'utf-8');
  }

  replay(missionId: string, limit = 100): MagnetEventMessage[] {
    const fp = this.filePath(missionId);
    if (!fs.existsSync(fp)) return [];
    const lines = fs.readFileSync(fp, 'utf-8').split('\n').filter((l) => l.trim());
    const slice = lines.slice(-limit);
    const out: MagnetEventMessage[] = [];
    for (const ln of slice) {
      try {
        out.push(JSON.parse(ln) as MagnetEventMessage);
      } catch {
        /* skip corrupt line */
      }
    }
    return out;
  }
}

export class MissionEventHub {
  private static instance: MissionEventHub;
  private store = new FileEventStore();
  private emitter = new EventEmitter();

  static getInstance(): MissionEventHub {
    if (!MissionEventHub.instance) {
      MissionEventHub.instance = new MissionEventHub();
    }
    return MissionEventHub.instance;
  }

  publish(missionId: string, event: MagnetEventMessage): void {
    this.store.append(missionId, event);
    this.emitter.emit(`mission:${missionId}`, event);
    this.emitter.emit('mission:all', event);
  }

  replay(missionId: string, limit = 100): MagnetEventMessage[] {
    return this.store.replay(missionId, limit);
  }

  onMissionEvent(missionId: string, cb: (event: MagnetEventMessage) => void): void {
    this.emitter.on(`mission:${missionId}`, cb);
  }

  offMissionEvent(missionId: string, cb: (event: MagnetEventMessage) => void): void {
    this.emitter.off(`mission:${missionId}`, cb);
  }

  onAnyEvent(cb: (event: MagnetEventMessage) => void): void {
    this.emitter.on('mission:all', cb);
  }

  offAnyEvent(cb: (event: MagnetEventMessage) => void): void {
    this.emitter.off('mission:all', cb);
  }
}
