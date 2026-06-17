import fs from "fs";
import path from "path";
import { nanoid } from "nanoid";
import { Request, Response, Router } from "express";
import { MetaBrainStore, type MetaBrainEntry } from "../meta-brain/meta-brain-store";
import { auditLog } from "../otel/audit-logger";

type GateVerdict = "pass" | "warn" | "fail";
type GateConfidence = "observed" | "strong_inference" | "weak_inference" | "unknown";
type FindingSeverity = "low" | "medium" | "high" | "critical";

interface GovernanceGate {
  id: string;
  title: string;
  requiredEvidence: string[];
}

interface CouncilFindingInput {
  title: string;
  summary: string;
  severity?: FindingSeverity;
  confidence?: GateConfidence;
  nextAction?: string;
}

interface CouncilRunInput {
  gateId: string;
  verdict: GateVerdict;
  confidence?: GateConfidence;
  summary: string;
  reportPath: string;
  sourceTeam?: string;
  repoKey?: string;
  userKey?: string;
  sessionId?: string;
  eventTs?: string;
  sourceKey?: string;
  correlationId?: string;
  budgetImpactUsd?: number;
  skillDegradationRisk?: number;
  findings?: CouncilFindingInput[];
  tags?: string[];
  metadata?: Record<string, unknown>;
}

interface CouncilRunRecord {
  ts: string;
  correlationId: string;
  sourceKey: string;
  gateId: string;
  verdict: GateVerdict;
  confidence: GateConfidence;
  sourceTeam: string;
  repoKey: string;
  userKey: string;
  reportPath: string;
  summary: string;
  findingsCount: number;
  budgetImpactUsd?: number;
  skillDegradationRisk?: number;
  tags: string[];
}

const GATES: GovernanceGate[] = [
  {
    id: "intent-routing",
    title: "Intent Routing Gate",
    requiredEvidence: [
      "Routing decision log sample",
      "Fallback behavior evidence",
      "Confidence mismatch review",
    ],
  },
  {
    id: "trust-boundary",
    title: "Trust Boundary Gate",
    requiredEvidence: [
      "Untrusted input containment check",
      "Token/handshake validation status",
      "Prompt injection hygiene notes",
    ],
  },
  {
    id: "maintenance-intelligence",
    title: "Maintenance Intelligence Gate",
    requiredEvidence: [
      "Daily review artifact",
      "Threshold trigger status",
      "Weekly rollup comparison",
    ],
  },
  {
    id: "offline-value-audit",
    title: "Offline Value Audit Gate",
    requiredEvidence: [
      "Offline confidence trend",
      "Budget impact estimate",
      "Model/value chain divergence signal",
    ],
  },
];

const CONFIDENCE_TO_SCORE: Record<GateConfidence, number> = {
  observed: 1,
  strong_inference: 0.85,
  weak_inference: 0.6,
  unknown: 0.4,
};

const GATE_IDS = new Set(GATES.map((g) => g.id));
const COUNCIL_ROOT = path.resolve(".agents", "council");
const COUNCIL_ARCHIVE_ROOT = path.resolve(".agents", "archive", "council");
const COUNCIL_RUNS_PATH = path.join(COUNCIL_ROOT, "council-runs.jsonl");
const EXTRACTION_CANDIDATES_PATH = path.join(COUNCIL_ROOT, "extraction-candidates.jsonl");

export const adminGovernanceRouter = Router();

let metaBrainStore: MetaBrainStore | null = null;

export function initializeAdminGovernanceRouter(store: MetaBrainStore): void {
  metaBrainStore = store;
}

function getStore(): MetaBrainStore {
  if (!metaBrainStore) {
    throw new Error("Governance router is not initialized");
  }
  return metaBrainStore;
}

function ensureCouncilDir(): void {
  fs.mkdirSync(COUNCIL_ROOT, { recursive: true });
}

function parseJsonlFile(filePath: string): Array<Record<string, unknown>> {
  if (!fs.existsSync(filePath)) return [];
  const raw = fs.readFileSync(filePath, "utf8");
  if (!raw.trim()) return [];

  const rows: Array<Record<string, unknown>> = [];
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed && typeof parsed === "object") {
        rows.push(parsed as Record<string, unknown>);
      }
    } catch {
      // Skip malformed lines to remain fail-open for legacy data.
    }
  }
  return rows;
}

function parseJsonlFiles(filePaths: string[]): Array<Record<string, unknown>> {
  return filePaths.flatMap((filePath) => parseJsonlFile(filePath));
}

function listArchivedCouncilJsonl(fileName: string): string[] {
  if (!fs.existsSync(COUNCIL_ARCHIVE_ROOT)) return [];

  return fs
    .readdirSync(COUNCIL_ARCHIVE_ROOT, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name === fileName)
    .map((entry) => path.join(entry.parentPath, entry.name));
}

function toGateVerdict(value: unknown): GateVerdict | null {
  if (value === "pass" || value === "warn" || value === "fail") return value;
  return null;
}

function toGateConfidence(value: unknown): GateConfidence {
  if (value === "observed" || value === "strong_inference" || value === "weak_inference") {
    return value;
  }
  return "unknown";
}

function toFindingSeverity(value: unknown): FindingSeverity {
  if (value === "low" || value === "medium" || value === "high" || value === "critical") {
    return value;
  }
  return "medium";
}

function asFiniteNumber(value: unknown): number | undefined {
  if (typeof value !== "number") return undefined;
  if (!Number.isFinite(value)) return undefined;
  return value;
}

function normalizeTags(tags: unknown, defaults: string[]): string[] {
  const base = Array.isArray(tags) ? tags.filter((tag): tag is string => typeof tag === "string") : [];
  return Array.from(new Set([...defaults, ...base])).slice(0, 24);
}

function resolveContainedCouncilPath(inputPath: string): { absolute: string; relative: string } {
  const normalizedInput = inputPath.replace(/\\/g, "/").trim();
  if (!normalizedInput) {
    throw new Error("reportPath is required");
  }

  const candidate = path.isAbsolute(normalizedInput)
    ? path.resolve(normalizedInput)
    : path.resolve(normalizedInput.startsWith(".agents/") ? normalizedInput : `.agents/council/${normalizedInput}`);

  const relativeToCouncil = path.relative(COUNCIL_ROOT, candidate);
  const insideCouncil = !(relativeToCouncil.startsWith("..") || path.isAbsolute(relativeToCouncil));
  if (insideCouncil) {
    return {
      absolute: candidate,
      relative: `.agents/council/${relativeToCouncil.replace(/\\/g, "/")}`,
    };
  }

  const relativeToArchive = path.relative(COUNCIL_ARCHIVE_ROOT, candidate);
  const insideArchive = !(relativeToArchive.startsWith("..") || path.isAbsolute(relativeToArchive));
  if (insideArchive) {
    return {
      absolute: candidate,
      relative: `.agents/archive/council/${relativeToArchive.replace(/\\/g, "/")}`,
    };
  }

  throw new Error("reportPath must resolve under .agents/council or .agents/archive/council");
}

function appendJsonl(filePath: string, record: Record<string, unknown>): void {
  fs.appendFileSync(filePath, `${JSON.stringify(record)}\n`, "utf8");
}

function buildMetaBrainContent(summary: string, findings: CouncilFindingInput[]): string {
  if (findings.length === 0) return summary;

  const lines = findings.map((finding, idx) => {
    const severity = toFindingSeverity(finding.severity).toUpperCase();
    const conf = toGateConfidence(finding.confidence);
    const next = finding.nextAction ? ` | next: ${finding.nextAction}` : "";
    return `${idx + 1}. [${severity}] (${conf}) ${finding.title}: ${finding.summary}${next}`;
  });

  return `${summary}\n\nFindings:\n${lines.join("\n")}`;
}

function findRunRecord(sourceKey?: string, correlationId?: string): CouncilRunRecord | null {
  const rows = parseJsonlFile(COUNCIL_RUNS_PATH);
  for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
    const row = rows[idx];
    const rowSourceKey = typeof row.sourceKey === "string" ? row.sourceKey : undefined;
    const rowCorrelationId = typeof row.correlationId === "string" ? row.correlationId : undefined;

    if (sourceKey && rowSourceKey === sourceKey) return row as unknown as CouncilRunRecord;
    if (correlationId && rowCorrelationId === correlationId) return row as unknown as CouncilRunRecord;
  }
  return null;
}

function extractionCandidatesForCorrelation(correlationId: string): number {
  const rows = parseJsonlFiles([
    EXTRACTION_CANDIDATES_PATH,
    ...listArchivedCouncilJsonl("extraction-candidates.jsonl"),
  ]);
  return rows.filter((row) => row.correlationId === correlationId).length;
}

adminGovernanceRouter.get("/gates", (_req: Request, res: Response) => {
  return res.json({
    runbookVersion: 1,
    gates: GATES,
  });
});

adminGovernanceRouter.get("/runbook", (_req: Request, res: Response) => {
  return res.json({
    runbookVersion: 1,
    flow: [
      "Collect council report under .agents/council",
      "POST /admin/governance/council-runs to persist DB + JSONL sinks",
      "POST /admin/governance/council-runs/validate to verify sink integrity",
      "Escalate WARN/FAIL findings to maintenance or implementation queues",
    ],
    requiredSinks: [
      "meta_brain_entries",
      ".agents/council/council-runs.jsonl",
      ".agents/council/extraction-candidates.jsonl (or archived equivalent under .agents/archive/council/)",
      "gen/logs/gen-audit.jsonl",
    ],
  });
});

adminGovernanceRouter.post("/council-runs", (req: Request, res: Response) => {
  try {
    ensureCouncilDir();

    const body = (req.body ?? {}) as Partial<CouncilRunInput>;
    const gateId = typeof body.gateId === "string" ? body.gateId : "";
    const verdict = toGateVerdict(body.verdict);

    if (!gateId || !GATE_IDS.has(gateId)) {
      return res.status(400).json({ error: "gateId must be one of the published runbook gates" });
    }
    if (!verdict) {
      return res.status(400).json({ error: "verdict must be one of: pass, warn, fail" });
    }
    if (typeof body.summary !== "string" || !body.summary.trim()) {
      return res.status(400).json({ error: "summary is required" });
    }
    if (typeof body.reportPath !== "string" || !body.reportPath.trim()) {
      return res.status(400).json({ error: "reportPath is required" });
    }

    const confidence = toGateConfidence(body.confidence);
    const findingsRaw = Array.isArray(body.findings) ? body.findings : [];
    const findings = findingsRaw
      .filter((item): item is CouncilFindingInput => Boolean(item && typeof item.title === "string" && typeof item.summary === "string"))
      .map((item) => ({
        title: item.title.trim(),
        summary: item.summary.trim(),
        severity: toFindingSeverity(item.severity),
        confidence: toGateConfidence(item.confidence),
        nextAction: typeof item.nextAction === "string" ? item.nextAction.trim() : undefined,
      }))
      .filter((item) => item.title.length > 0 && item.summary.length > 0)
      .slice(0, 100);

    const { absolute: reportAbsolutePath, relative: reportPath } = resolveContainedCouncilPath(body.reportPath);
    if (!fs.existsSync(reportAbsolutePath)) {
      return res.status(400).json({ error: "reportPath does not exist" });
    }

    const sourceTeam = typeof body.sourceTeam === "string" && body.sourceTeam.trim() ? body.sourceTeam.trim() : "governance";
    const repoKey = typeof body.repoKey === "string" && body.repoKey.trim() ? body.repoKey.trim() : "04-prism";
    const userKey = typeof body.userKey === "string" && body.userKey.trim() ? body.userKey.trim() : "default-user";
    const eventTs = typeof body.eventTs === "string" && body.eventTs.trim() ? body.eventTs.trim() : new Date().toISOString();
    const correlationId = typeof body.correlationId === "string" && body.correlationId.trim()
      ? body.correlationId.trim()
      : `council-${nanoid(12)}`;
    const sourceKey = typeof body.sourceKey === "string" && body.sourceKey.trim()
      ? body.sourceKey.trim()
      : `council:${gateId}:${path.basename(reportPath).toLowerCase()}`;

    const budgetImpactUsd = asFiniteNumber(body.budgetImpactUsd);
    const skillDegradationRisk = asFiniteNumber(body.skillDegradationRisk);
    const tags = normalizeTags(body.tags, ["governance", "council", `gate:${gateId}`, `verdict:${verdict}`]);

    const entry = getStore().createEntry({
      sourceTeam,
      sourceType: "review",
      repoKey,
      userKey,
      sessionId: typeof body.sessionId === "string" ? body.sessionId : undefined,
      title: `Council ${gateId} ${verdict.toUpperCase()}`,
      content: buildMetaBrainContent(body.summary.trim(), findings),
      confidence: CONFIDENCE_TO_SCORE[confidence],
      tagsJson: JSON.stringify(tags),
      metadataJson: JSON.stringify({
        gateId,
        verdict,
        confidence,
        reportPath,
        correlationId,
        findingsCount: findings.length,
        budgetImpactUsd,
        skillDegradationRisk,
        ...(body.metadata ?? {}),
      }),
      eventTs,
      sourceKey,
    });

    const runRecord: CouncilRunRecord = {
      ts: eventTs,
      correlationId,
      sourceKey,
      gateId,
      verdict,
      confidence,
      sourceTeam,
      repoKey,
      userKey,
      reportPath,
      summary: body.summary.trim(),
      findingsCount: findings.length,
      budgetImpactUsd,
      skillDegradationRisk,
      tags,
    };

    appendJsonl(COUNCIL_RUNS_PATH, runRecord as unknown as Record<string, unknown>);

    for (const finding of findings) {
      const severity = toFindingSeverity(finding.severity);
      if (severity === "low" && verdict === "pass") continue;

      appendJsonl(EXTRACTION_CANDIDATES_PATH, {
        ts: eventTs,
        source: "governance/council-run",
        correlationId,
        sourceKey,
        gateId,
        verdict,
        confidence,
        reportPath,
        repoKey,
        userKey,
        title: finding.title,
        summary: finding.summary,
        severity,
        nextAction: finding.nextAction ?? "",
      });
    }

    auditLog.write({
      kind: "policy_change",
      decision: "recorded",
      reason: `Council run persisted: ${gateId} ${verdict}`,
      meta: {
        correlationId,
        sourceKey,
        reportPath,
        findingsCount: findings.length,
        verdict,
      },
    });

    return res.status(201).json({
      ok: true,
      correlationId,
      sourceKey,
      run: runRecord,
      entry,
    });
  } catch (err) {
    auditLog.write({
      kind: "policy_change",
      decision: "error",
      reason: "Council run persistence failed",
      meta: {
        error: (err as Error).message,
      },
    });
    return res.status(503).json({ error: (err as Error).message });
  }
});

adminGovernanceRouter.post("/council-runs/validate", (req: Request, res: Response) => {
  try {
    ensureCouncilDir();
    const body = (req.body ?? {}) as { sourceKey?: unknown; correlationId?: unknown };
    const sourceKey = typeof body.sourceKey === "string" ? body.sourceKey.trim() : "";
    const correlationId = typeof body.correlationId === "string" ? body.correlationId.trim() : "";

    if (!sourceKey && !correlationId) {
      return res.status(400).json({ error: "Provide sourceKey or correlationId" });
    }

    const runRecord = findRunRecord(sourceKey || undefined, correlationId || undefined);
    if (!runRecord) {
      return res.status(404).json({ error: "No council run record found for provided key" });
    }

    const sourceKeyResolved = runRecord.sourceKey;
    const metaBrainEntry: MetaBrainEntry | null = getStore().getEntryBySourceKey(sourceKeyResolved);
    const reportResolved = resolveContainedCouncilPath(runRecord.reportPath);
    const reportExists = fs.existsSync(reportResolved.absolute);
    const extractionCount = extractionCandidatesForCorrelation(runRecord.correlationId);

    const sinkStatus = {
      councilRunsJsonl: true,
      reportFile: reportExists,
      metaBrainEntry: Boolean(metaBrainEntry),
      extractionCandidates: extractionCount > 0 || runRecord.verdict === "pass",
      extractionCandidateCount: extractionCount,
    };

    const ok = sinkStatus.councilRunsJsonl && sinkStatus.reportFile && sinkStatus.metaBrainEntry && sinkStatus.extractionCandidates;

    return res.json({
      ok,
      correlationId: runRecord.correlationId,
      sourceKey: sourceKeyResolved,
      sinkStatus,
      run: runRecord,
      metaBrainEntryId: metaBrainEntry?.id ?? null,
    });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});