/**
 * Tests for api.ts — covers request construction and response parsing via
 * a global fetch mock.
 */

import {
  getMissions,
  getMission,
  createMission,
  getAgents,
  getAgent,
  registerAgent,
  promoteAgent,
  getLevelThresholds,
  updateBeadStatus,
  getBeads,
  getHealthStatus,
  getMissionAnalytics,
  getMissionEventsRange,
} from './api';

// ---------------------------------------------------------------------------
// fetch mock helpers
// ---------------------------------------------------------------------------

function mockFetchOk(data: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: jest.fn().mockResolvedValue({ data }),
  } as unknown as Response);
}

function mockFetchError(status: number, error: string) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status,
    json: jest.fn().mockResolvedValue({ error }),
  } as unknown as Response);
}

function mockFetchRaw(body: unknown, ok = true) {
  global.fetch = jest.fn().mockResolvedValue({
    ok,
    json: jest.fn().mockResolvedValue(body),
  } as unknown as Response);
}

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// apiCall wrapper
// ---------------------------------------------------------------------------

describe('apiCall — shared fetch wrapper', () => {
  it('calls the correct URL for getMissions', async () => {
    mockFetchOk([]);
    await getMissions();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/missions'),
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('throws with server error message when response is not ok', async () => {
    mockFetchError(400, 'Mission not found');
    await expect(getMission('bad-id')).rejects.toThrow('Mission not found');
  });

  it('sends JSON body for POST requests', async () => {
    mockFetchOk({ mission_id: 'new-001', status: 'pending', objective: 'test', confidence_required: 0.8, autonomy_level: 1, magnets: [], stop_conditions: [], created_at: '' });
    await createMission({ objective: 'test', autonomy_level: 1, confidence_required: 0.8 });

    const callArgs = (global.fetch as jest.Mock).mock.calls[0];
    const options = callArgs[1] as RequestInit;
    expect(options.method).toBe('POST');
    expect(options.headers).toEqual({ 'Content-Type': 'application/json' });
    expect(JSON.parse(options.body as string)).toMatchObject({ packet: { objective: 'test' } });
  });
});

// ---------------------------------------------------------------------------
// getMission
// ---------------------------------------------------------------------------

describe('getMission', () => {
  it('returns the mission object on success', async () => {
    const mission = { mission_id: 'm1', status: 'running', objective: 'do something', confidence_required: 0.9, autonomy_level: 2, magnets: [], stop_conditions: [], created_at: '2024-01-01' };
    mockFetchOk(mission);
    const result = await getMission('m1');
    expect(result.mission_id).toBe('m1');
    expect(result.status).toBe('running');
  });
});

// ---------------------------------------------------------------------------
// getAgents / getAgent
// ---------------------------------------------------------------------------

describe('getAgents', () => {
  it('returns an array of agents', async () => {
    mockFetchOk([{ agent_id: 'a1' }, { agent_id: 'a2' }]);
    const result = await getAgents();
    expect(result).toHaveLength(2);
    expect(result[0].agent_id).toBe('a1');
  });
});

describe('getAgent', () => {
  it('fetches correct URL for agent id', async () => {
    mockFetchOk({ agent_id: 'abc' });
    await getAgent('abc');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/agents/abc'),
      expect.anything()
    );
  });
});

// ---------------------------------------------------------------------------
// registerAgent
// ---------------------------------------------------------------------------

describe('registerAgent', () => {
  it('POSTs to /agents with agent payload', async () => {
    const profile = { agent_id: 'new-agent', current_level: 0, total_executions: 0, successful_executions: 0, success_rate: 0, avg_confidence: 0, risk_score: 0, promotion_history: [] };
    mockFetchOk(profile);
    const result = await registerAgent({ agent_id: 'new-agent', description: 'my agent', initial_level: 0 });
    expect(result.agent_id).toBe('new-agent');

    const [url, opts] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/agents');
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body as string);
    expect(body.agent_id).toBe('new-agent');
  });
});

// ---------------------------------------------------------------------------
// promoteAgent
// ---------------------------------------------------------------------------

describe('promoteAgent', () => {
  it('POSTs to /agents/:id/promote with correct payload', async () => {
    const profile = { agent_id: 'agent-x', current_level: 2, total_executions: 30, successful_executions: 26, success_rate: 0.87, avg_confidence: 0.85, risk_score: 0.15, promotion_history: [] };
    mockFetchOk(profile);
    const result = await promoteAgent('agent-x', 2, 'excellent work');
    expect(result.current_level).toBe(2);

    const [url, opts] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/agents/agent-x/promote');
    const body = JSON.parse(opts.body as string);
    expect(body.new_level).toBe(2);
    expect(body.reason).toBe('excellent work');
  });
});

// ---------------------------------------------------------------------------
// getLevelThresholds
// ---------------------------------------------------------------------------

describe('getLevelThresholds', () => {
  it('returns thresholds keyed by level string', async () => {
    const thresholds = {
      '1': { min_executions: 10, min_success_rate: 0.7, max_risk: 0.4 },
    };
    mockFetchOk(thresholds);
    const result = await getLevelThresholds();
    expect(result['1'].min_executions).toBe(10);
  });
});

// ---------------------------------------------------------------------------
// updateBeadStatus
// ---------------------------------------------------------------------------

describe('updateBeadStatus', () => {
  it('sends PATCH request to /beads/:id', async () => {
    const bead = { bead_id: 'b1', type: 'action', title: 'do it', source: 'test', priority: 'p1', status: 'active', created_at: '', updated_at: '' };
    mockFetchOk(bead);
    await updateBeadStatus('b1', 'active');

    const [url, opts] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/beads/b1');
    expect(opts.method).toBe('PATCH');
    const body = JSON.parse(opts.body as string);
    expect(body.status).toBe('active');
  });
});

// ---------------------------------------------------------------------------
// getBeads
// ---------------------------------------------------------------------------

describe('getBeads', () => {
  it('returns array from /beads', async () => {
    mockFetchOk([{ bead_id: 'x1' }]);
    const result = await getBeads();
    expect(result[0].bead_id).toBe('x1');
  });
});

// ---------------------------------------------------------------------------
// getHealthStatus
// ---------------------------------------------------------------------------

describe('getHealthStatus', () => {
  it('returns status from API when healthy', async () => {
    mockFetchOk({ status: 'ok' });
    const result = await getHealthStatus();
    expect(result.status).toBe('ok');
  });

  it('returns unavailable when fetch throws', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('network down'));
    const result = await getHealthStatus();
    expect(result.status).toBe('unavailable');
  });
});

// ---------------------------------------------------------------------------
// getMissionAnalytics (direct fetch, not apiCall)
// ---------------------------------------------------------------------------

describe('getMissionAnalytics', () => {
  it('returns analytics object on success', async () => {
    const analytics = { mission_id: 'm1', event_count: 5, duration_seconds: 10, confidence_trend: [], risk_trend: [], magnet_breakdown: [], top_actions: [], avg_risk_delta: 0, avg_confidence_delta: 0 };
    mockFetchRaw(analytics, true);
    const result = await getMissionAnalytics('m1');
    expect(result).not.toBeNull();
    expect(result!.mission_id).toBe('m1');
  });

  it('returns null when response is not ok', async () => {
    mockFetchRaw({}, false);
    const result = await getMissionAnalytics('m1');
    expect(result).toBeNull();
  });

  it('returns null when fetch throws', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('network'));
    const result = await getMissionAnalytics('m1');
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// getMissionEventsRange (direct fetch, not apiCall)
// ---------------------------------------------------------------------------

describe('getMissionEventsRange', () => {
  it('returns events array on success', async () => {
    const events = [{ event_id: 'e1', mission_id: 'm1', magnet_name: 'intent', inflection_point: 'exec', risk_delta: 0, recommended_action: 'proceed', timestamp: '' }];
    mockFetchRaw(events, true);
    const result = await getMissionEventsRange('m1');
    expect(result).toHaveLength(1);
    expect(result[0].event_id).toBe('e1');
  });

  it('appends from_ts and to_ts as query params', async () => {
    mockFetchRaw([], true);
    await getMissionEventsRange('m1', '2024-01-01', '2024-01-02');
    const url = (global.fetch as jest.Mock).mock.calls[0][0] as string;
    expect(url).toContain('from_ts=2024-01-01');
    expect(url).toContain('to_ts=2024-01-02');
  });

  it('returns empty array when response is not ok', async () => {
    mockFetchRaw({}, false);
    const result = await getMissionEventsRange('m1');
    expect(result).toEqual([]);
  });

  it('returns empty array when fetch throws', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('network'));
    const result = await getMissionEventsRange('m1');
    expect(result).toEqual([]);
  });
});
