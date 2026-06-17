import { OllamaClient } from "./ollama-client";
import type { PrismEvent } from "../types/prism-event";

export interface EventClassification {
  intent: 'urgent' | 'action-needed' | 'fyi' | 'archive';
  confidence: number;
  reason: string;
}

export interface TriageResult {
  canHandle: boolean;
  result?: string;
  confidence: number;
  model: string;
}

export class OllamaTriage {
  private client: OllamaClient;
  private model: string;
  private confidenceThreshold: number;

  constructor(
    client: OllamaClient,
    model = "mistral:7b",
    confidenceThreshold = 0.7,
  ) {
    this.client = client;
    this.model = model;
    this.confidenceThreshold = confidenceThreshold;
  }

  async triageExploreTask(query: string): Promise<TriageResult> {
    const available = await this.client.isAvailable();
    if (!available) {
      return { canHandle: false, confidence: 0, model: this.model };
    }

    const prompt = `You are a research assistant. Answer the following query as completely and accurately as possible using your training knowledge.
After your answer, on a new final line write exactly: CONFIDENCE: <number from 0.0 to 1.0>
where 1.0 means completely certain, 0.0 means no idea.

Query: ${query}`;

    const raw = await this.client.generate(this.model, prompt, { temperature: 0.3 });
    if (!raw) return { canHandle: false, confidence: 0, model: this.model };

    const confidenceMatch = raw.match(/CONFIDENCE:\s*([\d.]+)/i);
    const confidence = confidenceMatch ? parseFloat(confidenceMatch[1]) : 0;
    const result = raw.replace(/CONFIDENCE:\s*[\d.]+\s*$/i, "").trim();

    return {
      canHandle: confidence >= this.confidenceThreshold,
      result,
      confidence,
      model: this.model,
    };
  }

  async classifyEvent(event: PrismEvent): Promise<EventClassification> {
    const prompt = `Classify this incoming event for a knowledge worker triage system.
Source: ${event.source}
Subject: ${event.subject}
Body: ${event.body_text.slice(0, 500)}

Return ONLY valid JSON (no markdown): {"intent": "urgent"|"action-needed"|"fyi"|"archive", "confidence": 0.0-1.0, "reason": "one sentence"}`;

    const result = await this.client.generateJSON<EventClassification>(
      this.model,
      prompt,
      { temperature: 0.1 },
    );
    if (!result || !['urgent','action-needed','fyi','archive'].includes(result.intent)) {
      return { intent: 'fyi', confidence: 0.5, reason: 'classification unavailable' };
    }
    return result;
  }
}
