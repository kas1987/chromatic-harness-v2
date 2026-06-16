"use client";

import React from "react";

interface GitCIProps {
  git: {
    branch: string;
    commit: string;
    commitMsg: string;
    modified: number;
    untracked: number;
  } | null;
  ci: {
    generated_at: string;
    default_branch: string;
    counts: {
      local_total: number;
      remote_total: number;
      local_stale: number;
      remote_stale: number;
    };
    caps: {
      local_max_total: number;
      remote_max_total: number;
    };
    violations: string[];
    local_stale: Array<{ name: string; age_days: number }>;
  } | null;
  loading: boolean;
}

export default function GitCI({ git, ci, loading }: GitCIProps) {
  if (loading) {
    return (
      <div className="cc-panel">
        <div className="cc-panel-title">GIT / CI STATUS</div>
        <div style={{ color: "var(--cc-muted, #888)", fontSize: "0.85rem" }}>
          Loading git status…
        </div>
      </div>
    );
  }

  const staleCount = ci?.counts?.local_stale ?? 0;
  const visibleStale = ci?.local_stale?.slice(0, 3) ?? [];
  const hiddenStale = (ci?.local_stale?.length ?? 0) - visibleStale.length;
  const truncate = (s: string, n: number) =>
    s.length > n ? s.slice(0, n) + "…" : s;

  return (
    <div className="cc-panel">
      <div className="cc-panel-title">GIT / CI STATUS</div>

      {git && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "0.5rem",
            marginBottom: "0.5rem",
          }}
        >
          <span
            style={{
              background: "#6b21a8",
              color: "#e9d5ff",
              borderRadius: "4px",
              padding: "1px 7px",
              fontSize: "0.8rem",
              fontWeight: 600,
            }}
          >
            {git.branch}
          </span>
          <span
            style={{
              fontFamily: "monospace",
              color: "#a3e635",
              fontSize: "0.8rem",
            }}
          >
            {git.commit.slice(0, 7)}
          </span>
          <span style={{ color: "#94a3b8", fontSize: "0.8rem" }}>
            M:{git.modified} U:{git.untracked}
          </span>
          <span
            style={{
              color: "#cbd5e1",
              fontSize: "0.8rem",
              flexBasis: "100%",
              marginTop: "2px",
            }}
          >
            {truncate(git.commitMsg, 50)}
          </span>
        </div>
      )}

      {ci && (
        <>
          <div
            style={{
              display: "flex",
              gap: "1rem",
              alignItems: "center",
              marginBottom: "0.5rem",
              fontSize: "0.82rem",
              flexWrap: "wrap",
            }}
          >
            <span style={{ color: "#94a3b8" }}>
              L:
              <span style={{ color: "#e2e8f0" }}>
                {ci.counts.local_total}/{ci.caps.local_max_total}
              </span>
            </span>
            <span style={{ color: "#94a3b8" }}>
              R:
              <span style={{ color: "#e2e8f0" }}>
                {ci.counts.remote_total}/{ci.caps.remote_max_total}
              </span>
            </span>
            <span style={{ color: "#94a3b8" }}>
              Stale:
              <span
                style={{ color: staleCount > 0 ? "#f87171" : "#e2e8f0", fontWeight: staleCount > 0 ? 700 : 400 }}
              >
                {staleCount}
              </span>
            </span>
          </div>

          <div style={{ marginBottom: "0.5rem" }}>
            {ci.violations.length > 0 ? (
              <ul
                style={{
                  margin: 0,
                  paddingLeft: "1.1rem",
                  color: "#f87171",
                  fontSize: "0.8rem",
                }}
              >
                {ci.violations.map((v, i) => (
                  <li key={i}>{v}</li>
                ))}
              </ul>
            ) : (
              <span style={{ color: "#4ade80", fontSize: "0.8rem" }}>
                No violations
              </span>
            )}
          </div>

          {visibleStale.length > 0 && (
            <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
              {visibleStale.map((b, i) => (
                <div key={i} style={{ marginBottom: "2px" }}>
                  <span style={{ color: "#fbbf24", fontFamily: "monospace" }}>
                    {b.name}
                  </span>
                  <span style={{ marginLeft: "0.4rem", color: "#64748b" }}>
                    {b.age_days.toFixed(1)}d
                  </span>
                </div>
              ))}
              {hiddenStale > 0 && (
                <div style={{ color: "#64748b", marginTop: "2px" }}>
                  and {hiddenStale} more
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
