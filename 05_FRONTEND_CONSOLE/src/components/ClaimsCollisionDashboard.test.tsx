import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ClaimsCollisionDashboard from "./ClaimsCollisionDashboard";
import { ThemeProvider } from "@/lib/theme";

// Mock fetch
global.fetch = jest.fn();

// Mock EventSource for SSE
class MockEventSource {
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    // Simulate connection opening
    setTimeout(() => this.onopen?.(), 10);
  }

  close() {
    // Mock close
  }

  static mockSendData(data: any) {
    if (this.instance?.onmessage) {
      this.instance.onmessage(
        new MessageEvent("message", { data: JSON.stringify(data) })
      );
    }
  }

  static instance: MockEventSource | null = null;
}

Object.defineProperty(window, "EventSource", {
  writable: true,
  value: MockEventSource,
});

const mockTheme = {
  panelBg: "#1a1a1a",
  panelBorder: "#333",
  text: "#fff",
  muted: "#999",
  heading: "#ccc",
  accent: "#00ff00",
  success: "#00aa00",
  warning: "#ffaa00",
  danger: "#ff3333",
  info: "#00aaff",
  brand: "#0077ff",
};

describe("ClaimsCollisionDashboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockClear();
  });

  test("renders dashboard with initial loading state", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        active_claims: [],
        stale_claims: [],
        conflicts: [],
        deadlock_cycles: [],
        timestamp: new Date().toISOString(),
      }),
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    expect(screen.getByText(/Live Collision Claims/i)).toBeInTheDocument();
  });

  test("displays active claims from API", async () => {
    const mockState = {
      active_claims: [
        {
          lease_id: "lease-abc123def456",
          owner_agent: "agent-01",
          resources: ["queue:bead-001"],
          created_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          heartbeat_at: new Date().toISOString(),
          status: "active" as const,
        },
      ],
      stale_claims: [],
      conflicts: [],
      deadlock_cycles: [],
      timestamp: new Date().toISOString(),
    };

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockState,
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/agent-01/)).toBeInTheDocument();
    });

    expect(screen.getByText(/bead-001/)).toBeInTheDocument();
  });

  test("shows stale claims warning", async () => {
    const mockState = {
      active_claims: [
        {
          lease_id: "lease-stale123",
          owner_agent: "agent-crashed",
          resources: ["queue:bead-002"],
          created_at: new Date(Date.now() - 7200000).toISOString(),
          expires_at: new Date(Date.now() - 100000).toISOString(),
          heartbeat_at: new Date(Date.now() - 7200000).toISOString(),
          status: "active" as const,
        },
      ],
      stale_claims: ["lease-stale123"],
      conflicts: [],
      deadlock_cycles: [],
      timestamp: new Date().toISOString(),
    };

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockState,
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Stale claim/i)).toBeInTheDocument();
      expect(screen.getByText(/owner may have crashed/i)).toBeInTheDocument();
    });
  });

  test("detects and displays resource conflicts", async () => {
    const mockState = {
      active_claims: [
        {
          lease_id: "lease-a1",
          owner_agent: "agent-01",
          resources: ["queue:bead-003"],
          created_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          heartbeat_at: new Date().toISOString(),
          status: "active" as const,
        },
        {
          lease_id: "lease-b2",
          owner_agent: "agent-02",
          resources: ["queue:bead-003"],
          created_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          heartbeat_at: new Date().toISOString(),
          status: "active" as const,
        },
      ],
      stale_claims: [],
      conflicts: [
        {
          lease_a: "lease-a1",
          lease_b: "lease-b2",
          resource: "queue:bead-003",
          owner_a: "agent-01",
          owner_b: "agent-02",
        },
      ],
      deadlock_cycles: [],
      timestamp: new Date().toISOString(),
    };

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockState,
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Live Conflicts: 1/i)).toBeInTheDocument();
      expect(screen.getByText(/agent-01.*↔.*agent-02/)).toBeInTheDocument();
    });
  });

  test("detects deadlock cycles", async () => {
    const mockState = {
      active_claims: [
        {
          lease_id: "lease-x1",
          owner_agent: "agent-x",
          resources: ["queue:bead-a"],
          created_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          heartbeat_at: new Date().toISOString(),
          status: "active" as const,
        },
        {
          lease_id: "lease-y2",
          owner_agent: "agent-y",
          resources: ["queue:bead-b"],
          created_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          heartbeat_at: new Date().toISOString(),
          status: "active" as const,
        },
      ],
      stale_claims: [],
      conflicts: [
        {
          lease_a: "lease-x1",
          lease_b: "lease-y2",
          resource: "queue:bead-a",
          owner_a: "agent-x",
          owner_b: "agent-y",
        },
        {
          lease_a: "lease-y2",
          lease_b: "lease-x1",
          resource: "queue:bead-b",
          owner_a: "agent-y",
          owner_b: "agent-x",
        },
      ],
      deadlock_cycles: [
        {
          cycle: ["lease-x1", "lease-y2"],
          resources: ["queue:bead-a", "queue:bead-b"],
          suggested_release: ["lease-x1"],
        },
      ],
      timestamp: new Date().toISOString(),
    };

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockState,
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/deadlock cycle/i)).toBeInTheDocument();
      expect(screen.getByText(/Suggested release order:/i)).toBeInTheDocument();
    });
  });

  test("force-release button shows confirmation dialog", async () => {
    const mockState = {
      active_claims: [
        {
          lease_id: "lease-to-release",
          owner_agent: "agent-01",
          resources: ["queue:bead-004"],
          created_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          heartbeat_at: new Date().toISOString(),
          status: "active" as const,
        },
      ],
      stale_claims: [],
      conflicts: [],
      deadlock_cycles: [],
      timestamp: new Date().toISOString(),
    };

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockState,
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      const releaseButton = screen.getByText(/Release/);
      fireEvent.click(releaseButton);
    });

    expect(screen.getByText(/Force Release Claim?/i)).toBeInTheDocument();
  });

  test("force-release sends POST request and shows success", async () => {
    const mockState = {
      active_claims: [
        {
          lease_id: "lease-release-me",
          owner_agent: "agent-01",
          resources: ["queue:bead-005"],
          created_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          heartbeat_at: new Date().toISOString(),
          status: "active" as const,
        },
      ],
      stale_claims: [],
      conflicts: [],
      deadlock_cycles: [],
      timestamp: new Date().toISOString(),
    };

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockState,
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      const releaseButton = screen.getByText(/Release/);
      fireEvent.click(releaseButton);
    });

    // Confirm the force release
    await waitFor(() => {
      const yesButton = screen.getByText(/Yes, Release/);
      fireEvent.click(yesButton);
    });

    // Confirm again
    await waitFor(() => {
      const confirmButton = screen.getByText(/Confirm Release/);
      fireEvent.click(confirmButton);
    });

    // Check that POST was made
    await waitFor(() => {
      const postCalls = (global.fetch as jest.Mock).mock.calls.filter(
        (call) => call[1]?.method === "POST"
      );
      expect(postCalls.length).toBeGreaterThan(0);
    });
  });

  test("displays polling indicator when SSE not connected", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        active_claims: [],
        stale_claims: [],
        conflicts: [],
        deadlock_cycles: [],
        timestamp: new Date().toISOString(),
      }),
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/polling/i)).toBeInTheDocument();
    });
  });

  test("shows no deadlocks message when none exist", async () => {
    const mockState = {
      active_claims: [],
      stale_claims: [],
      conflicts: [],
      deadlock_cycles: [],
      timestamp: new Date().toISOString(),
    };

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockState,
    });

    render(
      <ThemeProvider>
        <ClaimsCollisionDashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/No deadlocks or conflicts detected/i)
      ).toBeInTheDocument();
    });
  });
});
