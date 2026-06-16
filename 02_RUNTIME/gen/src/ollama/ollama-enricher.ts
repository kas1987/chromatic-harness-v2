import { OllamaClient } from "./ollama-client";

export interface EnrichmentTags {
  intent: string;
  category: string;
  risk_level: "low" | "medium" | "high";
  summary: string;
}

export class OllamaEnricher {
  private client: OllamaClient;
  private model: string;

  constructor(client: OllamaClient, model = "mistral:7b") {
    this.client = client;
    this.model = model;
  }

  async enrichEvent(
    toolName: string,
    input: Record<string, unknown>,
    succeeded: boolean,
  ): Promise<EnrichmentTags | null> {
    const inputSummary = this.summarizeInput(toolName, input);
    const prompt = `Classify this Claude Code tool call. Return ONLY valid JSON, no other text.

Tool: ${toolName}
Input: ${inputSummary}
Succeeded: ${succeeded}

Return JSON with exactly these fields:
{
  "intent": "one of: read_file, write_file, bash_command, search, web_fetch, git_operation, test_run, other",
  "category": "one of: code_change, exploration, execution, version_control, testing, other",
  "risk_level": "one of: low, medium, high",
  "summary": "one sentence describing what this tool call did"
}`;

    return this.client.generateJSON<EnrichmentTags>(this.model, prompt, {
      temperature: 0.05,
    }).catch(() => null);
  }

  private summarizeInput(toolName: string, input: Record<string, unknown>): string {
    if (toolName === "Bash") {
      const cmd = (input.command as string) ?? "";
      return cmd.substring(0, 150);
    }
    if (["Write", "Edit", "MultiEdit"].includes(toolName)) {
      return (input.file_path as string) ?? (input.filePath as string) ?? "unknown";
    }
    if (toolName === "Glob" || toolName === "Grep") {
      return (input.pattern as string) ?? (input.query as string) ?? "";
    }
    if (toolName === "WebFetch") {
      return (input.url as string) ?? "";
    }
    return JSON.stringify(input).substring(0, 150);
  }
}
