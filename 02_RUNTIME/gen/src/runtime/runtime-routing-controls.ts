import fs from "fs";
import path from "path";

export interface RuntimeRoutingControls {
  promptCleanBeforeDelegate: boolean;
  preferOfflineRouting: boolean;
  offlineAuditEnabled: boolean;
}

const controlsPath = path.resolve(__dirname, "../../..", ".agents", "runtime-routing-controls.json");

function defaultControls(): RuntimeRoutingControls {
  return {
    promptCleanBeforeDelegate: process.env.GEN_ENABLE_PROMPT_CLEAN_BEFORE_DELEGATE !== "false",
    preferOfflineRouting: process.env.GEN_PREFER_OFFLINE_ROUTING === "true",
    offlineAuditEnabled: process.env.GEN_ENABLE_OFFLINE_AUDIT !== "false",
  };
}

function sanitize(value: unknown, fallback: RuntimeRoutingControls): RuntimeRoutingControls {
  const obj = (value ?? {}) as Partial<RuntimeRoutingControls>;
  return {
    promptCleanBeforeDelegate:
      typeof obj.promptCleanBeforeDelegate === "boolean"
        ? obj.promptCleanBeforeDelegate
        : fallback.promptCleanBeforeDelegate,
    preferOfflineRouting:
      typeof obj.preferOfflineRouting === "boolean"
        ? obj.preferOfflineRouting
        : fallback.preferOfflineRouting,
    offlineAuditEnabled:
      typeof obj.offlineAuditEnabled === "boolean"
        ? obj.offlineAuditEnabled
        : fallback.offlineAuditEnabled,
  };
}

export function loadRuntimeRoutingControls(): RuntimeRoutingControls {
  const fallback = defaultControls();
  if (!fs.existsSync(controlsPath)) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(controlsPath, "utf-8")) as unknown;
    return sanitize(parsed, fallback);
  } catch {
    return fallback;
  }
}

export function persistRuntimeRoutingControls(controls: RuntimeRoutingControls): void {
  const safe = sanitize(controls, defaultControls());
  fs.mkdirSync(path.dirname(controlsPath), { recursive: true });
  fs.writeFileSync(controlsPath, JSON.stringify(safe, null, 2), "utf-8");
}

export function getRuntimeRoutingControlsPath(): string {
  return controlsPath;
}
