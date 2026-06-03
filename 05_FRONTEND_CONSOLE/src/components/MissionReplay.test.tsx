import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import MissionReplay from './MissionReplay';
import * as api from '@/lib/api';
import type { MissionAnalytics, MagnetEvent } from '@/lib/api';

jest.mock('@/lib/api');

const mockedApi = api as jest.Mocked<typeof api>;

const makeAnalytics = (overrides: Partial<MissionAnalytics> = {}): MissionAnalytics => ({
  mission_id: 'mission-001',
  event_count: 3,
  duration_seconds: 12,
  confidence_trend: [
    { timestamp: '2024-01-01T00:00:00Z', value: 0.5 },
    { timestamp: '2024-01-01T00:00:06Z', value: 0.7 },
    { timestamp: '2024-01-01T00:00:12Z', value: 0.9 },
  ],
  risk_trend: [
    { timestamp: '2024-01-01T00:00:00Z', value: 0.3 },
    { timestamp: '2024-01-01T00:00:06Z', value: 0.2 },
    { timestamp: '2024-01-01T00:00:12Z', value: 0.1 },
  ],
  magnet_breakdown: [
    { magnet_name: 'intent', event_count: 1, total_risk_delta: 0, total_confidence_delta: 0.2 },
    { magnet_name: 'scope', event_count: 2, total_risk_delta: -0.1, total_confidence_delta: 0.3 },
  ],
  top_actions: [{ action: 'proceed', count: 3 }],
  avg_risk_delta: -0.05,
  avg_confidence_delta: 0.1,
  ...overrides,
});

const makeEvent = (id: string, overrides: Partial<MagnetEvent> = {}): MagnetEvent => ({
  event_id: id,
  mission_id: 'mission-001',
  magnet_name: 'intent',
  inflection_point: 'execution',
  risk_delta: 0.0,
  recommended_action: 'proceed',
  timestamp: '2024-01-01T00:00:01Z',
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

describe('MissionReplay', () => {
  it('renders loading state initially', () => {
    mockedApi.getMissionAnalytics.mockReturnValue(new Promise(() => {}));
    mockedApi.getMissionEventsRange.mockReturnValue(new Promise(() => {}));

    render(<MissionReplay missionId="mission-001" />);
    expect(screen.getByText('Mission Replay')).toBeInTheDocument();
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it('renders empty state when analytics reports zero events', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics({ event_count: 0 }));
    mockedApi.getMissionEventsRange.mockResolvedValue([]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      expect(screen.getByText(/No events recorded/i)).toBeInTheDocument();
    });
  });

  it('renders empty state when analytics is null', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(null);
    mockedApi.getMissionEventsRange.mockResolvedValue([]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      expect(screen.getByText(/No events recorded/i)).toBeInTheDocument();
    });
  });

  it('renders playback controls after loading', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics());
    mockedApi.getMissionEventsRange.mockResolvedValue([
      makeEvent('e1'),
      makeEvent('e2'),
      makeEvent('e3'),
    ]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      // Rewind, play, fast-forward buttons
      expect(screen.getByText('⏮')).toBeInTheDocument();
      expect(screen.getByText('▶')).toBeInTheDocument();
      expect(screen.getByText('⏭')).toBeInTheDocument();
    });
  });

  it('shows the mission id and event count in the heading', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics({ mission_id: 'mission-001', event_count: 3, duration_seconds: 12 }));
    mockedApi.getMissionEventsRange.mockResolvedValue([
      makeEvent('e1'),
      makeEvent('e2'),
      makeEvent('e3'),
    ]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      expect(screen.getByText(/mission-001/)).toBeInTheDocument();
      expect(screen.getByText(/3 events/)).toBeInTheDocument();
      expect(screen.getByText(/12s/)).toBeInTheDocument();
    });
  });

  it('shows magnet breakdown labels', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics());
    mockedApi.getMissionEventsRange.mockResolvedValue([makeEvent('e1')]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      // getAllByText since 'intent' may appear in both breakdown section and event log
      expect(screen.getAllByText('intent').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('scope').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders speed select with options', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics());
    mockedApi.getMissionEventsRange.mockResolvedValue([makeEvent('e1'), makeEvent('e2')]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('1×')).toBeInTheDocument();
    });

    // Use within the select element to avoid collisions with other numeric text
    const select = screen.getByDisplayValue('1×');
    expect(select).toBeInTheDocument();
    expect(select.tagName.toLowerCase()).toBe('select');
    // Verify the option values are present in the select
    const options = Array.from((select as HTMLSelectElement).options).map(o => o.text);
    expect(options).toContain('0.5×');
    expect(options).toContain('1×');
    expect(options).toContain('2×');
    expect(options).toContain('4×');
  });

  it('shows first event in log at playhead 0', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics());
    mockedApi.getMissionEventsRange.mockResolvedValue([
      makeEvent('e1', { magnet_name: 'first-magnet', recommended_action: 'review' }),
      makeEvent('e2', { magnet_name: 'second-magnet', recommended_action: 'proceed' }),
    ]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      expect(screen.getByText('first-magnet')).toBeInTheDocument();
    });
    // Second event not yet visible (playhead=0 means slice(0,1))
    expect(screen.queryByText('second-magnet')).not.toBeInTheDocument();
  });

  it('toggles play/pause button text', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics());
    mockedApi.getMissionEventsRange.mockResolvedValue([
      makeEvent('e1'),
      makeEvent('e2'),
      makeEvent('e3'),
    ]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      expect(screen.getByText('▶')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('▶'));
    expect(screen.getByText('⏸')).toBeInTheDocument();

    fireEvent.click(screen.getByText('⏸'));
    expect(screen.getByText('▶')).toBeInTheDocument();
  });

  it('fast-forward button jumps to last event', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics());
    mockedApi.getMissionEventsRange.mockResolvedValue([
      makeEvent('e1', { magnet_name: 'alpha' }),
      makeEvent('e2', { magnet_name: 'beta' }),
      makeEvent('e3', { magnet_name: 'gamma' }),
    ]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      expect(screen.getByText('⏭')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('⏭'));

    await waitFor(() => {
      // All three events should be visible after going to end
      expect(screen.getByText('alpha')).toBeInTheDocument();
      expect(screen.getByText('beta')).toBeInTheDocument();
      expect(screen.getByText('gamma')).toBeInTheDocument();
    });
  });

  it('rewind button resets playhead to 0', async () => {
    mockedApi.getMissionAnalytics.mockResolvedValue(makeAnalytics());
    mockedApi.getMissionEventsRange.mockResolvedValue([
      makeEvent('e1', { magnet_name: 'alpha' }),
      makeEvent('e2', { magnet_name: 'beta' }),
    ]);

    render(<MissionReplay missionId="mission-001" />);

    await waitFor(() => {
      expect(screen.getByText('⏭')).toBeInTheDocument();
    });

    // Jump to end first
    fireEvent.click(screen.getByText('⏭'));
    await waitFor(() => {
      expect(screen.getByText('beta')).toBeInTheDocument();
    });

    // Now rewind
    fireEvent.click(screen.getByText('⏮'));
    await waitFor(() => {
      expect(screen.queryByText('beta')).not.toBeInTheDocument();
      expect(screen.getByText('alpha')).toBeInTheDocument();
    });
  });
});
