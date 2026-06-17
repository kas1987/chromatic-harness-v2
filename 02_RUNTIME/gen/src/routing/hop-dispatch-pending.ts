/**
 * Session-scoped lines from async dispatch workers, drained at the next user-prompt.
 * Workers POST /hooks/dispatch-outcome; Claude sees [DISPATCH UPDATES] on the following message.
 */

import { randomUUID } from "crypto";

const TTL_MS = 30 * 60 * 1000; // 30 minutes
const MAX_LINES_PER_SESSION = 32;
const MAX_LINE_LEN = 2000;

interface Entry {
  lines: string[];
  expiresAt: number;
}

interface IssuedHop {
  nonce: string;
  expiresAt: number;
}

class HopDispatchPendingStore {
  private store = new Map<string, Entry>();
  private issuedHops = new Map<string, IssuedHop>();

  private hopKey(sessionId: string, hopId: string): string {
    return `${sessionId}::${hopId}`;
  }

  private evictStale(): void {
    const now = Date.now();
    for (const [key, e] of this.store) {
      if (e.expiresAt <= now) this.store.delete(key);
    }
    for (const [key, e] of this.issuedHops) {
      if (e.expiresAt <= now) this.issuedHops.delete(key);
    }
  }

  issueOutcomeToken(sessionId: string, hopId: string): string | null {
    const cleanSession = sessionId.trim();
    const cleanHop = hopId.trim();
    if (!cleanSession || !cleanHop) return null;

    this.evictStale();
    const nonce = randomUUID();
    this.issuedHops.set(this.hopKey(cleanSession, cleanHop), {
      nonce,
      expiresAt: Date.now() + TTL_MS,
    });
    return nonce;
  }

  consumeOutcomeToken(sessionId: string, hopId: string, nonce: string): boolean {
    const cleanSession = sessionId.trim();
    const cleanHop = hopId.trim();
    const cleanNonce = nonce.trim();
    if (!cleanSession || !cleanHop || !cleanNonce) return false;

    this.evictStale();
    const key = this.hopKey(cleanSession, cleanHop);
    const entry = this.issuedHops.get(key);
    if (!entry) return false;
    if (entry.expiresAt <= Date.now()) {
      this.issuedHops.delete(key);
      return false;
    }
    const ok = entry.nonce === cleanNonce;
    if (ok) this.issuedHops.delete(key);
    return ok;
  }

  formatUntrustedStatusLine(hopId: string, status: string, summary?: string): string {
    const cleanHop = hopId.trim().slice(0, 128).replace(/\s+/g, " ");
    const cleanStatus = status.trim().slice(0, 128).replace(/\s+/g, " ");
    const cleanSummary = (summary ?? "").replace(/[\r\n\t]/g, " ").replace(/\s+/g, " ").trim().slice(0, 1200);
    const payload = cleanSummary
      ? { hop_id: cleanHop, status: cleanStatus, summary: cleanSummary }
      : { hop_id: cleanHop, status: cleanStatus };
    return JSON.stringify(payload);
  }

  enqueue(sessionId: string, line: string): void {
    if (!sessionId.trim()) return;
    const trimmed = line.trim().slice(0, MAX_LINE_LEN);
    if (!trimmed) return;

    this.evictStale();
    const now = Date.now();
    let entry = this.store.get(sessionId);
    if (!entry || entry.expiresAt <= now) {
      entry = { lines: [], expiresAt: now + TTL_MS };
      this.store.set(sessionId, entry);
    }
    entry.lines.push(trimmed);
    if (entry.lines.length > MAX_LINES_PER_SESSION) {
      entry.lines.splice(0, entry.lines.length - MAX_LINES_PER_SESSION);
    }
    entry.expiresAt = now + TTL_MS;
  }

  /** Return pending lines and clear the queue for this session. */
  drain(sessionId: string): string[] {
    if (!sessionId.trim()) return [];
    this.evictStale();
    const entry = this.store.get(sessionId);
    if (!entry || entry.expiresAt <= Date.now()) {
      if (entry) this.store.delete(sessionId);
      return [];
    }
    this.store.delete(sessionId);
    return [...entry.lines];
  }
}

export const hopDispatchPendingStore = new HopDispatchPendingStore();
