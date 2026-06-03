import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentRegistration from './AgentRegistration';
import * as api from '@/lib/api';
import type { AgentProfile } from '@/lib/api';

// Mock the entire api module
jest.mock('@/lib/api');

const mockedApi = api as jest.Mocked<typeof api>;

const makeAgent = (overrides: Partial<AgentProfile> = {}): AgentProfile => ({
  agent_id: 'test-agent',
  current_level: 0,
  total_executions: 0,
  successful_executions: 0,
  success_rate: 0,
  avg_confidence: 0,
  risk_score: 0,
  promotion_history: [],
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  mockedApi.getLevelThresholds.mockResolvedValue({
    '1': { min_executions: 10, min_success_rate: 0.7, max_risk: 0.4 },
    '2': { min_executions: 25, min_success_rate: 0.8, max_risk: 0.3 },
    '3': { min_executions: 50, min_success_rate: 0.85, max_risk: 0.25 },
    '4': { min_executions: 100, min_success_rate: 0.9, max_risk: 0.2 },
    '5': { min_executions: 200, min_success_rate: 0.95, max_risk: 0.1 },
  });
});

describe('AgentRegistration', () => {
  it('renders the heading', async () => {
    render(<AgentRegistration />);
    expect(screen.getByText('Agent Registration')).toBeInTheDocument();
  });

  it('renders the agent id input', async () => {
    render(<AgentRegistration />);
    expect(screen.getByPlaceholderText(/agent-id/i)).toBeInTheDocument();
  });

  it('renders the description input', async () => {
    render(<AgentRegistration />);
    expect(screen.getByPlaceholderText(/description/i)).toBeInTheDocument();
  });

  it('renders the Register Agent button', async () => {
    render(<AgentRegistration />);
    expect(screen.getByRole('button', { name: /register agent/i })).toBeInTheDocument();
  });

  it('renders the initial level select dropdown', async () => {
    render(<AgentRegistration />);
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByText(/L0/)).toBeInTheDocument();
    expect(screen.getByText(/L5/)).toBeInTheDocument();
  });

  it('shows validation error when submitting without agent id', async () => {
    render(<AgentRegistration />);
    fireEvent.click(screen.getByRole('button', { name: /register agent/i }));
    await waitFor(() => {
      expect(screen.getByText('Agent ID is required')).toBeInTheDocument();
    });
  });

  it('calls registerAgent with correct payload on submit', async () => {
    const returnedAgent = makeAgent({ agent_id: 'my-agent' });
    mockedApi.registerAgent.mockResolvedValue(returnedAgent);

    render(<AgentRegistration />);

    await userEvent.type(screen.getByPlaceholderText(/agent-id/i), 'my-agent');
    await userEvent.type(screen.getByPlaceholderText(/description/i), 'A test agent');
    fireEvent.click(screen.getByRole('button', { name: /register agent/i }));

    await waitFor(() => {
      expect(mockedApi.registerAgent).toHaveBeenCalledWith({
        agent_id: 'my-agent',
        description: 'A test agent',
        initial_level: 0,
      });
    });
  });

  it('calls onAgentRegistered callback after successful registration', async () => {
    const returnedAgent = makeAgent({ agent_id: 'callback-agent' });
    mockedApi.registerAgent.mockResolvedValue(returnedAgent);
    const onAgentRegistered = jest.fn();

    render(<AgentRegistration onAgentRegistered={onAgentRegistered} />);
    await userEvent.type(screen.getByPlaceholderText(/agent-id/i), 'callback-agent');
    fireEvent.click(screen.getByRole('button', { name: /register agent/i }));

    await waitFor(() => {
      expect(onAgentRegistered).toHaveBeenCalledWith(returnedAgent);
    });
  });

  it('clears inputs after successful registration', async () => {
    const returnedAgent = makeAgent({ agent_id: 'cleared-agent' });
    mockedApi.registerAgent.mockResolvedValue(returnedAgent);

    render(<AgentRegistration />);
    const agentIdInput = screen.getByPlaceholderText(/agent-id/i) as HTMLInputElement;
    await userEvent.type(agentIdInput, 'cleared-agent');
    fireEvent.click(screen.getByRole('button', { name: /register agent/i }));

    await waitFor(() => {
      expect(agentIdInput.value).toBe('');
    });
  });

  it('shows error message when registerAgent throws', async () => {
    mockedApi.registerAgent.mockRejectedValue(new Error('Agent already exists'));

    render(<AgentRegistration />);
    await userEvent.type(screen.getByPlaceholderText(/agent-id/i), 'dupe-agent');
    fireEvent.click(screen.getByRole('button', { name: /register agent/i }));

    await waitFor(() => {
      expect(screen.getByText('Agent already exists')).toBeInTheDocument();
    });
  });

  it('submits on Enter key in agent id field', async () => {
    const returnedAgent = makeAgent({ agent_id: 'enter-agent' });
    mockedApi.registerAgent.mockResolvedValue(returnedAgent);

    render(<AgentRegistration />);
    const agentIdInput = screen.getByPlaceholderText(/agent-id/i);
    await userEvent.type(agentIdInput, 'enter-agent{Enter}');

    await waitFor(() => {
      expect(mockedApi.registerAgent).toHaveBeenCalledWith(
        expect.objectContaining({ agent_id: 'enter-agent' })
      );
    });
  });

  it('shows promotion timeline when selectedAgent is provided', async () => {
    const agent = makeAgent({
      agent_id: 'promoted-agent',
      current_level: 1,
      total_executions: 5,
      success_rate: 0.6,
      risk_score: 0.3,
    });
    render(<AgentRegistration selectedAgent={agent} />);

    await waitFor(() => {
      expect(screen.getByText(/Promotion timeline/i)).toBeInTheDocument();
      expect(screen.getByText('promoted-agent')).toBeInTheDocument();
    });
  });

  it('does not show promotion timeline without selectedAgent', async () => {
    render(<AgentRegistration />);
    await waitFor(() => {
      expect(screen.queryByText(/Promotion timeline/i)).not.toBeInTheDocument();
    });
  });

  it('shows locked promote button when agent does not meet thresholds', async () => {
    const agent = makeAgent({
      agent_id: 'locked-agent',
      current_level: 0,
      total_executions: 0,
      success_rate: 0,
      risk_score: 1.0,
    });
    render(<AgentRegistration selectedAgent={agent} />);

    await waitFor(() => {
      expect(screen.getByText(/L1 locked/i)).toBeInTheDocument();
    });
  });

  it('shows enabled promote button when agent meets thresholds', async () => {
    const agent = makeAgent({
      agent_id: 'ready-agent',
      current_level: 0,
      total_executions: 15,
      success_rate: 0.8,
      risk_score: 0.1,
    });
    render(<AgentRegistration selectedAgent={agent} />);

    await waitFor(() => {
      expect(screen.getByText(/Promote → L1/i)).toBeInTheDocument();
    });
  });
});
