import { metrics, Meter, Counter, Histogram } from "@opentelemetry/api";

export function getMeter(): Meter {
  return metrics.getMeter("gen-orchestrator", "1.0.0");
}

let _hookCallsCounter: Counter | null = null;
let _hookLatencyHistogram: Histogram | null = null;
let _memoriesWrittenCounter: Counter | null = null;
let _budgetStopsCounter: Counter | null = null;
let _tokensUsedCounter: Counter | null = null;
let _routingReconciliationCounter: Counter | null = null;
let _userPromptBypassCounter: Counter | null = null;
let _sessionRoutingMetricsRegistered = false;

export function getHookCallsCounter(): Counter {
  if (!_hookCallsCounter) {
    _hookCallsCounter = getMeter().createCounter("gen.hook_calls", {
      description: "Total number of hook invocations",
    });
  }
  return _hookCallsCounter;
}

export function getHookLatencyHistogram(): Histogram {
  if (!_hookLatencyHistogram) {
    _hookLatencyHistogram = getMeter().createHistogram("gen.hook_latency_ms", {
      description: "Hook handler latency in milliseconds",
      unit: "ms",
    });
  }
  return _hookLatencyHistogram;
}

export function getMemoriesWrittenCounter(): Counter {
  if (!_memoriesWrittenCounter) {
    _memoriesWrittenCounter = getMeter().createCounter("gen.memories_written", {
      description: "Total number of memories written to the store",
    });
  }
  return _memoriesWrittenCounter;
}

export function getBudgetStopsCounter(): Counter {
  if (!_budgetStopsCounter) {
    _budgetStopsCounter = getMeter().createCounter("gen.budget_stops", {
      description: "Total number of tool calls blocked by budget guard",
    });
  }
  return _budgetStopsCounter;
}

export function getTokensUsedCounter(): Counter {
  if (!_tokensUsedCounter) {
    _tokensUsedCounter = getMeter().createCounter("gen.tokens_used", {
      description: "Cumulative token consumption reported via hooks",
    });
  }
  return _tokensUsedCounter;
}

/** Labels: `result` = match | mismatch | unknown */
export function getRoutingReconciliationCounter(): Counter {
  if (!_routingReconciliationCounter) {
    _routingReconciliationCounter = getMeter().createCounter("gen.routing_reconciliation", {
      description: "Pretool suggested vs client-reported active LLM comparison",
    });
  }
  return _routingReconciliationCounter;
}

export function getUserPromptBypassCounter(): Counter {
  if (!_userPromptBypassCounter) {
    _userPromptBypassCounter = getMeter().createCounter("gen.user_prompt_bypass", {
      description: "User-prompt normalizer bypassed (short prompt, etc.)",
    });
  }
  return _userPromptBypassCounter;
}

type SessionRoutingStatsFn = () => { size: number; evictionsTotal: number };

/**
 * Register observable gauges for session routing store (polls every metric export).
 * Safe to call once at process startup.
 */
export function registerSessionRoutingStoreMetrics(getStats: SessionRoutingStatsFn): void {
  if (_sessionRoutingMetricsRegistered) return;
  _sessionRoutingMetricsRegistered = true;
  const meter = getMeter();
  meter.createObservableGauge("gen.session_routing_store_entries", {
    description: "In-memory session routing hint count",
  }).addCallback((obs) => {
    obs.observe(getStats().size);
  });
  meter.createObservableGauge("gen.session_routing_store_evictions_total", {
    description: "Cumulative expired-entry evictions from session routing store",
  }).addCallback((obs) => {
    obs.observe(getStats().evictionsTotal);
  });
}
