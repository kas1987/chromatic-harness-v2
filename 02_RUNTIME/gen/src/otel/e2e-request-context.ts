import type { Request } from "express";
import type { Span } from "@opentelemetry/api";
import { GEN_ATTRS } from "./attributes";

const MAX_RUN_ID_LEN = 256;
const MAX_TAGS = 32;
const MAX_TAG_LEN = 64;

export type E2eContext = { runId?: string; tags?: string[] };

export function isE2eMetadataEnabled(): boolean {
  return process.env.GEN_E2E_METADATA === "1";
}

function normalizeTags(raw: string[] | undefined): string[] | undefined {
  if (!raw?.length) return undefined;
  const seen = new Set<string>();
  const out: string[] = [];
  for (const t of raw) {
    const s = String(t).trim().slice(0, MAX_TAG_LEN);
    if (!s || seen.has(s)) continue;
    seen.add(s);
    out.push(s);
    if (out.length >= MAX_TAGS) break;
  }
  return out.length ? out : undefined;
}

function parseTagsHeader(h: string | undefined): string[] | undefined {
  if (h === undefined || !String(h).trim()) return undefined;
  const parts = String(h)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return normalizeTags(parts);
}

function readBodyMetadata(body: unknown): E2eContext {
  if (!body || typeof body !== "object") return {};
  const meta = (body as Record<string, unknown>).metadata;
  if (!meta || typeof meta !== "object") return {};
  const m = meta as Record<string, unknown>;
  const runRaw = m.e2eRunId;
  const runId =
    typeof runRaw === "string" && runRaw.trim()
      ? runRaw.trim().slice(0, MAX_RUN_ID_LEN)
      : undefined;
  let tags: string[] | undefined;
  if (Array.isArray(m.e2eTags)) {
    tags = normalizeTags(m.e2eTags.map((x) => String(x)));
  }
  return { runId: runId || undefined, tags };
}

/**
 * When GEN_E2E_METADATA=1, merge X-Gen-E2E-* headers with optional body.metadata
 * { e2eRunId, e2eTags }. Headers win when present.
 */
export function parseE2eFromRequest(req: Request, body: unknown): E2eContext {
  if (!isE2eMetadataEnabled()) return {};
  const fromBody = readBodyMetadata(body);
  const headerRun = req.get("x-gen-e2e-run")?.trim().slice(0, MAX_RUN_ID_LEN);
  const runId =
    headerRun && headerRun.length > 0 ? headerRun : fromBody.runId;

  const rawHeaderTags = req.get("x-gen-e2e-tags");
  const headerTags = rawHeaderTags !== undefined ? parseTagsHeader(rawHeaderTags) : undefined;
  const tags =
    headerTags !== undefined && headerTags.length > 0 ? headerTags : fromBody.tags;

  return {
    runId: runId || undefined,
    tags: tags && tags.length > 0 ? tags : undefined,
  };
}

export function applyE2eSpanAttributes(span: Span, ctx: E2eContext): void {
  if (!isE2eMetadataEnabled()) return;
  if (ctx.runId) span.setAttribute(GEN_ATTRS.E2E_RUN_ID, ctx.runId);
  if (ctx.tags?.length) span.setAttribute(GEN_ATTRS.E2E_TAGS, ctx.tags.join(","));
}

/** Attach e2e fields to hook observability metadata object (mutates target). */
export function mergeE2eIntoHookMetadata(
  target: Record<string, unknown>,
  ctx: E2eContext,
): void {
  if (!isE2eMetadataEnabled()) return;
  if (ctx.runId) target.e2e_run_id = ctx.runId;
  if (ctx.tags?.length) target.e2e_tags = ctx.tags.join(",");
}
