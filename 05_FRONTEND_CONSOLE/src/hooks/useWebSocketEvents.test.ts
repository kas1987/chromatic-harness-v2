import { renderHook, act } from '@testing-library/react';
import { useWebSocketEvents } from './useWebSocketEvents';

// ---- WebSocket mock --------------------------------------------------------

type WSListener = (event: MessageEvent | Event) => void;

interface MockWS {
  url: string;
  onopen: WSListener | null;
  onmessage: ((e: MessageEvent) => void) | null;
  onerror: WSListener | null;
  onclose: WSListener | null;
  close: jest.Mock;
  readyState: number;
  // test helpers
  _triggerOpen(): void;
  _triggerMessage(data: unknown): void;
  _triggerError(): void;
  _triggerClose(): void;
}

let lastSocket: MockWS | null = null;

class MockWebSocket implements MockWS {
  url: string;
  onopen: WSListener | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: WSListener | null = null;
  onclose: WSListener | null = null;
  close = jest.fn();
  readyState = WebSocket.CONNECTING;

  constructor(url: string) {
    this.url = url;
    lastSocket = this;
  }

  _triggerOpen() {
    this.readyState = WebSocket.OPEN;
    this.onopen?.(new Event('open'));
  }

  _triggerMessage(data: unknown) {
    const evt = new MessageEvent('message', { data: JSON.stringify(data) });
    this.onmessage?.(evt);
  }

  _triggerError() {
    this.readyState = WebSocket.CLOSED;
    this.onerror?.(new Event('error'));
  }

  _triggerClose() {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.(new Event('close'));
  }
}

// Replace global WebSocket before all tests
const OriginalWebSocket = global.WebSocket;

beforeAll(() => {
  // @ts-expect-error -- replacing global for tests
  global.WebSocket = MockWebSocket;
});

afterAll(() => {
  global.WebSocket = OriginalWebSocket;
});

beforeEach(() => {
  lastSocket = null;
});

// ---- helpers ---------------------------------------------------------------

const sampleMessage = {
  type: 'magnet_event',
  mission_id: 'mission-123',
  timestamp: Date.now(),
  data: {
    magnet_type: 'intent',
    anomalies: [],
    recommendation: 'proceed',
  },
};

const anomalousMessage = {
  type: 'magnet_synthesis',
  mission_id: 'mission-123',
  timestamp: Date.now(),
  data: {
    magnet_type: 'scope',
    anomalies: [{ message: 'high memory usage' }],
  },
};

// ---- tests -----------------------------------------------------------------

describe('useWebSocketEvents', () => {
  it('returns initial state when missionId is null', () => {
    const { result } = renderHook(() => useWebSocketEvents(null));
    expect(result.current.events).toEqual([]);
    expect(result.current.connected).toBe(false);
    expect(result.current.error).toBeNull();
    expect(lastSocket).toBeNull();
  });

  it('creates a WebSocket with the correct URL', () => {
    renderHook(() => useWebSocketEvents('mission-abc'));
    expect(lastSocket).not.toBeNull();
    expect(lastSocket!.url).toContain('/ws/missions/mission-abc/events');
  });

  it('sets connected=true when WebSocket opens', () => {
    const { result } = renderHook(() => useWebSocketEvents('mission-001'));

    act(() => {
      lastSocket!._triggerOpen();
    });

    expect(result.current.connected).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('adds event to state when a valid message arrives', () => {
    const { result } = renderHook(() => useWebSocketEvents('mission-001'));

    act(() => {
      lastSocket!._triggerOpen();
      lastSocket!._triggerMessage(sampleMessage);
    });

    expect(result.current.events).toHaveLength(1);
    const ev = result.current.events[0];
    expect(ev.mission_id).toBe('mission-123');
    expect(ev.magnet_name).toBe('intent');
    expect(ev.risk_delta).toBe(0);
    expect(ev.recommended_action).toBe('proceed');
  });

  it('sets risk_delta to 0.15 when anomalies are present', () => {
    const { result } = renderHook(() => useWebSocketEvents('mission-001'));

    act(() => {
      lastSocket!._triggerOpen();
      lastSocket!._triggerMessage(anomalousMessage);
    });

    expect(result.current.events[0].risk_delta).toBe(0.15);
    expect(result.current.events[0].recommended_action).toBe('high memory usage');
  });

  it('prepends new events (most recent first)', () => {
    const { result } = renderHook(() => useWebSocketEvents('mission-001'));

    act(() => {
      lastSocket!._triggerOpen();
      lastSocket!._triggerMessage({ ...sampleMessage, data: { magnet_type: 'first', anomalies: [] } });
      lastSocket!._triggerMessage({ ...sampleMessage, data: { magnet_type: 'second', anomalies: [] } });
    });

    expect(result.current.events[0].magnet_name).toBe('second');
    expect(result.current.events[1].magnet_name).toBe('first');
  });

  it('caps events list at 50 entries', () => {
    const { result } = renderHook(() => useWebSocketEvents('mission-001'));

    act(() => {
      lastSocket!._triggerOpen();
      for (let i = 0; i < 60; i++) {
        lastSocket!._triggerMessage({ ...sampleMessage, data: { magnet_type: `m${i}`, anomalies: [] } });
      }
    });

    expect(result.current.events).toHaveLength(50);
  });

  it('sets error and connected=false on WebSocket error', () => {
    const { result } = renderHook(() => useWebSocketEvents('mission-001'));

    act(() => {
      lastSocket!._triggerOpen();
      lastSocket!._triggerError();
    });

    expect(result.current.connected).toBe(false);
    expect(result.current.error).toBe('WebSocket connection error');
  });

  it('sets connected=false on WebSocket close', () => {
    const { result } = renderHook(() => useWebSocketEvents('mission-001'));

    act(() => {
      lastSocket!._triggerOpen();
      lastSocket!._triggerClose();
    });

    expect(result.current.connected).toBe(false);
  });

  it('closes WebSocket on unmount', () => {
    const { unmount } = renderHook(() => useWebSocketEvents('mission-001'));
    const socket = lastSocket!;

    unmount();

    expect(socket.close).toHaveBeenCalledTimes(1);
  });

  it('does not crash on malformed JSON message', () => {
    const { result } = renderHook(() => useWebSocketEvents('mission-001'));

    act(() => {
      lastSocket!._triggerOpen();
      // Manually send bad JSON
      const badEvt = new MessageEvent('message', { data: '{not valid json}' });
      lastSocket!.onmessage?.(badEvt);
    });

    // Should not throw; events list stays empty
    expect(result.current.events).toHaveLength(0);
  });

  it('reconnects when missionId changes', () => {
    const { rerender } = renderHook(
      ({ id }: { id: string }) => useWebSocketEvents(id),
      { initialProps: { id: 'mission-A' } }
    );
    const firstSocket = lastSocket;

    rerender({ id: 'mission-B' });

    // The first socket should have been closed
    expect(firstSocket!.close).toHaveBeenCalledTimes(1);
    // A new socket should have been created
    expect(lastSocket).not.toBe(firstSocket);
    expect(lastSocket!.url).toContain('mission-B');
  });
});
