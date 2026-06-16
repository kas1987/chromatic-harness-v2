/**
 * NateClient — read-only access to the Nate knowledge SQLite DB.
 *
 * The Nate MCP server (scripts/nate/mcp_server.py) uses fastmcp over stdio, not
 * HTTP, so Gen queries the shared DB file directly via better-sqlite3 rather than
 * spawning a subprocess.  Connection is established lazily on first query and
 * re-opened with exponential backoff if the file is temporarily locked.
 *
 * Fail-open: every public method catches all errors and returns an empty array /
 * null so callers never need to guard for Nate being offline.
 */

import Database from "better-sqlite3";
import path from "path";
import fs from "fs";

export interface KnowledgeResult {
  source_type: "post" | "kit" | "guide";
  title: string;
  url: string;
  excerpt: string;
  published_at?: string;
  access_tier?: string;
  content_type?: string;
  tags?: string[];
  description?: string;
}

// Resolve DB path relative to this file's location:
// gen/src/services/ → D:\.04_Prism\scripts\nate\nate_knowledge.db
const DEFAULT_DB_PATH = path.resolve(
  __dirname,
  "../../../scripts/nate/nate_knowledge.db",
);

const MAX_RETRIES = 3;
const BASE_BACKOFF_MS = 250;

export class NateClient {
  private dbPath: string;
  private db: Database.Database | null = null;
  private available = false;
  private initAttempted = false;

  constructor(dbPath = DEFAULT_DB_PATH) {
    this.dbPath = dbPath;
  }

  // ---------------------------------------------------------------------------
  // Initialisation
  // ---------------------------------------------------------------------------

  private async initWithRetry(): Promise<void> {
    if (this.initAttempted) return;
    this.initAttempted = true;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        if (!fs.existsSync(this.dbPath)) {
          console.warn(
            `[nate-client] DB not found at ${this.dbPath} — Nate unavailable`,
          );
          return;
        }
        this.db = new Database(this.dbPath, { readonly: true, fileMustExist: true });
        this.available = true;
        console.log(`[nate-client] Nate client initialized — ${this.dbPath}`);
        return;
      } catch (err) {
        const wait = BASE_BACKOFF_MS * 2 ** attempt;
        console.warn(
          `[nate-client] Connection attempt ${attempt + 1} failed, retrying in ${wait}ms:`,
          (err as Error).message,
        );
        await new Promise((r) => setTimeout(r, wait));
      }
    }
    console.warn("[nate-client] Nate unavailable after all retries — fail-open");
  }

  async ensureReady(): Promise<boolean> {
    if (!this.initAttempted) await this.initWithRetry();
    return this.available;
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /**
   * Full-text search across posts, prompt kits, and guides.
   * Returns up to `limit` results ordered by recency (posts) then relevance.
   */
  async query(
    query: string,
    limit = 8,
    source: "" | "post" | "kit" | "guide" = "",
  ): Promise<KnowledgeResult[]> {
    try {
      const ready = await this.ensureReady();
      if (!ready || !this.db) return [];

      const results: KnowledgeResult[] = [];
      const db = this.db;

      const safeQuery = query.trim();
      if (!safeQuery) return [];

      if (source === "" || source === "post") {
        const rows = db
          .prepare(
            `SELECT p.title, p.url, p.published_at, p.tags, p.access_tier,
                    p.content_type,
                    snippet(posts_fts, 2, '', '', '...', 32) as excerpt
             FROM posts_fts
             JOIN posts p ON posts_fts.rowid = p.id
             WHERE posts_fts MATCH ?
             ORDER BY rank
             LIMIT ?`,
          )
          .all(safeQuery, limit) as any[];
        for (const r of rows) {
          results.push({
            source_type: "post",
            title: r.title ?? "",
            url: r.url ?? "",
            excerpt: r.excerpt ?? "",
            published_at: r.published_at ?? undefined,
            access_tier: r.access_tier ?? undefined,
            content_type: r.content_type ?? undefined,
            tags: JSON.parse(r.tags || "[]"),
          });
        }
      }

      if (source === "" || source === "kit") {
        const rows = db
          .prepare(
            `SELECT k.title, k.url, k.description,
                    snippet(prompt_kits_fts, 1, '', '', '...', 32) as excerpt
             FROM prompt_kits_fts
             JOIN prompt_kits k ON prompt_kits_fts.rowid = k.id
             WHERE prompt_kits_fts MATCH ?
             ORDER BY rank
             LIMIT ?`,
          )
          .all(safeQuery, limit) as any[];
        for (const r of rows) {
          results.push({
            source_type: "kit",
            title: r.title ?? "",
            url: r.url ?? "",
            excerpt: r.excerpt ?? "",
            description: r.description ?? undefined,
          });
        }
      }

      if (source === "" || source === "guide") {
        const rows = db
          .prepare(
            `SELECT g.title, g.url,
                    snippet(guides_fts, 1, '', '', '...', 32) as excerpt
             FROM guides_fts
             JOIN guides g ON guides_fts.rowid = g.id
             WHERE guides_fts MATCH ?
             ORDER BY rank
             LIMIT ?`,
          )
          .all(safeQuery, limit) as any[];
        for (const r of rows) {
          results.push({
            source_type: "guide",
            title: r.title ?? "",
            url: r.url ?? "",
            excerpt: r.excerpt ?? "",
          });
        }
      }

      // Sort posts by date, others follow; truncate to limit
      results.sort((a, b) =>
        (b.published_at ?? "").localeCompare(a.published_at ?? ""),
      );
      return results.slice(0, limit);
    } catch (err) {
      console.warn("[nate-client] query() failed (fail-open):", (err as Error).message);
      return [];
    }
  }

  /**
   * Lightweight health/status check — returns DB row counts or null if offline.
   */
  async ping(): Promise<{ posts: number; kits: number; guides: number } | null> {
    try {
      const ready = await this.ensureReady();
      if (!ready || !this.db) return null;
      const posts = (this.db.prepare("SELECT COUNT(*) as n FROM posts").get() as any).n as number;
      const kits = (this.db.prepare("SELECT COUNT(*) as n FROM prompt_kits").get() as any).n as number;
      const guides = (this.db.prepare("SELECT COUNT(*) as n FROM guides").get() as any).n as number;
      return { posts, kits, guides };
    } catch (err) {
      console.warn("[nate-client] ping() failed:", (err as Error).message);
      return null;
    }
  }

  close(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
      this.available = false;
      this.initAttempted = false;
    }
  }
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

let _instance: NateClient | null = null;

export function getNateClient(dbPath?: string): NateClient {
  if (!_instance) {
    _instance = new NateClient(dbPath);
  }
  return _instance;
}
