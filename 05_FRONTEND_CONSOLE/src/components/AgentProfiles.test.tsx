import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentProfiles from './AgentProfiles';
import type { AgentProfile } from '@/lib/api';

const makeAgent = (overrides: Partial<AgentProfile> = {}): AgentProfile => ({
  agent_id: 'test-agent',
  current_level: 1,
  total_executions: 42,
  successful_executions: 38,
  success_rate: 0.905,
  avg_confidence: 0.88,
  risk_score: 0.12,
  promotion_history: [],
  ...overrides,
});

describe('AgentProfiles', () => {
  it('renders the heading', () => {
    render(<AgentProfiles agents={[]} />);
    expect(screen.getByText('Agent Trust Profiles')).toBeInTheDocument();
  });

  it('shows empty state message when no agents', () => {
    render(<AgentProfiles agents={[]} />);
    expect(screen.getByText('No agents registered.')).toBeInTheDocument();
  });

  it('does not show empty state message when agents exist', () => {
    const agents = [makeAgent()];
    render(<AgentProfiles agents={agents} />);
    expect(screen.queryByText('No agents registered.')).not.toBeInTheDocument();
  });

  it('renders agent ids for all agents', () => {
    const agents = [
      makeAgent({ agent_id: 'agent-alpha' }),
      makeAgent({ agent_id: 'agent-beta', current_level: 2 }),
    ];
    render(<AgentProfiles agents={agents} />);
    expect(screen.getByText('agent-alpha')).toBeInTheDocument();
    expect(screen.getByText('agent-beta')).toBeInTheDocument();
  });

  it('renders level badges for each agent', () => {
    const agents = [
      makeAgent({ agent_id: 'agent-alpha', current_level: 1 }),
      makeAgent({ agent_id: 'agent-beta', current_level: 3 }),
    ];
    render(<AgentProfiles agents={agents} />);
    expect(screen.getByText('L1')).toBeInTheDocument();
    expect(screen.getByText('L3')).toBeInTheDocument();
  });

  it('calls onSelect with the agent when clicking an agent card', () => {
    const agents = [makeAgent({ agent_id: 'clickable-agent' })];
    const onSelect = jest.fn();
    render(<AgentProfiles agents={agents} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('clickable-agent'));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(agents[0]);
  });

  it('renders selected agent detail panel when selectedAgent is provided', () => {
    const agent = makeAgent({
      agent_id: 'selected-one',
      current_level: 2,
      total_executions: 100,
      success_rate: 0.9,
      risk_score: 0.2,
    });
    render(<AgentProfiles agents={[agent]} selectedAgent={agent} />);
    expect(screen.getByText('Current Level')).toBeInTheDocument();
    expect(screen.getByText('Success Rate')).toBeInTheDocument();
    expect(screen.getByText('Risk Score')).toBeInTheDocument();
    // Executions count
    expect(screen.getByText('Executions: 100')).toBeInTheDocument();
  });

  it('does not render selected agent detail panel without selectedAgent', () => {
    const agent = makeAgent({ agent_id: 'unselected' });
    render(<AgentProfiles agents={[agent]} />);
    expect(screen.queryByText('Current Level')).not.toBeInTheDocument();
  });

  it('shows promotion history in detail panel when history is non-empty', () => {
    const agent = makeAgent({
      agent_id: 'veteran-agent',
      promotion_history: [
        { level: 1, date: '2024-01-15T00:00:00Z', reason: 'Proved reliability' },
      ],
    });
    render(<AgentProfiles agents={[agent]} selectedAgent={agent} />);
    expect(screen.getByText('Promotion History')).toBeInTheDocument();
    expect(screen.getByText(/Proved reliability/)).toBeInTheDocument();
  });

  it('does not show promotion history section when history is empty', () => {
    const agent = makeAgent({ promotion_history: [] });
    render(<AgentProfiles agents={[agent]} selectedAgent={agent} />);
    expect(screen.queryByText('Promotion History')).not.toBeInTheDocument();
  });

  it('renders success and risk percentages in agent list row', () => {
    const agent = makeAgent({ success_rate: 0.75, risk_score: 0.30 });
    render(<AgentProfiles agents={[agent]} />);
    expect(screen.getByText(/Success: 75%/)).toBeInTheDocument();
    expect(screen.getByText(/Risk: 30%/)).toBeInTheDocument();
  });
});
