import Database from "better-sqlite3";
import { WebhookStore } from "../webhooks/webhook-store";
import { ChannelBroadcaster } from "../channels/channel-broadcaster";
import {
  webhooksRouter,
  initializeWebhookStore,
} from "./webhooks";
import {
  channelsRouter,
  initializeChannelBroadcaster,
} from "./channels";

export { webhooksRouter } from "./webhooks";
export { channelsRouter } from "./channels";
export { initializeWebhookStore } from "./webhooks";
export { initializeChannelBroadcaster } from "./channels";

export function createWebhookChannelServices(db: Database.Database): {
  webhookStore: WebhookStore;
  broadcaster: ChannelBroadcaster;
} {
  const webhookStore = new WebhookStore(db);
  const broadcaster = new ChannelBroadcaster();

  // Wire up the routers
  initializeWebhookStore(webhookStore, broadcaster);
  initializeChannelBroadcaster(broadcaster);

  return { webhookStore, broadcaster };
}
