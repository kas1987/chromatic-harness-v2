/**
 * React Hook: useWebSocketEvents
 * 
 * Custom hook for consuming real-time magnet events via WebSocket
 * Drop-in replacement for HTTP polling in dashboard components
 */

import { useEffect, useState } from 'react';
import type { MagnetEvent } from '../lib/api';

interface MagnetEventMessage {
  type: 'magnet_event' | 'magnet_synthesis' | 'gate_decision' | 'bead_created';
  mission_id: string;
  timestamp: number;
  data: Record<string, any>;
}

export function useWebSocketEvents(missionId: string | null) {
  const [events, setEvents] = useState<MagnetEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!missionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/missions/${missionId}/events`;

    const ws = new WebSocket(url);

    ws.onopen = () => {
      setConnected(true);
      setError(null);
      console.log(`Connected to ${missionId} event stream`);
    };

    ws.onmessage = (event) => {
      try {
        const msg: MagnetEventMessage = JSON.parse(event.data);

        const magnetEvent: MagnetEvent = {
          event_id: `evt-${Date.now()}-${Math.random()}`,
          mission_id: msg.mission_id,
          magnet_name: msg.data.magnet_type || msg.type,
          inflection_point: msg.type,
          risk_delta: msg.data.anomalies?.length > 0 ? 0.15 : 0,
          recommended_action:
            msg.data.anomalies?.[0]?.message ||
            msg.data.recommendation ||
            'proceed',
          timestamp: new Date(msg.timestamp).toISOString(),
        };

        setEvents((prev) => {
          const updated = [magnetEvent, ...prev];
          return updated.slice(0, 50);
        });
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [missionId]);

  return { events, connected, error };
}

export default useWebSocketEvents;
