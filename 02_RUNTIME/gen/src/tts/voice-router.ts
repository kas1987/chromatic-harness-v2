import voiceRoles from "./voice-roles.json";

export type VoiceContext =
  | "budget_stop"
  | "budget_warn"
  | "memory_recall"
  | "routing_suggestion"
  | "confirmation"
  | "default";

export function selectVoice(context: VoiceContext): string {
  const contextMap = voiceRoles.context_map as Record<string, string>;
  const roles = voiceRoles.roles as Record<string, string>;

  const role = contextMap[context] ?? "assistant_default";
  return roles[role] ?? roles["assistant_default"];
}
