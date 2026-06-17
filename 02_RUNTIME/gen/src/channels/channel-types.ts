export interface ChannelEvent {
  id: string;
  channelId: string;
  eventType: string;
  payload: Record<string, unknown>;
  sentAt: string;
  source: "webhook" | "internal" | "admin";
}

export interface Subscriber {
  sessionId: string;
  channelId: string;
  filters?: string[];
  subscribedAt: string;
  lastHeartbeatAt: string;
}
