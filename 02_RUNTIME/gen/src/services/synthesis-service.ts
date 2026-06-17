import fs from 'fs';
import path from 'path';
import type { PrismEvent } from '../types/prism-event';

export interface SynthesisBrief {
  windowStart: string;
  windowEnd: string;
  urgent: PrismEvent[];
  actionNeeded: PrismEvent[];
  fyi: PrismEvent[];
  skippedCount: number;
  crossServiceSignals: Array<{ subject: string; sources: string[] }>;
}

export class SynthesisService {
  private outputDir: string;
  private windowHours: number;

  constructor(outputDir: string, windowHours: number = 6) {
    this.outputDir = outputDir;
    this.windowHours = windowHours;
    // pm-005: auto-create output directory on init
    fs.mkdirSync(outputDir, { recursive: true });
  }

  generateBrief(
    events: Array<{ event: PrismEvent; classification: string }>
  ): SynthesisBrief {
    const now = new Date();
    const windowEnd = now.toISOString();

    const allEventObjects = events.map(e => e.event);

    let windowStart: string;
    if (allEventObjects.length > 0) {
      const sorted = [...allEventObjects].sort((a, b) =>
        a.received_at < b.received_at ? -1 : 1
      );
      windowStart = sorted[0].received_at;
    } else {
      windowStart = new Date(now.getTime() - this.windowHours * 60 * 60 * 1000).toISOString();
    }

    const urgent: PrismEvent[] = [];
    const actionNeeded: PrismEvent[] = [];
    const fyi: PrismEvent[] = [];
    let skippedCount = 0;

    for (const { event, classification } of events) {
      switch (classification) {
        case 'urgent':
          urgent.push(event);
          break;
        case 'action-needed':
          actionNeeded.push(event);
          break;
        case 'fyi':
          fyi.push(event);
          break;
        case 'archive':
        default:
          skippedCount++;
          break;
      }
    }

    // Max 5 urgent items
    const trimmedUrgent = urgent.slice(0, 5);

    // Cross-service signals on all non-archived events
    const nonArchived = [...trimmedUrgent, ...actionNeeded, ...fyi];
    const crossServiceSignals = this.detectCrossServiceSignals(nonArchived);

    return {
      windowStart,
      windowEnd,
      urgent: trimmedUrgent,
      actionNeeded,
      fyi,
      skippedCount,
      crossServiceSignals,
    };
  }

  writeBrief(brief: SynthesisBrief): string {
    const dt = new Date(brief.windowEnd);
    const YYYY = dt.getUTCFullYear().toString().padStart(4, '0');
    const MM = (dt.getUTCMonth() + 1).toString().padStart(2, '0');
    const DD = dt.getUTCDate().toString().padStart(2, '0');
    const HH = dt.getUTCHours().toString().padStart(2, '0');

    const filename = `${YYYY}-${MM}-${DD}-${HH}.brief.md`;
    const filePath = path.join(this.outputDir, filename);

    const totalCount =
      brief.urgent.length +
      brief.actionNeeded.length +
      brief.fyi.length +
      brief.skippedCount;

    const lines: string[] = [];

    lines.push(`# Synthesis Brief — ${YYYY}-${MM}-${DD} ${HH}:00`);
    lines.push('');
    lines.push(`**Window:** ${brief.windowStart} → ${brief.windowEnd}`);
    lines.push(`**Events processed:** ${totalCount}`);
    lines.push(`**Archived/skipped:** ${brief.skippedCount}`);
    lines.push('');

    // Urgent
    lines.push(`## Urgent (${brief.urgent.length})`);
    if (brief.urgent.length === 0) {
      lines.push('(none)');
    } else {
      for (const e of brief.urgent) {
        lines.push(`- [${e.source}] ${e.subject}`);
      }
    }
    lines.push('');

    // Actions Needed
    lines.push(`## Actions Needed (${brief.actionNeeded.length})`);
    if (brief.actionNeeded.length === 0) {
      lines.push('(none)');
    } else {
      for (const e of brief.actionNeeded) {
        const urlSuffix = e.url ? ` — ${e.url}` : '';
        lines.push(`- [${e.source}] ${e.subject}${urlSuffix}`);
      }
    }
    lines.push('');

    // FYI — grouped by source
    lines.push(`## FYI (${brief.fyi.length} items)`);
    if (brief.fyi.length === 0) {
      lines.push('(none)');
    } else {
      const bySource = new Map<string, PrismEvent[]>();
      for (const e of brief.fyi) {
        const group = bySource.get(e.source) ?? [];
        group.push(e);
        bySource.set(e.source, group);
      }
      for (const [source, evts] of bySource) {
        lines.push(`### ${source}`);
        for (const e of evts) {
          lines.push(`- ${e.subject}`);
        }
        lines.push('');
      }
    }
    if (brief.fyi.length > 0) {
      // already pushed blank lines per group; ensure section separator
    } else {
      lines.push('');
    }

    // Cross-Service Signals
    lines.push('## Cross-Service Signals');
    if (brief.crossServiceSignals.length === 0) {
      lines.push('(none)');
    } else {
      for (const signal of brief.crossServiceSignals) {
        lines.push(`- "${signal.subject}" seen in: ${signal.sources.join(', ')}`);
      }
    }
    lines.push('');

    // Skipped
    lines.push('## Skipped (archive)');
    lines.push(`${brief.skippedCount} items archived/filtered`);
    lines.push('');

    fs.writeFileSync(filePath, lines.join('\n'), 'utf8');
    return filePath;
  }

  private detectCrossServiceSignals(
    events: PrismEvent[]
  ): Array<{ subject: string; sources: string[] }> {
    const subjectMap = new Map<string, Set<string>>();

    for (const e of events) {
      const key = e.subject.toLowerCase().trim();
      const sources = subjectMap.get(key) ?? new Set<string>();
      sources.add(e.source);
      subjectMap.set(key, sources);
    }

    const signals: Array<{ subject: string; sources: string[] }> = [];
    for (const [subject, sources] of subjectMap) {
      if (sources.size >= 2) {
        signals.push({ subject, sources: Array.from(sources) });
      }
    }

    return signals;
  }
}
