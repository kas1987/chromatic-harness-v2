---
name: driver-abstraction-for-os-bound-code
source_ids: [2026-04-26-driver-abstraction-for-os-bound-code]
source_type: anti-pattern
confidence: 0.90
suggested_use: Driver Abstractions Make OS-Bound Code Unit-Testable
canon_map: operations
status: approved
tags: [testing, abstraction, os-integration, dependency-injection]
---

## Summary

Driver Abstractions Make OS-Bound Code Unit-Testable

## Evidence

# Learning: Driver Abstractions Make OS-Bound Code Unit-Testable

## What We Learned

When implementing code that depends on real OS interactions (keyboard simulation, clipboard, file watchers, etc.), define a small `Driver` interface and a setter (`setHotkeyDriver`, `setClipboardDriver`) that lets tests swap in a mock. The production code uses a real driver imported lazily; tests use an in-memory recording driver.

```typescript
export interface ClipboardDriver {
  read(): Promise<string>;
  write(text: string): Promise<void>;
}

class ClipboardyDriver implements ClipboardDriver { /* uses real lib */ }

let activeDriver: ClipboardDriver = new ClipboardyDriver();
export function setClipboardDriver(driver: ClipboardDriver): void {
  activeDriver = driver;
}
```

## Why It Matters

- Eliminates "can't unit-test this, requires CI with X" excuses
- Tests run in <1 second instead of requiring real keyboard/clipboard/filesystem
- Production code stays clean (no `if (testMode) ...` branches)
- Native libraries can be dynamically imported (lazy load) so test runs don't pull in heavy native deps

## Source

whisper-call v0.1.0: `whisper-flow-mcp/src/hotkey.ts` (HotkeyDriver) and
`whisper-flow-mcp/src/clipboard.ts` (ClipboardDriver). Verified by 5 unit tests
running in <100ms with no real OS interaction.

## When to Apply

- OS-level APIs (keyboard, clipboard, screen, audio capture)
- Network calls in code that should be testable offline
- Time-dependent code (`Date.now()` → `ClockDriver`)
- Random number generation (`RngDriver` for deterministic tests)
- Subprocess spawning (`SubprocessDriver`)
