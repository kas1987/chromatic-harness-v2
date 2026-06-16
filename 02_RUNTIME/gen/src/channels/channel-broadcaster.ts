import { Response } from "express";
import { randomUUID } from "crypto";
import type { ChannelEvent, Subscriber } from "./channel-types";

interface SubscriberEntry {
  res: Response;
  subscriber: Subscriber;
}

export class ChannelBroadcaster {
  private subscribers = new Map<string, SubscriberEntry>();

  subscribe(
    sessionId: string,
    channelId: string,
    filters: string[],
    res: Response
  ): void {
    const now = new Date().toISOString();
    const subscriber: Subscriber = {
      sessionId,
      channelId,
      filters: filters.length > 0 ? filters : [],
      subscribedAt: now,
      lastHeartbeatAt: now,
    };
    this.subscribers.set(sessionId, { res, subscriber });
  }

  unsubscribe(sessionId: string): void {
    this.subscribers.delete(sessionId);
  }

  broadcast(channelId: string, event: ChannelEvent): void {
    const data = this.serializeEvent(event);
    for (const [, entry] of this.subscribers) {
      const { subscriber, res } = entry;
      if (subscriber.channelId !== channelId) continue;
      if (!this.matchesFilters(subscriber, event.eventType)) continue;
      this.writeSSE(res, data);
      subscriber.lastHeartbeatAt = new Date().toISOString();
    }
  }

  broadcastAll(event: ChannelEvent): void {
    const data = this.serializeEvent(event);
    for (const [, entry] of this.subscribers) {
      const { subscriber, res } = entry;
      if (!this.matchesFilters(subscriber, event.eventType)) continue;
      this.writeSSE(res, data);
      subscriber.lastHeartbeatAt = new Date().toISOString();
    }
  }

  getActiveSubscribers(): Subscriber[] {
    return Array.from(this.subscribers.values()).map((e) => e.subscriber);
  }

  pruneStale(maxAgeMs = 5 * 60 * 1000): void {
    const now = Date.now();
    for (const [sessionId, entry] of this.subscribers) {
      const lastBeat = new Date(entry.subscriber.lastHeartbeatAt).getTime();
      if (now - lastBeat > maxAgeMs) {
        this.subscribers.delete(sessionId);
      }
    }
  }

  private matchesFilters(subscriber: Subscriber, eventType: string): boolean {
    if (!subscriber.filters || subscriber.filters.length === 0) return true;
    return subscriber.filters.includes(eventType);
  }

  private serializeEvent(event: ChannelEvent): string {
    return JSON.stringify({
      id: event.id,
      eventType: event.eventType,
      payload: event.payload,
      sentAt: event.sentAt,
    });
  }

  private writeSSE(res: Response, data: string): void {
    try {
      res.write(`data: ${data}\n\n`);
    } catch {
      // Client disconnected — ignore write error
    }
  }

  makeChannelEvent(
    channelId: string,
    eventType: string,
    payload: Record<string, unknown>,
    source: ChannelEvent["source"] = "internal"
  ): ChannelEvent {
    return {
      id: randomUUID(),
      channelId,
      eventType,
      payload,
      sentAt: new Date().toISOString(),
      source,
    };
  }
}
