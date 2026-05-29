/**
 * Phase 6.5: WebSocket Server for Real-Time Magnet Events
 * 
 * Replaces HTTP polling (5s interval) with instant WebSocket push
 * Frontend subscribes to /ws/missions/:id/events
 * Backend emits magnet reports as they occur
 */

import { WebSocketServer, WebSocket } from 'ws';
import { MagnetEventMessage, MissionEventHub } from './event_store';

export type { MagnetEventMessage } from './event_store';

/**
 * Mission event bus — persists to JSONL and emits locally.
 */
export class MissionEventBus {
  private hub = MissionEventHub.getInstance();

  private static instance: MissionEventBus;

  static getInstance(): MissionEventBus {
    if (!MissionEventBus.instance) {
      MissionEventBus.instance = new MissionEventBus();
    }
    return MissionEventBus.instance;
  }

  private publish(event: MagnetEventMessage) {
    this.hub.publish(event.mission_id, event);
  }

  emitMagnetEvent(missionId: string, magnetType: string, score: number, anomalies: any[]) {
    this.publish({
      type: 'magnet_event',
      mission_id: missionId,
      timestamp: Date.now(),
      data: { magnet_type: magnetType, score, anomalies },
    });
  }

  emitSynthesis(missionId: string, synthesisScore: number, recommendation: string) {
    this.publish({
      type: 'magnet_synthesis',
      mission_id: missionId,
      timestamp: Date.now(),
      data: { synthesis_score: synthesisScore, recommendation },
    });
  }

  emitGateDecision(missionId: string, gateName: string, passed: boolean) {
    this.publish({
      type: 'gate_decision',
      mission_id: missionId,
      timestamp: Date.now(),
      data: { gate_name: gateName, gate_passed: passed },
    });
  }

  emitBeadCreated(missionId: string, beadId: string, beadType: string) {
    this.publish({
      type: 'bead_created',
      mission_id: missionId,
      timestamp: Date.now(),
      data: { bead_id: beadId, bead_type: beadType },
    });
  }

  onMissionEvent(missionId: string, callback: (event: MagnetEventMessage) => void) {
    this.hub.onMissionEvent(missionId, callback);
  }

  offMissionEvent(missionId: string, callback: (event: MagnetEventMessage) => void) {
    this.hub.offMissionEvent(missionId, callback);
  }

  replay(missionId: string, limit = 100): MagnetEventMessage[] {
    return this.hub.replay(missionId, limit);
  }
}

/**
 * WebSocket connection manager
 */
export class WebSocketManager {
  private wss: WebSocketServer;
  private connections: Map<string, Set<WebSocket>> = new Map();
  private eventBus = MissionEventBus.getInstance();

  constructor(server: any) {
    this.wss = new WebSocketServer({ server });
    this.setupConnections();
  }

  private setupConnections() {
    this.wss.on('connection', (ws: WebSocket, req) => {
      const url = new URL(req.url || '', 'http://localhost');
      const missionId = url.pathname.split('/').pop();

      if (!missionId || missionId === 'ws') {
        ws.close(1008, 'Invalid mission ID');
        return;
      }

      // Register connection
      if (!this.connections.has(missionId)) {
        this.connections.set(missionId, new Set());
      }
      this.connections.get(missionId)!.add(ws);

      // Replay persisted history for late subscribers
      for (const past of this.eventBus.replay(missionId, 50)) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(past));
        }
      }

      // Listen for magnet events
      const eventHandler = (event: MagnetEventMessage) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(event));
        }
      };

      this.eventBus.onMissionEvent(missionId, eventHandler);

      ws.on('close', () => {
        this.connections.get(missionId)?.delete(ws);
        this.eventBus.offMissionEvent(missionId, eventHandler);
      });

      ws.on('error', (error) => {
        console.error(`WebSocket error for mission ${missionId}:`, error);
      });
    });
  }

  broadcast(missionId: string, event: MagnetEventMessage) {
    const clients = this.connections.get(missionId);
    if (clients) {
      for (const client of clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send(JSON.stringify(event));
        }
      }
    }
  }

  getConnectedClients(missionId: string): number {
    return this.connections.get(missionId)?.size || 0;
  }
}

/**
 * Frontend integration (to replace in src/app/page.tsx)
 */
export class DashboardWebSocketClient {
  private ws: WebSocket | null = null;
  private missionId: string;
  private callbacks: Map<string, (event: MagnetEventMessage) => void> = new Map();

  constructor(missionId: string) {
    this.missionId = missionId;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${protocol}//${window.location.host}/ws/missions/${this.missionId}/events`;

      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log(`Connected to mission ${this.missionId} event stream`);
        resolve();
      };

      this.ws.onmessage = (event) => {
        const msg: MagnetEventMessage = JSON.parse(event.data);
        this.handleEvent(msg);
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onclose = () => {
        console.log('Disconnected from event stream');
      };
    });
  }

  on(type: string, callback: (event: MagnetEventMessage) => void) {
    this.callbacks.set(type, callback);
  }

  private handleEvent(event: MagnetEventMessage) {
    const callback = this.callbacks.get(event.type);
    if (callback) {
      callback(event);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export default WebSocketManager;
