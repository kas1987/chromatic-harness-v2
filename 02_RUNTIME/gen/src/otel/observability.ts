import * as crypto from 'crypto';
import { EventEnvelope, EventEnvelopePayload, TraceObject, TaskObject } from '../types/agent-observability';

export class ObservabilityLogger {
  /**
   * Generates a standard Event Envelope
   */
  static createEvent(
    eventType: string,
    workflowId: string,
    taskId: string,
    traceId: string,
    agentId: string,
    versionRefs: { prompt: string; policy: string; tools: string },
    payload: EventEnvelopePayload
  ): EventEnvelope {
    return {
      event_id: `evt_${crypto.randomUUID()}`,
      event_type: eventType,
      timestamp: new Date().toISOString(),
      workflow_id: workflowId,
      task_id: taskId,
      trace_id: traceId,
      agent_id: agentId,
      version_refs: versionRefs,
      payload
    };
  }

  /**
   * Log an event to the console (or external OTLP exporter)
   */
  static logEvent(event: EventEnvelope): void {
    // In a real implementation this would push to an OTel collector, DB, or event bus
    console.log(`[OBSERVABILITY EVENT] ${event.event_type} | Trace: ${event.trace_id} | Task: ${event.task_id}`);
    console.debug(JSON.stringify(event, null, 2));
  }
}
