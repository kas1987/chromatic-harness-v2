import type { OllamaClient } from "../ollama/ollama-client";

export async function formatForSpeech(
  text: string,
  ollamaModel: string,
  ollamaClient?: OllamaClient | null,
): Promise<string> {
  if (ollamaClient) {
    try {
      const available = await ollamaClient.isAvailable();
      if (available) {
        const prompt = `Convert this context note to a single natural spoken sentence. No markdown, no bullets, no introductory phrases. Just the spoken content.\n\nInput: ${text}\n\nSpoken:`;
        const result = await ollamaClient.generate(ollamaModel, prompt, { temperature: 0.3 });
        if (result && result.length > 10) return result.trim();
      }
    } catch {
      // Fall through to simple cleanup
    }
  }
  // Simple fallback: strip bullet markers, join lines
  return text
    .replace(/^[•*-]\s*/gm, "")
    .replace(/\n+/g, ". ")
    .replace(/\s+/g, " ")
    .replace(/\.$/, "")
    .trim();
}
