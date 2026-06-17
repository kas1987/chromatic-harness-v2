"use client"

import { useRef, useEffect, useState } from "react"

interface MagnetEvent {
  event_id: string
  mission_id: string
  magnet_name: string
  inflection_point: string
  risk_delta: number
  recommended_action: string
  timestamp: string
}

function riskColor(delta: number): string {
  return delta > 0.3 ? '#ef4444' : delta > 0.1 ? '#f59e0b' : '#22c55e'
}

function magnetColor(name: string): string {
  const n = name.toLowerCase()
  if (n.includes('intake')) return '#14b8a6'
  if (n.includes('scope')) return '#facc15'
  if (n.includes('execution')) return '#22c55e'
  if (n.includes('cost')) return '#f59e0b'
  if (n.includes('security')) return '#ef4444'
  if (n.includes('validation')) return '#3b82f6'
  if (n.includes('decision')) return '#8b5cf6'
  if (n.includes('closure')) return '#a855f7'
  return '#a78bfa'
}

function fmt(ts: string): string {
  return new Date(ts).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

interface EventStreamProps {
  events: MagnetEvent[]
  wsLive: boolean
  missionId: string | null
}

export default function EventStream({ events, wsLive, missionId }: EventStreamProps) {
  const [paused, setPaused] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!paused && listRef.current) {
      listRef.current.scrollTop = 0
    }
  }, [events, paused])

  const displayed = [...events].reverse().slice(0, 50)

  return (
    <div className="cc-panel" style={{ marginTop: 14 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="cc-panel-title" style={{ margin: 0 }}>
            EVENT STREAM (LIVE)
          </span>
          <span
            className={wsLive ? 'cc-dot-live' : 'cc-dot-idle'}
            style={{ flexShrink: 0 }}
          />
          <span
            style={{
              fontSize: 9,
              color: wsLive ? '#22c55e' : '#475569',
              fontFamily: 'var(--font-mono, "IBM Plex Mono", monospace)',
              letterSpacing: '0.06em',
            }}
          >
            {wsLive ? 'LIVE' : 'POLLING'}
          </span>
          {missionId && (
            <span
              style={{
                fontSize: 9,
                color: 'var(--cc-muted, #475569)',
                fontFamily: 'var(--font-mono, "IBM Plex Mono", monospace)',
                maxWidth: '20ch',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={missionId}
            >
              {missionId}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            className="chromatic-button-ghost"
            style={{ padding: '2px 8px', fontSize: 11 }}
            onClick={() => {}}
            aria-label="Export events"
          >
            +
          </button>
          <button
            className="chromatic-button-ghost"
            style={{
              padding: '2px 8px',
              fontSize: 11,
              color: paused ? '#f59e0b' : undefined,
              borderColor: paused ? '#f59e0b' : undefined,
            }}
            onClick={() => setPaused((p) => !p)}
            aria-label={paused ? 'Resume event stream' : 'Pause event stream'}
          >
            {paused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </div>

      <div
        ref={listRef}
        className="cc-scrollable"
        style={{ maxHeight: 180, marginTop: 10 }}
      >
        {displayed.length === 0 ? (
          <div
            style={{
              fontSize: 12,
              color: 'var(--cc-muted, #475569)',
              fontStyle: 'italic',
              textAlign: 'center',
              padding: 20,
            }}
          >
            {missionId
              ? 'Waiting for magnet events...'
              : 'Select a mission to view events.'}
          </div>
        ) : (
          displayed.map((ev) => (
            <div
              key={ev.event_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 0',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                fontSize: 11,
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: riskColor(ev.risk_delta),
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  minWidth: 66,
                  fontFamily: 'var(--font-mono, "IBM Plex Mono", monospace)',
                  color: 'var(--cc-muted, #475569)',
                  fontSize: 10,
                }}
              >
                {fmt(ev.timestamp)}
              </span>
              <span
                style={{
                  fontWeight: 600,
                  color: magnetColor(ev.magnet_name),
                  minWidth: 130,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  fontSize: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
                title={ev.magnet_name}
              >
                {ev.magnet_name}
              </span>
              <span
                style={{
                  flex: 1,
                  color: 'var(--color-text-secondary, #94a3b8)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                title={ev.inflection_point}
              >
                {ev.inflection_point}
              </span>
              {ev.risk_delta !== 0 && (
                <span
                  className="cc-tag"
                  style={{
                    color: riskColor(ev.risk_delta),
                    fontSize: 9,
                    padding: '1px 5px',
                    flexShrink: 0,
                  }}
                >
                  {ev.risk_delta > 0 ? '+' : ''}
                  {ev.risk_delta.toFixed(2)}
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
