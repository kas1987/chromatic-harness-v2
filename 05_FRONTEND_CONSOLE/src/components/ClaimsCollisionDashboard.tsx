"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useTheme } from "@/lib/theme";

interface ClaimRecord {
  lease_id: string;
  owner_agent: string;
  resources: string[];
  created_at: string;
  expires_at: string;
  heartbeat_at: string;
  released_at?: string;
  status: "active" | "released" | "expired";
}

interface ConflictPair {
  lease_a: string;
  lease_b: string;
  resource: string;
  owner_a: string;
  owner_b: string;
}

interface DeadlockCycle {
  cycle: string[];
  resources: string[];
  suggested_release: string[];
}

interface ClaimsState {
  active_claims: ClaimRecord[];
  stale_claims: string[];
  conflicts: ConflictPair[];
  deadlock_cycles: DeadlockCycle[];
  timestamp: string;
}

interface UseWebSocketEventsOptions {
  onClaimStateChange?: (state: ClaimsState) => void;
}

function useWebSocketClaimsEvents(options?: UseWebSocketEventsOptions) {
  const [state, setState] = useState<ClaimsState | null>(null);
  const [connected, setConnected] = useState(false);
  // Stabilise the callback so changing it does not recreate the EventSource.
  const callbackRef = useRef(options?.onClaimStateChange);
  callbackRef.current = options?.onClaimStateChange;

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let cancelled = false;

    try {
      // Try SSE (Server-Sent Events) for live updates
      eventSource = new EventSource("/api/ws/claims?sse=true");

      eventSource.onopen = () => {
        if (!cancelled) setConnected(true);
      };
      eventSource.onmessage = (event) => {
        if (cancelled) return;
        try {
          const data = JSON.parse(event.data) as ClaimsState;
          setState(data);
          callbackRef.current?.(data);
        } catch {
          // ignore malformed SSE payloads
        }
      };
      eventSource.onerror = () => {
        if (!cancelled) setConnected(false);
        eventSource?.close();
      };
    } catch {
      setConnected(false);
    }

    return () => {
      cancelled = true;
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  return { state, connected };
}

export default function ClaimsCollisionDashboard() {
  const { theme } = useTheme();
  const [claimsState, setClaimsState] = useState<ClaimsState | null>(null);
  const [forceReleaseLeaseId, setForceReleaseLeaseId] = useState<string | null>(null);
  const [forceReleaseConfirm, setForceReleaseConfirm] = useState(false);
  const [releaseLoading, setReleaseLoading] = useState(false);
  const [releaseStatus, setReleaseStatus] = useState<"ok" | "err" | null>(null);

  // WebSocket connection for live updates
  const { state: wsState, connected: wsConnected } = useWebSocketClaimsEvents({
    onClaimStateChange: setClaimsState,
  });

  // Polling fallback every 3s
  const pollClaims = useCallback(async () => {
    try {
      const res = await fetch("/api/claims/state");
      if (res.ok) {
        const data = (await res.json()) as ClaimsState;
        setClaimsState(data);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    pollClaims();
    const interval = setInterval(pollClaims, 3000);
    return () => clearInterval(interval);
  }, [pollClaims]);

  async function handleForceRelease() {
    if (!forceReleaseLeaseId) return;
    setReleaseLoading(true);
    setReleaseStatus(null);
    try {
      const res = await fetch("/api/claims/force-release", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lease_id: forceReleaseLeaseId }),
      });
      if (res.ok) {
        setReleaseStatus("ok");
        setForceReleaseLeaseId(null);
        setForceReleaseConfirm(false);
        pollClaims();
      } else {
        setReleaseStatus("err");
      }
    } catch {
      setReleaseStatus("err");
    } finally {
      setReleaseLoading(false);
    }
  }

  const PANEL: React.CSSProperties = {
    border: `1px solid ${theme.panelBorder}`,
    borderRadius: 4,
    padding: 12,
    marginBottom: 16,
    background: theme.panelBg,
  };

  const HEADING: React.CSSProperties = {
    fontSize: 12,
    fontWeight: "bold",
    color: theme.heading,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 8,
    marginTop: 0,
  };

  const BADGE = (color: string): React.CSSProperties => ({
    display: "inline-block",
    padding: "1px 6px",
    borderRadius: 3,
    background: color,
    color: "#fff",
    fontSize: 11,
    marginLeft: 6,
  });

  const chip: React.CSSProperties = { fontSize: 11, color: theme.muted };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
      {/* Panel — Live Claim State */}
      <div style={PANEL}>
        <p style={HEADING}>
          Live Collision Claims
          {wsConnected && (
            <span style={{ marginLeft: 8, fontSize: 10, fontWeight: "normal", letterSpacing: 0, textTransform: "none", color: theme.success }}>
              ● live
            </span>
          )}
          {!wsConnected && (
            <span style={{ marginLeft: 8, fontSize: 10, fontWeight: "normal", letterSpacing: 0, textTransform: "none", color: theme.muted }}>
              ○ polling
            </span>
          )}
        </p>

        {!claimsState && <p style={{ color: theme.muted, fontSize: 12 }}>Loading claim state...</p>}

        {claimsState && (
          <>
            {/* Summary badges */}
            <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
              <span style={BADGE(theme.info)}>
                Active Claims: {claimsState.active_claims.length}
              </span>
              {claimsState.stale_claims.length > 0 && (
                <span style={BADGE(theme.warning)}>
                  Stale: {claimsState.stale_claims.length}
                </span>
              )}
              {claimsState.conflicts.length > 0 && (
                <span style={BADGE(theme.danger)}>
                  Live Conflicts: {claimsState.conflicts.length}
                </span>
              )}
            </div>

            {/* Active claims list */}
            {claimsState.active_claims.length === 0 && (
              <p style={{ color: theme.muted, fontSize: 12 }}>No active claims.</p>
            )}

            {claimsState.active_claims.map((claim) => {
              const expiresAt = new Date(claim.expires_at);
              const now = new Date();
              const msUntilExpiry = expiresAt.getTime() - now.getTime();
              const isExpiringSoon = msUntilExpiry < 5 * 60 * 1000; // < 5 min
              const isStale = claimsState.stale_claims.includes(claim.lease_id);

              return (
                <div
                  key={claim.lease_id}
                  style={{
                    padding: "6px 8px",
                    marginBottom: 6,
                    borderRadius: 3,
                    background: theme.panelBg,
                    fontSize: 12,
                    border: `1px solid ${isStale ? theme.danger : isExpiringSoon ? theme.warning : theme.panelBorder}`,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div>
                      <span style={{ color: theme.accent, fontWeight: "bold" }}>
                        {claim.lease_id.slice(0, 12)}…
                      </span>
                      <span style={{ marginLeft: 8, color: theme.text }}>
                        {claim.owner_agent}
                      </span>
                    </div>
                    <button
                      onClick={() => setForceReleaseLeaseId(claim.lease_id)}
                      style={{
                        background: theme.danger,
                        border: "none",
                        color: "#fff",
                        padding: "2px 8px",
                        borderRadius: 3,
                        cursor: "pointer",
                        fontSize: 10,
                      }}
                    >
                      Release
                    </button>
                  </div>
                  <div style={{ marginTop: 4, color: theme.muted, fontSize: 10 }}>
                    <div>
                      Resources: {claim.resources.map((r) => r.replace("queue:", "")).join(", ")}
                    </div>
                    <div>
                      Created: {new Date(claim.created_at).toLocaleTimeString()}
                      {isExpiringSoon && (
                        <span style={{ marginLeft: 4, color: theme.warning }}>
                          (expires in {Math.round(msUntilExpiry / 1000 / 60)}m)
                        </span>
                      )}
                    </div>
                    {isStale && (
                      <div style={{ color: theme.danger, marginTop: 2 }}>
                        ⚠ Stale claim — owner may have crashed
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Panel — Deadlock Detector & Conflicts */}
      <div style={PANEL}>
        <p style={HEADING}>Deadlock Detector</p>

        {!claimsState && <p style={{ color: theme.muted, fontSize: 12 }}>Loading deadlock analysis...</p>}

        {claimsState && (
          <>
            {claimsState.deadlock_cycles.length === 0 && claimsState.conflicts.length === 0 && (
              <p style={{ color: theme.success, fontSize: 12 }}>No deadlocks or conflicts detected.</p>
            )}

            {/* Deadlock cycles */}
            {claimsState.deadlock_cycles.length > 0 && (
              <>
                <p style={{ color: theme.danger, fontSize: 11, marginBottom: 8 }}>
                  {claimsState.deadlock_cycles.length} deadlock cycle(s) detected:
                </p>
                {claimsState.deadlock_cycles.map((cycle, i) => (
                  <div
                    key={i}
                    style={{
                      padding: "6px 8px",
                      marginBottom: 8,
                      borderRadius: 3,
                      background: theme.panelBg,
                      border: `2px solid ${theme.danger}`,
                      fontSize: 11,
                    }}
                  >
                    <div style={{ color: theme.danger, fontWeight: "bold", marginBottom: 4 }}>
                      Cycle: {cycle.cycle.join(" → ")}
                    </div>
                    <div style={{ color: theme.text, marginBottom: 4 }}>
                      Contested resources: {cycle.resources.join(", ")}
                    </div>
                    <div style={{ color: theme.warning }}>
                      <strong>Suggested release order:</strong>
                      {cycle.suggested_release.map((leaseId, idx) => (
                        <div key={idx} style={{ marginLeft: 12, marginTop: 2 }}>
                          {idx + 1}. {leaseId.slice(0, 12)}…
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </>
            )}

            {/* Conflicts (non-cyclic) */}
            {claimsState.conflicts.length > 0 && claimsState.deadlock_cycles.length === 0 && (
              <>
                <p style={{ color: theme.warning, fontSize: 11, marginBottom: 8 }}>
                  {claimsState.conflicts.length} resource conflict(s):
                </p>
                {claimsState.conflicts.map((conflict, i) => (
                  <div
                    key={i}
                    style={{
                      padding: "6px 8px",
                      marginBottom: 6,
                      borderRadius: 3,
                      background: theme.panelBg,
                      border: `1px solid ${theme.warning}`,
                      fontSize: 11,
                    }}
                  >
                    <div style={{ color: theme.text, marginBottom: 2 }}>
                      <span style={{ fontWeight: "bold" }}>{conflict.owner_a}</span>
                      <span style={{ color: theme.muted, margin: "0 4px" }}>↔</span>
                      <span style={{ fontWeight: "bold" }}>{conflict.owner_b}</span>
                    </div>
                    <div style={{ color: theme.muted }}>
                      Contested: {conflict.resource.replace("queue:", "")}
                    </div>
                  </div>
                ))}
              </>
            )}

            <div style={{ marginTop: 12, color: theme.muted, fontSize: 10 }}>
              Last updated: {claimsState.timestamp ? new Date(claimsState.timestamp).toLocaleTimeString() : "—"}
            </div>
          </>
        )}
      </div>

      {/* Modal: Force-Release Confirmation */}
      {forceReleaseLeaseId && (
        <div
          style={{
            gridColumn: "1 / -1",
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => {
            setForceReleaseLeaseId(null);
            setForceReleaseConfirm(false);
          }}
        >
          <div
            style={{
              background: theme.panelBg,
              border: `1px solid ${theme.panelBorder}`,
              borderRadius: 8,
              padding: 20,
              maxWidth: 400,
              color: theme.text,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 12px 0", color: theme.heading }}>
              Force Release Claim?
            </h3>
            <p style={{ color: theme.muted, marginBottom: 12 }}>
              Lease ID: <code style={{ color: theme.accent }}>{forceReleaseLeaseId.slice(0, 16)}…</code>
            </p>
            <p style={{ color: theme.warning, marginBottom: 12 }}>
              ⚠ This will forcibly release the claim. Use only if the owner agent has crashed and is not recovering.
            </p>

            {!forceReleaseConfirm && (
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => setForceReleaseConfirm(true)}
                  style={{
                    flex: 1,
                    background: theme.danger,
                    border: "none",
                    color: "#fff",
                    padding: "8px 12px",
                    borderRadius: 3,
                    cursor: "pointer",
                    fontWeight: "bold",
                  }}
                >
                  Yes, Release
                </button>
                <button
                  onClick={() => setForceReleaseLeaseId(null)}
                  style={{
                    flex: 1,
                    background: theme.panelBorder,
                    border: "none",
                    color: theme.text,
                    padding: "8px 12px",
                    borderRadius: 3,
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
              </div>
            )}

            {forceReleaseConfirm && (
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={handleForceRelease}
                  disabled={releaseLoading}
                  style={{
                    flex: 1,
                    background: releaseLoading ? theme.panelBorder : theme.danger,
                    border: "none",
                    color: releaseLoading ? theme.muted : "#fff",
                    padding: "8px 12px",
                    borderRadius: 3,
                    cursor: releaseLoading ? "default" : "pointer",
                    fontWeight: "bold",
                  }}
                >
                  {releaseLoading ? "Releasing…" : "Confirm Release"}
                </button>
                <button
                  onClick={() => {
                    setForceReleaseLeaseId(null);
                    setForceReleaseConfirm(false);
                  }}
                  disabled={releaseLoading}
                  style={{
                    flex: 1,
                    background: theme.panelBorder,
                    border: "none",
                    color: theme.text,
                    padding: "8px 12px",
                    borderRadius: 3,
                    cursor: releaseLoading ? "default" : "pointer",
                  }}
                >
                  Cancel
                </button>
              </div>
            )}

            {releaseStatus === "ok" && (
              <div style={{ marginTop: 12, color: theme.success, fontSize: 12 }}>
                ✓ Claim released successfully.
              </div>
            )}
            {releaseStatus === "err" && (
              <div style={{ marginTop: 12, color: theme.danger, fontSize: 12 }}>
                ✗ Failed to release claim. Check console.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
