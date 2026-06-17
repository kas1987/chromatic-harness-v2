import { trace, Tracer } from "@opentelemetry/api";

export function getTracer(): Tracer {
  return trace.getTracer("gen-orchestrator", "1.0.0");
}
