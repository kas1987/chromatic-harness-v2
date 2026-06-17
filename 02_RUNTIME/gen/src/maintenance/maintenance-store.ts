import Database from "better-sqlite3";
import { nanoid } from "nanoid";
import fs from "fs";
import path from "path";
import { readLatestOfflineValueAudit } from "./offline-value-audit";
import { loadRuntimeRoutingControls } from "../runtime/runtime-routing-controls";

export type MaintenanceSeverity = "low" | "medium" | "high" | "critical";
export type MaintenancePriority = "P0" | "P1" | "P2" | "P3" | "P4";
export type MaintenanceStatus = "open" | "in_progress" | "blocked" | "resolved" | "archived";
export type MaintenanceConfidence = "observed" | "strong_inference" | "weak_inference" | "unknown";

export interface MaintenanceRecord {
  id: string;
  createdAt: string;
  updatedAt: string;
  groupKey: string;
  category: string;
  title: string;
  summary?: string;
  severity: MaintenanceSeverity;
  priority: MaintenancePriority;
  status: MaintenanceStatus;
  confidence: MaintenanceConfidence;
  source?: string;
  sourceRef?: string;
  workflowId?: string;
  component?: string;
  environment?: string;
  ownerRole?: string;
  assignee?: string;
  dueDate?: string;
  sessionId?: string;
  taskId?: string;
  impactScore: number;
  effortScore: number;
  riskScore: number;
  evidenceJson: string;
  recommendationJson: string;
  tagsJson: string;
  isArchived: boolean;
  closedAt?: string;
}

export interface CreateMaintenanceRecordInput {
  groupKey: string;
  category: string;
  title: string;
  summary?: string;
  severity?: MaintenanceSeverity;
  priority?: MaintenancePriority;
  status?: MaintenanceStatus;
  confidence?: MaintenanceConfidence;
  source?: string;
  sourceRef?: string;
  workflowId?: string;
  component?: string;
  environment?: string;
  ownerRole?: string;
  assignee?: string;
  dueDate?: string;
  sessionId?: string;
  taskId?: string;
  impactScore?: number;
  effortScore?: number;
  riskScore?: number;
  evidenceJson?: string;
  recommendationJson?: string;
  tagsJson?: string;
}

export interface MaintenanceRecordFilters {
  groupKey?: string;
  status?: MaintenanceStatus;
  severity?: MaintenanceSeverity;
  priority?: MaintenancePriority;
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
}

export interface MaintenanceAnalyticsRow {
  recordId: string;
  computedAt: string;
  helpfulnessScore: number;
  timeCostScore: number;
  efficiencyScore: number;
  automationPotential: number;
  evidenceCount: number;
  recommendationCount: number;
}

export interface MaintenanceCorrelationInsight {
  dimension: "severity" | "status" | "confidence" | "category";
  value: string;
  count: number;
  avgHelpfulness: number;
  avgTimeCost: number;
  avgEfficiency: number;
  avgAutomationPotential: number;
}

export interface MaintenanceResponsePattern {
  responseTemplate: string;
  count: number;
  share: number;
  highConfidenceShare: number;
  automationReady: boolean;
}

export interface MaintenanceAutomationCandidate {
  recordId: string;
  title: string;
  category: string;
  status: string;
  confidence: string;
  automationPotential: number;
  supportingPattern?: string;
}

export interface MaintenanceIntelligenceReport {
  generatedAt: string;
  groupKey: string;
  totalRecords: number;
  analyticsTotal: number;
  avgHelpfulness: number;
  avgTimeCost: number;
  avgEfficiency: number;
  avgAutomationPotential: number;
  correlations: MaintenanceCorrelationInsight[];
  responsePatterns: MaintenanceResponsePattern[];
  automationCandidates: MaintenanceAutomationCandidate[];
  findings: string[];
  recommendedAutomations: string[];
}

export interface MaintenanceTrendSnapshot {
  groupKey: string;
  reviewerRole: string;
  latestDate: string | null;
  previousDate: string | null;
  latest: {
    avgHelpfulness: number;
    avgTimeCost: number;
    avgEfficiency: number;
    avgAutomationPotential: number;
    automationCandidates: number;
  };
  previous: {
    avgHelpfulness: number;
    avgTimeCost: number;
    avgEfficiency: number;
    avgAutomationPotential: number;
    automationCandidates: number;
  } | null;
  delta: {
    avgHelpfulness: number;
    avgTimeCost: number;
    avgEfficiency: number;
    avgAutomationPotential: number;
    automationCandidates: number;
  };
}

export interface DailyReviewExportResult {
  reviewId: string;
  reviewDate: string;
  groupKey: string;
  reviewerRole: string;
  directory: string;
  summaryPath: string;
  intelligencePath: string;
  independentSummaryPath: string;
  independentJsonPath: string;
  bytesWritten: number;
}

export interface IndependentEvaluationSummary {
  generatedAt: string;
  reviewDate: string;
  groupKey: string;
  hotmd: {
    rootsScanned: number;
    totalFiles: number;
    fallbackFiles: number;
    fallbackRate: number;
  };
  budget: {
    totalTokens: number;
    externalCalls: number;
    stoppedTasks: number;
    flaggedCostAccuracy: number;
    avgCostAccuracyPct: number;
  };
  degradation: {
    current7dSuccessRate: number;
    previous7dSuccessRate: number;
    deltaSuccessRate: number;
    isDegrading: boolean;
  };
  drift: {
    mismatchCount24h: number;
    decisionCount24h: number;
    mismatchRate24h: number;
  };
  offlineAudit: {
    enabled: boolean;
    available: boolean;
    generatedAt?: string;
    model: string;
    sampledFiles: number;
    successCount: number;
    failureCount: number;
    avgConfidence: number;
    lowConfidenceCount: number;
  };
  findings: string[];
}

export interface WeeklyIndependentRollup {
  generatedAt: string;
  groupKey: string;
  reviewerRole: string;
  endDate: string;
  windows: {
    recentDays: number;
    priorDays: number;
  };
  recent: {
    avgEfficiency: number;
    avgAutomationPotential: number;
    avgHotmdFallbackRate: number;
    avgRoutingMismatchRate: number;
    avgDegradationDelta: number;
    avgOfflineConfidence: number;
    findingsCount: number;
  };
  prior: {
    avgEfficiency: number;
    avgAutomationPotential: number;
    avgHotmdFallbackRate: number;
    avgRoutingMismatchRate: number;
    avgDegradationDelta: number;
    avgOfflineConfidence: number;
    findingsCount: number;
  };
  delta: {
    avgEfficiency: number;
    avgAutomationPotential: number;
    avgHotmdFallbackRate: number;
    avgRoutingMismatchRate: number;
    avgDegradationDelta: number;
    avgOfflineConfidence: number;
    findingsCount: number;
  };
  findings: string[];
}

export interface MaintenanceDailyReview {
  id: string;
  reviewDate: string;
  groupKey: string;
  reviewerRole: string;
  generatedAt: string;
  summaryMarkdown: string;
  intelligenceJson: string;
}

type AnalyticsJoinRow = {
  record_id: string;
  title: string;
  category: string;
  severity: string;
  status: string;
  confidence: string;
  recommendation_json: string;
  helpfulness_score: number;
  time_cost_score: number;
  efficiency_score: number;
  automation_potential: number;
};

export class MaintenanceStore {
  constructor(private db: Database.Database) {
    this.initSchema();
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS maintenance_records (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        group_key TEXT NOT NULL,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        severity TEXT NOT NULL DEFAULT 'medium',
        priority TEXT NOT NULL DEFAULT 'P2',
        status TEXT NOT NULL DEFAULT 'open',
        confidence TEXT NOT NULL DEFAULT 'unknown',
        source TEXT,
        source_ref TEXT,
        workflow_id TEXT,
        component TEXT,
        environment TEXT,
        owner_role TEXT,
        assignee TEXT,
        due_date TEXT,
        session_id TEXT,
        task_id TEXT,
        impact_score REAL NOT NULL DEFAULT 0,
        effort_score REAL NOT NULL DEFAULT 0,
        risk_score REAL NOT NULL DEFAULT 0,
        evidence_json TEXT NOT NULL DEFAULT '[]',
        recommendation_json TEXT NOT NULL DEFAULT '[]',
        tags_json TEXT NOT NULL DEFAULT '[]',
        is_archived INTEGER NOT NULL DEFAULT 0,
        closed_at TEXT
      );

      CREATE TABLE IF NOT EXISTS maintenance_analytics (
        id TEXT PRIMARY KEY,
        record_id TEXT NOT NULL,
        computed_at TEXT NOT NULL,
        helpfulness_score REAL NOT NULL,
        time_cost_score REAL NOT NULL,
        efficiency_score REAL NOT NULL,
        automation_potential REAL NOT NULL,
        evidence_count INTEGER NOT NULL DEFAULT 0,
        recommendation_count INTEGER NOT NULL DEFAULT 0,
        UNIQUE(record_id)
      );

      CREATE TABLE IF NOT EXISTS maintenance_daily_reviews (
        id TEXT PRIMARY KEY,
        review_date TEXT NOT NULL,
        group_key TEXT NOT NULL,
        reviewer_role TEXT NOT NULL DEFAULT 'architecture_director',
        generated_at TEXT NOT NULL,
        summary_markdown TEXT NOT NULL,
        intelligence_json TEXT NOT NULL,
        UNIQUE(review_date, group_key, reviewer_role)
      );

      CREATE INDEX IF NOT EXISTS idx_maintenance_group_status
        ON maintenance_records(group_key, status, priority);
      CREATE INDEX IF NOT EXISTS idx_maintenance_severity
        ON maintenance_records(severity, priority);
      CREATE INDEX IF NOT EXISTS idx_maintenance_updated
        ON maintenance_records(updated_at DESC);
      CREATE INDEX IF NOT EXISTS idx_maintenance_component
        ON maintenance_records(component);
      CREATE INDEX IF NOT EXISTS idx_maintenance_workflow
        ON maintenance_records(workflow_id);
      CREATE INDEX IF NOT EXISTS idx_maintenance_analytics_efficiency
        ON maintenance_analytics(efficiency_score DESC);
      CREATE INDEX IF NOT EXISTS idx_maintenance_daily_reviews_date
        ON maintenance_daily_reviews(review_date DESC, group_key, reviewer_role);
    `);

    this.migrateSchema();
  }

  private migrateSchema(): void {
    const cols = this.db.prepare("PRAGMA table_info(maintenance_records)").all() as { name: string }[];
    const names = new Set(cols.map((c) => c.name));
    const add = (name: string, sqlType: string) => {
      if (!names.has(name)) {
        this.db.exec(`ALTER TABLE maintenance_records ADD COLUMN ${name} ${sqlType}`);
      }
    };

    // Keep schema evolvable and EAST/ease-friendly for analytics use cases.
    add("source", "TEXT");
    add("source_ref", "TEXT");
    add("workflow_id", "TEXT");
    add("component", "TEXT");
    add("environment", "TEXT");
    add("owner_role", "TEXT");
    add("assignee", "TEXT");
    add("due_date", "TEXT");
    add("session_id", "TEXT");
    add("task_id", "TEXT");
    add("impact_score", "REAL NOT NULL DEFAULT 0");
    add("effort_score", "REAL NOT NULL DEFAULT 0");
    add("risk_score", "REAL NOT NULL DEFAULT 0");
    add("evidence_json", "TEXT NOT NULL DEFAULT '[]'");
    add("recommendation_json", "TEXT NOT NULL DEFAULT '[]'");
    add("tags_json", "TEXT NOT NULL DEFAULT '[]'");
    add("is_archived", "INTEGER NOT NULL DEFAULT 0");
    add("closed_at", "TEXT");
  }

  createRecord(input: CreateMaintenanceRecordInput): MaintenanceRecord {
    const now = new Date().toISOString();
    const id = nanoid();

    this.db
      .prepare(
        `INSERT INTO maintenance_records (
          id, created_at, updated_at, group_key, category, title, summary,
          severity, priority, status, confidence,
          source, source_ref, workflow_id, component, environment,
          owner_role, assignee, due_date, session_id, task_id,
          impact_score, effort_score, risk_score,
          evidence_json, recommendation_json, tags_json,
          is_archived, closed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(
        id,
        now,
        now,
        input.groupKey,
        input.category,
        input.title,
        input.summary ?? null,
        input.severity ?? "medium",
        input.priority ?? "P2",
        input.status ?? "open",
        input.confidence ?? "unknown",
        input.source ?? null,
        input.sourceRef ?? null,
        input.workflowId ?? null,
        input.component ?? null,
        input.environment ?? null,
        input.ownerRole ?? null,
        input.assignee ?? null,
        input.dueDate ?? null,
        input.sessionId ?? null,
        input.taskId ?? null,
        input.impactScore ?? 0,
        input.effortScore ?? 0,
        input.riskScore ?? 0,
        input.evidenceJson ?? "[]",
        input.recommendationJson ?? "[]",
        input.tagsJson ?? "[]",
        0,
        null,
      );

    const created = this.getById(id);
    if (!created) {
      throw new Error("Failed to create maintenance record");
    }
    return created;
  }

  updateRecord(id: string, patch: Partial<CreateMaintenanceRecordInput> & { status?: MaintenanceStatus; isArchived?: boolean }): MaintenanceRecord | null {
    const existing = this.getById(id);
    if (!existing) return null;

    const nextStatus = patch.status ?? existing.status;
    const isArchived = patch.isArchived ?? existing.isArchived;
    const closedAt = nextStatus === "resolved" ? new Date().toISOString() : existing.closedAt;

    this.db
      .prepare(
        `UPDATE maintenance_records SET
          updated_at = ?,
          group_key = ?,
          category = ?,
          title = ?,
          summary = ?,
          severity = ?,
          priority = ?,
          status = ?,
          confidence = ?,
          source = ?,
          source_ref = ?,
          workflow_id = ?,
          component = ?,
          environment = ?,
          owner_role = ?,
          assignee = ?,
          due_date = ?,
          session_id = ?,
          task_id = ?,
          impact_score = ?,
          effort_score = ?,
          risk_score = ?,
          evidence_json = ?,
          recommendation_json = ?,
          tags_json = ?,
          is_archived = ?,
          closed_at = ?
        WHERE id = ?`
      )
      .run(
        new Date().toISOString(),
        patch.groupKey ?? existing.groupKey,
        patch.category ?? existing.category,
        patch.title ?? existing.title,
        patch.summary ?? existing.summary ?? null,
        patch.severity ?? existing.severity,
        patch.priority ?? existing.priority,
        nextStatus,
        patch.confidence ?? existing.confidence,
        patch.source ?? existing.source ?? null,
        patch.sourceRef ?? existing.sourceRef ?? null,
        patch.workflowId ?? existing.workflowId ?? null,
        patch.component ?? existing.component ?? null,
        patch.environment ?? existing.environment ?? null,
        patch.ownerRole ?? existing.ownerRole ?? null,
        patch.assignee ?? existing.assignee ?? null,
        patch.dueDate ?? existing.dueDate ?? null,
        patch.sessionId ?? existing.sessionId ?? null,
        patch.taskId ?? existing.taskId ?? null,
        patch.impactScore ?? existing.impactScore,
        patch.effortScore ?? existing.effortScore,
        patch.riskScore ?? existing.riskScore,
        patch.evidenceJson ?? existing.evidenceJson,
        patch.recommendationJson ?? existing.recommendationJson,
        patch.tagsJson ?? existing.tagsJson,
        isArchived ? 1 : 0,
        closedAt ?? null,
        id,
      );

    return this.getById(id);
  }

  getById(id: string): MaintenanceRecord | null {
    const row = this.db
      .prepare("SELECT * FROM maintenance_records WHERE id = ?")
      .get(id) as Record<string, unknown> | undefined;

    if (!row) return null;
    return rowToRecord(row);
  }

  listRecords(filters: MaintenanceRecordFilters = {}): MaintenanceRecord[] {
    const where: string[] = [];
    const params: unknown[] = [];

    if (filters.groupKey) {
      where.push("group_key = ?");
      params.push(filters.groupKey);
    }
    if (filters.status) {
      where.push("status = ?");
      params.push(filters.status);
    }
    if (filters.severity) {
      where.push("severity = ?");
      params.push(filters.severity);
    }
    if (filters.priority) {
      where.push("priority = ?");
      params.push(filters.priority);
    }
    if (!filters.includeArchived) {
      where.push("is_archived = 0");
    }

    const limit = Math.max(1, Math.min(filters.limit ?? 100, 500));
    const offset = Math.max(0, filters.offset ?? 0);

    const sql = `
      SELECT *
      FROM maintenance_records
      ${where.length > 0 ? `WHERE ${where.join(" AND ")}` : ""}
      ORDER BY updated_at DESC
      LIMIT ? OFFSET ?
    `;

    const rows = this.db.prepare(sql).all(...params, limit, offset) as Record<string, unknown>[];
    return rows.map(rowToRecord);
  }

  groupSummary(groupKey?: string): Array<{ groupKey: string; status: string; count: number }> {
    const sql = groupKey
      ? `
          SELECT group_key, status, COUNT(*) as count
          FROM maintenance_records
          WHERE group_key = ?
          GROUP BY group_key, status
          ORDER BY group_key, status
        `
      : `
          SELECT group_key, status, COUNT(*) as count
          FROM maintenance_records
          GROUP BY group_key, status
          ORDER BY group_key, status
        `;

    const rows = groupKey
      ? (this.db.prepare(sql).all(groupKey) as Array<{ group_key: string; status: string; count: number }>)
      : (this.db.prepare(sql).all() as Array<{ group_key: string; status: string; count: number }>);

    return rows.map((r) => ({
      groupKey: r.group_key,
      status: r.status,
      count: r.count,
    }));
  }

  tableColumns(): string[] {
    const cols = this.db.prepare("PRAGMA table_info(maintenance_records)").all() as Array<{ name: string }>;
    return cols.map((c) => c.name);
  }

  recomputeAnalytics(groupKey?: string): { updated: number } {
    const rows = this.listRecords({
      groupKey,
      includeArchived: true,
      limit: 500,
      offset: 0,
    });

    let updated = 0;
    for (const r of rows) {
      const evidenceCount = safeJsonArrayLength(r.evidenceJson);
      const recommendationCount = safeJsonArrayLength(r.recommendationJson);

      // Helpfulness favors high impact/risk plus concrete recommendations.
      const helpfulnessRaw =
        r.impactScore * 0.45 +
        r.riskScore * 0.35 +
        Math.min(10, recommendationCount * 2) * 0.20;

      // Time cost uses effort score plus evidence processing overhead.
      const timeCostRaw =
        r.effortScore * 0.75 +
        Math.min(10, evidenceCount * 0.8) * 0.25;

      const helpfulnessScore = round2(clamp(helpfulnessRaw, 0, 10));
      const timeCostScore = round2(clamp(timeCostRaw, 0.1, 10));
      const efficiencyScore = round2(clamp((helpfulnessScore / timeCostScore) * 5, 0, 10));

      // Automation potential increases when evidence is structured and effort is high.
      const automationPotential = round2(
        clamp(
          (evidenceCount >= 3 ? 3.5 : evidenceCount * 1.1) +
            Math.min(4, r.effortScore * 0.4) +
            (r.confidence === "observed" || r.confidence === "strong_inference" ? 2.0 : 0.8),
          0,
          10,
        ),
      );

      this.db
        .prepare(
          `INSERT INTO maintenance_analytics (
            id, record_id, computed_at, helpfulness_score, time_cost_score,
            efficiency_score, automation_potential, evidence_count, recommendation_count
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT(record_id) DO UPDATE SET
            computed_at = excluded.computed_at,
            helpfulness_score = excluded.helpfulness_score,
            time_cost_score = excluded.time_cost_score,
            efficiency_score = excluded.efficiency_score,
            automation_potential = excluded.automation_potential,
            evidence_count = excluded.evidence_count,
            recommendation_count = excluded.recommendation_count`,
        )
        .run(
          nanoid(),
          r.id,
          new Date().toISOString(),
          helpfulnessScore,
          timeCostScore,
          efficiencyScore,
          automationPotential,
          evidenceCount,
          recommendationCount,
        );
      updated += 1;
    }

    return { updated };
  }

  analyticsOverview(groupKey?: string): {
    total: number;
    avgHelpfulness: number;
    avgTimeCost: number;
    avgEfficiency: number;
    avgAutomationPotential: number;
    topEfficient: MaintenanceAnalyticsRow[];
    topTimeConsuming: MaintenanceAnalyticsRow[];
  } {
    const whereSql = groupKey ? "WHERE mr.group_key = ?" : "";
    const params = groupKey ? [groupKey] : [];

    const agg = this.db
      .prepare(
        `SELECT
          COUNT(*) AS total,
          AVG(ma.helpfulness_score) AS avg_helpfulness,
          AVG(ma.time_cost_score) AS avg_time_cost,
          AVG(ma.efficiency_score) AS avg_efficiency,
          AVG(ma.automation_potential) AS avg_automation
         FROM maintenance_analytics ma
         JOIN maintenance_records mr ON mr.id = ma.record_id
         ${whereSql}`,
      )
      .get(...params) as {
      total: number;
      avg_helpfulness: number | null;
      avg_time_cost: number | null;
      avg_efficiency: number | null;
      avg_automation: number | null;
    };

    const topEfficientRows = this.db
      .prepare(
        `SELECT ma.record_id, ma.computed_at, ma.helpfulness_score, ma.time_cost_score,
                ma.efficiency_score, ma.automation_potential, ma.evidence_count, ma.recommendation_count
         FROM maintenance_analytics ma
         JOIN maintenance_records mr ON mr.id = ma.record_id
         ${whereSql}
         ORDER BY ma.efficiency_score DESC, ma.helpfulness_score DESC
         LIMIT 5`,
      )
      .all(...params) as Array<Record<string, unknown>>;

    const topTimeRows = this.db
      .prepare(
        `SELECT ma.record_id, ma.computed_at, ma.helpfulness_score, ma.time_cost_score,
                ma.efficiency_score, ma.automation_potential, ma.evidence_count, ma.recommendation_count
         FROM maintenance_analytics ma
         JOIN maintenance_records mr ON mr.id = ma.record_id
         ${whereSql}
         ORDER BY ma.time_cost_score DESC, ma.helpfulness_score ASC
         LIMIT 5`,
      )
      .all(...params) as Array<Record<string, unknown>>;

    return {
      total: agg.total ?? 0,
      avgHelpfulness: round2(Number(agg.avg_helpfulness ?? 0)),
      avgTimeCost: round2(Number(agg.avg_time_cost ?? 0)),
      avgEfficiency: round2(Number(agg.avg_efficiency ?? 0)),
      avgAutomationPotential: round2(Number(agg.avg_automation ?? 0)),
      topEfficient: topEfficientRows.map(rowToAnalyticsRow),
      topTimeConsuming: topTimeRows.map(rowToAnalyticsRow),
    };
  }

  getIntelligenceReport(groupKey = "architecture"): MaintenanceIntelligenceReport {
    const joined = this.getAnalyticsJoinRows(groupKey);
    const responsePatterns = this.computeResponsePatterns(joined);
    const correlations = this.computeCorrelations(joined);
    const automationCandidates = this.computeAutomationCandidates(joined, responsePatterns);
    const overview = this.analyticsOverview(groupKey);
    const findings = this.buildFindings(overview, correlations, responsePatterns, automationCandidates);
    const recommendedAutomations = responsePatterns
      .filter((p) => p.automationReady)
      .slice(0, 5)
      .map((p) => `Automate response template '${p.responseTemplate}' (${p.count} uses, ${Math.round(p.highConfidenceShare * 100)}% high-confidence)`);

    return {
      generatedAt: new Date().toISOString(),
      groupKey,
      totalRecords: this.listRecords({ groupKey, includeArchived: true, limit: 500, offset: 0 }).length,
      analyticsTotal: overview.total,
      avgHelpfulness: overview.avgHelpfulness,
      avgTimeCost: overview.avgTimeCost,
      avgEfficiency: overview.avgEfficiency,
      avgAutomationPotential: overview.avgAutomationPotential,
      correlations,
      responsePatterns,
      automationCandidates,
      findings,
      recommendedAutomations,
    };
  }

  generateDailyReview(groupKey = "architecture", reviewerRole = "architecture_director", reviewDate?: string): MaintenanceDailyReview {
    const date = reviewDate ?? new Date().toISOString().split("T")[0];
    this.recomputeAnalytics(groupKey);
    const intelligence = this.getIntelligenceReport(groupKey);
    const thresholdResult = this.applyAutomationThresholdRules(groupKey, intelligence);
    const independent = this.getIndependentEvaluation(groupKey, date);
    const independentThresholdResult = this.applyIndependentThresholdRules(groupKey, independent);

    const intelligenceWithRules: MaintenanceIntelligenceReport = {
      ...intelligence,
      findings: [
        ...intelligence.findings,
        ...(thresholdResult.created > 0
          ? [`${thresholdResult.created} automation-threshold maintenance records were created automatically.`]
          : []),
        ...(independentThresholdResult.created > 0
          ? [`${independentThresholdResult.created} independent-evaluation threshold records were created automatically.`]
          : []),
      ],
    };
    const summaryMarkdown = this.renderDailySummaryMarkdown(date, reviewerRole, intelligenceWithRules);
    const now = new Date().toISOString();
    const id = nanoid();

    this.db
      .prepare(
        `INSERT INTO maintenance_daily_reviews (
          id, review_date, group_key, reviewer_role, generated_at, summary_markdown, intelligence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(review_date, group_key, reviewer_role) DO UPDATE SET
          generated_at = excluded.generated_at,
          summary_markdown = excluded.summary_markdown,
          intelligence_json = excluded.intelligence_json`,
      )
      .run(
        id,
        date,
        groupKey,
        reviewerRole,
        now,
        summaryMarkdown,
        JSON.stringify(intelligenceWithRules),
      );

    const row = this.db
      .prepare(
        `SELECT * FROM maintenance_daily_reviews
         WHERE review_date = ? AND group_key = ? AND reviewer_role = ?
         LIMIT 1`,
      )
      .get(date, groupKey, reviewerRole) as Record<string, unknown> | undefined;

    if (!row) {
      throw new Error("Failed to load generated daily review");
    }

    return rowToDailyReview(row);
  }

  ensureTodayReview(groupKey = "architecture", reviewerRole = "architecture_director"): MaintenanceDailyReview {
    const date = new Date().toISOString().split("T")[0];
    const existing = this.db
      .prepare(
        `SELECT * FROM maintenance_daily_reviews
         WHERE review_date = ? AND group_key = ? AND reviewer_role = ?
         LIMIT 1`,
      )
      .get(date, groupKey, reviewerRole) as Record<string, unknown> | undefined;

    if (existing) {
      return rowToDailyReview(existing);
    }

    return this.generateDailyReview(groupKey, reviewerRole, date);
  }

  listDailyReviews(groupKey = "architecture", reviewerRole = "architecture_director", limit = 14): MaintenanceDailyReview[] {
    const cappedLimit = Math.max(1, Math.min(limit, 90));
    const rows = this.db
      .prepare(
        `SELECT * FROM maintenance_daily_reviews
         WHERE group_key = ? AND reviewer_role = ?
         ORDER BY review_date DESC
         LIMIT ?`,
      )
      .all(groupKey, reviewerRole, cappedLimit) as Array<Record<string, unknown>>;

    return rows.map(rowToDailyReview);
  }

  intelligenceTrends(groupKey = "architecture", reviewerRole = "architecture_director"): MaintenanceTrendSnapshot {
    const reviews = this.listDailyReviews(groupKey, reviewerRole, 2);
    const latest = reviews[0] ?? null;
    const previous = reviews[1] ?? null;

    const latestReport = latest ? parseIntelligenceReport(latest.intelligenceJson) : null;
    const previousReport = previous ? parseIntelligenceReport(previous.intelligenceJson) : null;

    const latestMetrics = {
      avgHelpfulness: latestReport?.avgHelpfulness ?? 0,
      avgTimeCost: latestReport?.avgTimeCost ?? 0,
      avgEfficiency: latestReport?.avgEfficiency ?? 0,
      avgAutomationPotential: latestReport?.avgAutomationPotential ?? 0,
      automationCandidates: latestReport?.automationCandidates.length ?? 0,
    };

    const previousMetrics = previousReport
      ? {
          avgHelpfulness: previousReport.avgHelpfulness,
          avgTimeCost: previousReport.avgTimeCost,
          avgEfficiency: previousReport.avgEfficiency,
          avgAutomationPotential: previousReport.avgAutomationPotential,
          automationCandidates: previousReport.automationCandidates.length,
        }
      : null;

    return {
      groupKey,
      reviewerRole,
      latestDate: latest?.reviewDate ?? null,
      previousDate: previous?.reviewDate ?? null,
      latest: latestMetrics,
      previous: previousMetrics,
      delta: {
        avgHelpfulness: round2(latestMetrics.avgHelpfulness - (previousMetrics?.avgHelpfulness ?? 0)),
        avgTimeCost: round2(latestMetrics.avgTimeCost - (previousMetrics?.avgTimeCost ?? 0)),
        avgEfficiency: round2(latestMetrics.avgEfficiency - (previousMetrics?.avgEfficiency ?? 0)),
        avgAutomationPotential: round2(latestMetrics.avgAutomationPotential - (previousMetrics?.avgAutomationPotential ?? 0)),
        automationCandidates: latestMetrics.automationCandidates - (previousMetrics?.automationCandidates ?? 0),
      },
    };
  }

  exportDailyReviewArtifact(groupKey = "architecture", reviewerRole = "architecture_director", reviewDate?: string): DailyReviewExportResult {
    const targetDate = reviewDate ?? new Date().toISOString().split("T")[0];

    const row = this.db
      .prepare(
        `SELECT * FROM maintenance_daily_reviews
         WHERE review_date = ? AND group_key = ? AND reviewer_role = ?
         LIMIT 1`,
      )
      .get(targetDate, groupKey, reviewerRole) as Record<string, unknown> | undefined;

    if (!row) {
      throw new Error(`No daily review found for ${targetDate} (${groupKey}/${reviewerRole})`);
    }

    const review = rowToDailyReview(row);
    const root = path.resolve(__dirname, "../../..", ".agents", "director-reviews", groupKey, targetDate);
    fs.mkdirSync(root, { recursive: true });

    const summaryPath = path.join(root, `${reviewerRole}.summary.md`);
    const intelligencePath = path.join(root, `${reviewerRole}.intelligence.json`);
    const independentSummaryPath = path.join(root, `${reviewerRole}.independent-eval.md`);
    const independentJsonPath = path.join(root, `${reviewerRole}.independent-eval.json`);

    const independent = this.getIndependentEvaluation(groupKey, review.reviewDate);
    const independentMarkdown = this.renderIndependentEvaluationMarkdown(independent);

    fs.writeFileSync(summaryPath, review.summaryMarkdown, "utf-8");
    fs.writeFileSync(intelligencePath, review.intelligenceJson, "utf-8");
    fs.writeFileSync(independentSummaryPath, independentMarkdown, "utf-8");
    fs.writeFileSync(independentJsonPath, JSON.stringify(independent, null, 2), "utf-8");

    const bytesWritten =
      Buffer.byteLength(review.summaryMarkdown, "utf-8") +
      Buffer.byteLength(review.intelligenceJson, "utf-8") +
      Buffer.byteLength(independentMarkdown, "utf-8") +
      Buffer.byteLength(JSON.stringify(independent), "utf-8");
    return {
      reviewId: review.id,
      reviewDate: review.reviewDate,
      groupKey: review.groupKey,
      reviewerRole: review.reviewerRole,
      directory: root,
      summaryPath,
      intelligencePath,
      independentSummaryPath,
      independentJsonPath,
      bytesWritten,
    };
  }

  getIndependentEvaluation(groupKey = "architecture", reviewDate?: string): IndependentEvaluationSummary {
    const date = reviewDate ?? new Date().toISOString().split("T")[0];
    const hotmd = this.collectHotMdSignals();
    const budget = this.collectBudgetSignals();
    const degradation = this.collectDegradationSignals();
    const drift = this.collectDriftSignals();
    const offlineAudit = this.collectOfflineAuditSignals();

    const findings: string[] = [];
    if (hotmd.fallbackRate >= 0.25) {
      findings.push(`HotMD fallback queue is elevated at ${Math.round(hotmd.fallbackRate * 100)}%.`);
    }
    if (budget.stoppedTasks > 0) {
      findings.push(`${budget.stoppedTasks} budget-stopped task(s) detected; review token/call ceilings.`);
    }
    if (budget.flaggedCostAccuracy > 0) {
      findings.push(`${budget.flaggedCostAccuracy} cost-accuracy records are flagged (>20% estimate error).`);
    }
    if (degradation.isDegrading) {
      findings.push(`Tool outcome success rate is degrading (${round2(degradation.deltaSuccessRate * 100)} pts vs prior 7d).`);
    }
    if (drift.mismatchRate24h >= 0.2 && drift.decisionCount24h > 0) {
      findings.push(`Routing drift is high at ${Math.round(drift.mismatchRate24h * 100)}% mismatch (24h).`);
    }
    if (offlineAudit.available && offlineAudit.lowConfidenceCount > 0) {
      findings.push(
        `Offline audit detected ${offlineAudit.lowConfidenceCount} low-confidence sample(s) at avg confidence ${round2(offlineAudit.avgConfidence * 100)}%.`,
      );
    }
    if (!offlineAudit.available) {
      findings.push("Offline value-chain audit artifact is missing; run the audit loop to validate local-model confidence.");
    }
    if (findings.length === 0) {
      findings.push("Independent evaluation shows stable budget, routing, and knowledge quality signals.");
    }

    return {
      generatedAt: new Date().toISOString(),
      reviewDate: date,
      groupKey,
      hotmd,
      budget,
      degradation,
      drift,
      offlineAudit,
      findings,
    };
  }

  getWeeklyIndependentRollup(
    groupKey = "architecture",
    reviewerRole = "architecture_director",
    endDate?: string,
  ): WeeklyIndependentRollup {
    const targetEndDate = endDate ?? new Date().toISOString().split("T")[0];
    const reviews = this.listDailyReviews(groupKey, reviewerRole, 14).reverse();
    const dated = reviews
      .filter((r) => r.reviewDate <= targetEndDate)
      .map((r) => ({ review: r, report: parseIntelligenceReport(r.intelligenceJson) }))
      .filter((x) => Boolean(x.report)) as Array<{ review: MaintenanceDailyReview; report: MaintenanceIntelligenceReport }>;

    const recent = dated.slice(-7);
    const prior = dated.slice(Math.max(0, dated.length - 14), Math.max(0, dated.length - 7));

    const summarize = (rows: Array<{ review: MaintenanceDailyReview; report: MaintenanceIntelligenceReport }>) => {
      if (rows.length === 0) {
        return {
          avgEfficiency: 0,
          avgAutomationPotential: 0,
          avgHotmdFallbackRate: 0,
          avgRoutingMismatchRate: 0,
          avgDegradationDelta: 0,
          avgOfflineConfidence: 0,
          findingsCount: 0,
        };
      }

      let eff = 0;
      let auto = 0;
      let fallback = 0;
      let drift = 0;
      let degrad = 0;
      let offlineConfidence = 0;
      let offlineCount = 0;
      let findings = 0;
      for (const item of rows) {
        eff += Number(item.report.avgEfficiency ?? 0);
        auto += Number(item.report.avgAutomationPotential ?? 0);
        const indep = this.getIndependentEvaluation(groupKey, item.review.reviewDate);
        fallback += Number(indep.hotmd.fallbackRate ?? 0);
        drift += Number(indep.drift.mismatchRate24h ?? 0);
        degrad += Number(indep.degradation.deltaSuccessRate ?? 0);
        if (indep.offlineAudit.available) {
          offlineConfidence += Number(indep.offlineAudit.avgConfidence ?? 0);
          offlineCount += 1;
        }
        findings += indep.findings.length;
      }

      return {
        avgEfficiency: round2(eff / rows.length),
        avgAutomationPotential: round2(auto / rows.length),
        avgHotmdFallbackRate: round2(fallback / rows.length),
        avgRoutingMismatchRate: round2(drift / rows.length),
        avgDegradationDelta: round2(degrad / rows.length),
        avgOfflineConfidence: round2(offlineCount > 0 ? offlineConfidence / offlineCount : 0),
        findingsCount: findings,
      };
    };

    const recentStats = summarize(recent);
    const priorStats = summarize(prior);

    const findings: string[] = [];
    if (recentStats.avgHotmdFallbackRate > priorStats.avgHotmdFallbackRate + 0.05) {
      findings.push("HotMD fallback rate drifted up week-over-week.");
    }
    if (recentStats.avgRoutingMismatchRate > priorStats.avgRoutingMismatchRate + 0.05) {
      findings.push("Routing mismatch drift increased week-over-week.");
    }
    if (recentStats.avgDegradationDelta < priorStats.avgDegradationDelta - 0.03) {
      findings.push("Skill/outcome degradation trend worsened week-over-week.");
    }
    if (recentStats.avgAutomationPotential < priorStats.avgAutomationPotential - 0.2) {
      findings.push("Automation potential dropped versus prior window.");
    }
    if (recentStats.avgOfflineConfidence < priorStats.avgOfflineConfidence - 0.05) {
      findings.push("Offline confidence declined week-over-week.");
    }
    if (findings.length === 0) {
      findings.push("Weekly independent-evaluation trend is stable or improving.");
    }

    return {
      generatedAt: new Date().toISOString(),
      groupKey,
      reviewerRole,
      endDate: targetEndDate,
      windows: {
        recentDays: recent.length,
        priorDays: prior.length,
      },
      recent: recentStats,
      prior: priorStats,
      delta: {
        avgEfficiency: round2(recentStats.avgEfficiency - priorStats.avgEfficiency),
        avgAutomationPotential: round2(recentStats.avgAutomationPotential - priorStats.avgAutomationPotential),
        avgHotmdFallbackRate: round2(recentStats.avgHotmdFallbackRate - priorStats.avgHotmdFallbackRate),
        avgRoutingMismatchRate: round2(recentStats.avgRoutingMismatchRate - priorStats.avgRoutingMismatchRate),
        avgDegradationDelta: round2(recentStats.avgDegradationDelta - priorStats.avgDegradationDelta),
        avgOfflineConfidence: round2(recentStats.avgOfflineConfidence - priorStats.avgOfflineConfidence),
        findingsCount: recentStats.findingsCount - priorStats.findingsCount,
      },
      findings,
    };
  }

  exportWeeklyIndependentRollupArtifact(
    groupKey = "architecture",
    reviewerRole = "architecture_director",
    endDate?: string,
  ): { directory: string; summaryPath: string; jsonPath: string; endDate: string; bytesWritten: number } {
    const rollup = this.getWeeklyIndependentRollup(groupKey, reviewerRole, endDate);
    const root = path.resolve(__dirname, "../../..", ".agents", "director-reviews", groupKey, "weekly", rollup.endDate);
    fs.mkdirSync(root, { recursive: true });

    const summaryPath = path.join(root, `${reviewerRole}.independent-weekly.md`);
    const jsonPath = path.join(root, `${reviewerRole}.independent-weekly.json`);
    const markdown = this.renderWeeklyRollupMarkdown(rollup);
    const raw = JSON.stringify(rollup, null, 2);

    fs.writeFileSync(summaryPath, markdown, "utf-8");
    fs.writeFileSync(jsonPath, raw, "utf-8");

    return {
      directory: root,
      summaryPath,
      jsonPath,
      endDate: rollup.endDate,
      bytesWritten: Buffer.byteLength(markdown, "utf-8") + Buffer.byteLength(raw, "utf-8"),
    };
  }

  private getAnalyticsJoinRows(groupKey: string): AnalyticsJoinRow[] {
    return this.db
      .prepare(
        `SELECT
          mr.id AS record_id,
          mr.title AS title,
          mr.category AS category,
          mr.severity AS severity,
          mr.status AS status,
          mr.confidence AS confidence,
          mr.recommendation_json AS recommendation_json,
          ma.helpfulness_score AS helpfulness_score,
          ma.time_cost_score AS time_cost_score,
          ma.efficiency_score AS efficiency_score,
          ma.automation_potential AS automation_potential
         FROM maintenance_records mr
         JOIN maintenance_analytics ma ON ma.record_id = mr.id
         WHERE mr.group_key = ?`,
      )
      .all(groupKey) as AnalyticsJoinRow[];
  }

  private computeCorrelations(rows: AnalyticsJoinRow[]): MaintenanceCorrelationInsight[] {
    type Bucket = {
      count: number;
      helpfulness: number;
      timeCost: number;
      efficiency: number;
      automation: number;
    };

    const dims: Array<{ key: MaintenanceCorrelationInsight["dimension"]; pick: (row: AnalyticsJoinRow) => string }> = [
      { key: "severity", pick: (row) => row.severity },
      { key: "status", pick: (row) => row.status },
      { key: "confidence", pick: (row) => row.confidence },
      { key: "category", pick: (row) => row.category },
    ];

    const out: MaintenanceCorrelationInsight[] = [];
    for (const dim of dims) {
      const buckets = new Map<string, Bucket>();
      for (const row of rows) {
        const value = dim.pick(row) || "unknown";
        const current = buckets.get(value) ?? { count: 0, helpfulness: 0, timeCost: 0, efficiency: 0, automation: 0 };
        current.count += 1;
        current.helpfulness += row.helpfulness_score;
        current.timeCost += row.time_cost_score;
        current.efficiency += row.efficiency_score;
        current.automation += row.automation_potential;
        buckets.set(value, current);
      }

      for (const [value, bucket] of buckets.entries()) {
        out.push({
          dimension: dim.key,
          value,
          count: bucket.count,
          avgHelpfulness: round2(bucket.helpfulness / bucket.count),
          avgTimeCost: round2(bucket.timeCost / bucket.count),
          avgEfficiency: round2(bucket.efficiency / bucket.count),
          avgAutomationPotential: round2(bucket.automation / bucket.count),
        });
      }
    }

    return out.sort((a, b) => {
      if (a.dimension === b.dimension) {
        return b.count - a.count;
      }
      return a.dimension.localeCompare(b.dimension);
    });
  }

  private computeResponsePatterns(rows: AnalyticsJoinRow[]): MaintenanceResponsePattern[] {
    const counts = new Map<string, { count: number; highConfidenceCount: number; display: string }>();
    let total = 0;

    for (const row of rows) {
      const templates = extractResponseTemplates(row.recommendation_json);
      if (templates.length === 0) continue;

      for (const template of templates) {
        const key = normalizeTemplate(template);
        if (!key) continue;

        const current = counts.get(key) ?? { count: 0, highConfidenceCount: 0, display: template.trim() };
        current.count += 1;
        if (row.confidence === "observed" || row.confidence === "strong_inference") {
          current.highConfidenceCount += 1;
        }
        counts.set(key, current);
        total += 1;
      }
    }

    if (total === 0) {
      return [];
    }

    return Array.from(counts.values())
      .map((entry) => {
        const share = entry.count / total;
        const highConfidenceShare = entry.highConfidenceCount / entry.count;
        return {
          responseTemplate: entry.display,
          count: entry.count,
          share: round2(share),
          highConfidenceShare: round2(highConfidenceShare),
          automationReady: entry.count >= 3 && highConfidenceShare >= 0.66,
        };
      })
      .sort((a, b) => b.count - a.count)
      .slice(0, 15);
  }

  private computeAutomationCandidates(
    rows: AnalyticsJoinRow[],
    patterns: MaintenanceResponsePattern[],
  ): MaintenanceAutomationCandidate[] {
    const ready = patterns.filter((p) => p.automationReady).map((p) => p.responseTemplate);

    return rows
      .filter((row) => row.automation_potential >= 7)
      .filter((row) => row.confidence === "observed" || row.confidence === "strong_inference")
      .map((row) => {
        const templates = extractResponseTemplates(row.recommendation_json);
        const supporting = templates.find((t) => ready.some((r) => normalizeTemplate(r) === normalizeTemplate(t)));
        return {
          recordId: row.record_id,
          title: row.title,
          category: row.category,
          status: row.status,
          confidence: row.confidence,
          automationPotential: round2(row.automation_potential),
          supportingPattern: supporting,
        };
      })
      .sort((a, b) => b.automationPotential - a.automationPotential)
      .slice(0, 20);
  }

  private buildFindings(
    overview: ReturnType<MaintenanceStore["analyticsOverview"]>,
    correlations: MaintenanceCorrelationInsight[],
    patterns: MaintenanceResponsePattern[],
    automationCandidates: MaintenanceAutomationCandidate[],
  ): string[] {
    const findings: string[] = [];

    findings.push(
      `Average efficiency is ${overview.avgEfficiency.toFixed(2)} with automation potential at ${overview.avgAutomationPotential.toFixed(2)}.`,
    );

    const highestEfficiencyBucket = correlations
      .filter((c) => c.dimension === "category")
      .sort((a, b) => b.avgEfficiency - a.avgEfficiency)[0];
    if (highestEfficiencyBucket) {
      findings.push(
        `Category '${highestEfficiencyBucket.value}' has the highest efficiency (${highestEfficiencyBucket.avgEfficiency.toFixed(2)}) across ${highestEfficiencyBucket.count} records.`,
      );
    }

    const topPattern = patterns[0];
    if (topPattern) {
      findings.push(
        `Most frequent response template appears ${topPattern.count} times (${Math.round(topPattern.share * 100)}% share).`,
      );
    }

    if (automationCandidates.length > 0) {
      findings.push(
        `${automationCandidates.length} records are currently automation candidates with high confidence and automation potential >= 7.`,
      );
    }

    return findings;
  }

  private applyAutomationThresholdRules(groupKey: string, report: MaintenanceIntelligenceReport): { created: number } {
    let created = 0;

    for (const pattern of report.responsePatterns) {
      if (!pattern.automationReady || pattern.count < 3) continue;
      const normalized = normalizeTemplate(pattern.responseTemplate);
      const sourceRef = `${groupKey}:${normalized}`;

      const existing = this.db
        .prepare(
          `SELECT id FROM maintenance_records
           WHERE group_key = ?
             AND source = 'automation-threshold-rule'
             AND source_ref = ?
             AND status IN ('open', 'in_progress', 'blocked')
             AND is_archived = 0
           LIMIT 1`,
        )
        .get(groupKey, sourceRef) as { id: string } | undefined;

      if (existing) continue;

      this.createRecord({
        groupKey,
        category: "automation",
        title: `Automation threshold reached: ${pattern.responseTemplate}`,
        summary: `Template reached ${pattern.count} uses with ${Math.round(pattern.highConfidenceShare * 100)}% high-confidence responses.`,
        severity: pattern.count >= 6 ? "high" : "medium",
        priority: pattern.count >= 6 ? "P1" : "P2",
        status: "open",
        confidence: pattern.highConfidenceShare >= 0.8 ? "observed" : "strong_inference",
        source: "automation-threshold-rule",
        sourceRef,
        impactScore: clamp(4 + pattern.count * 0.5, 0, 10),
        effortScore: 3,
        riskScore: clamp(2 + (pattern.share * 10), 0, 10),
        recommendationJson: JSON.stringify([
          { recommendation: `Convert '${pattern.responseTemplate}' into an automated playbook step.` },
          { recommendation: "Add guardrails and monitoring before full automation rollout." },
        ]),
        tagsJson: JSON.stringify(["automation", "threshold", "daily-review"]),
      });

      created += 1;
    }

    return { created };
  }

  private applyIndependentThresholdRules(groupKey: string, summary: IndependentEvaluationSummary): { created: number } {
    const alerts: Array<{ key: string; title: string; summary: string; severity: MaintenanceSeverity; priority: MaintenancePriority; risk: number; impact: number }> = [];

    if (summary.hotmd.fallbackRate >= 0.3) {
      alerts.push({
        key: `${groupKey}:hotmd-fallback`,
        title: "Independent threshold reached: HotMD fallback rate",
        summary: `Fallback queue rate is ${Math.round(summary.hotmd.fallbackRate * 100)}% with ${summary.hotmd.fallbackFiles} fallback files.`,
        severity: "high",
        priority: "P1",
        risk: 7,
        impact: 7,
      });
    }
    if (summary.drift.mismatchRate24h >= 0.2 && summary.drift.decisionCount24h > 0) {
      alerts.push({
        key: `${groupKey}:routing-drift`,
        title: "Independent threshold reached: routing drift mismatch",
        summary: `Routing mismatch is ${Math.round(summary.drift.mismatchRate24h * 100)}% (${summary.drift.mismatchCount24h}/${summary.drift.decisionCount24h}) over 24h.`,
        severity: "high",
        priority: "P1",
        risk: 8,
        impact: 6,
      });
    }
    if (summary.degradation.isDegrading) {
      alerts.push({
        key: `${groupKey}:skill-degradation`,
        title: "Independent threshold reached: skill degradation trend",
        summary: `7d success-rate delta is ${round2(summary.degradation.deltaSuccessRate * 100)} pts against prior window.`,
        severity: "medium",
        priority: "P2",
        risk: 6,
        impact: 6,
      });
    }
    if (summary.budget.stoppedTasks > 0) {
      alerts.push({
        key: `${groupKey}:budget-stops`,
        title: "Independent threshold reached: budget stops",
        summary: `${summary.budget.stoppedTasks} stopped tasks detected in budget states.`,
        severity: "medium",
        priority: "P2",
        risk: 5,
        impact: 5,
      });
    }
    if (summary.offlineAudit.available && summary.offlineAudit.avgConfidence < 0.6) {
      alerts.push({
        key: `${groupKey}:offline-confidence`,
        title: "Independent threshold reached: offline confidence decay",
        summary: `Offline audit average confidence is ${Math.round(summary.offlineAudit.avgConfidence * 100)}% with ${summary.offlineAudit.lowConfidenceCount} low-confidence samples.`,
        severity: "high",
        priority: "P1",
        risk: 8,
        impact: 7,
      });
    }

    let created = 0;
    for (const alert of alerts) {
      const existing = this.db
        .prepare(
          `SELECT id FROM maintenance_records
           WHERE group_key = ?
             AND source = 'independent-eval-threshold'
             AND source_ref = ?
             AND status IN ('open', 'in_progress', 'blocked')
             AND is_archived = 0
           LIMIT 1`,
        )
        .get(groupKey, alert.key) as { id: string } | undefined;
      if (existing) continue;

      this.createRecord({
        groupKey,
        category: "independent-evaluation",
        title: alert.title,
        summary: alert.summary,
        severity: alert.severity,
        priority: alert.priority,
        status: "open",
        confidence: "observed",
        source: "independent-eval-threshold",
        sourceRef: alert.key,
        impactScore: alert.impact,
        effortScore: 3,
        riskScore: alert.risk,
        tagsJson: JSON.stringify(["independent-eval", "threshold", "daily-review"]),
      });
      created += 1;
    }
    return { created };
  }

  private renderDailySummaryMarkdown(
    date: string,
    reviewerRole: string,
    report: MaintenanceIntelligenceReport,
  ): string {
    const independent = this.getIndependentEvaluation(report.groupKey, date);
    const lines: string[] = [];
    lines.push(`# Daily Architecture Director Review — ${date}`);
    lines.push("");
    lines.push(`Reviewer: ${reviewerRole}`);
    lines.push(`Group: ${report.groupKey}`);
    lines.push(`Generated: ${report.generatedAt}`);
    lines.push("");
    lines.push("## Overview");
    lines.push(`- Records analyzed: ${report.totalRecords}`);
    lines.push(`- Analytics rows: ${report.analyticsTotal}`);
    lines.push(`- Automation candidates: ${report.automationCandidates.length}`);
    lines.push("");
    lines.push("## Key Findings");
    if (report.findings.length === 0) {
      lines.push("- No significant findings yet; collect more records for reliable trends.");
    } else {
      for (const finding of report.findings) {
        lines.push(`- ${finding}`);
      }
    }
    lines.push("");
    lines.push("## Top Response Patterns");
    if (report.responsePatterns.length === 0) {
      lines.push("- No repeatable response templates detected yet.");
    } else {
      for (const pattern of report.responsePatterns.slice(0, 5)) {
        lines.push(
          `- ${pattern.responseTemplate} (count=${pattern.count}, share=${Math.round(pattern.share * 100)}%, high-confidence=${Math.round(pattern.highConfidenceShare * 100)}%, automation-ready=${pattern.automationReady ? "yes" : "no"})`,
        );
      }
    }
    lines.push("");
    lines.push("## Recommended Automations");
    if (report.recommendedAutomations.length === 0) {
      lines.push("- No automation recommendations passed confidence threshold today.");
    } else {
      for (const item of report.recommendedAutomations) {
        lines.push(`- ${item}`);
      }
    }

    lines.push("");
    lines.push("## Independent Evaluation");
    lines.push(`- HotMD files: ${independent.hotmd.totalFiles} (fallback queue: ${independent.hotmd.fallbackFiles}, rate: ${Math.round(independent.hotmd.fallbackRate * 100)}%)`);
    lines.push(`- Budget impact: tokens=${independent.budget.totalTokens}, external_calls=${independent.budget.externalCalls}, stopped_tasks=${independent.budget.stoppedTasks}`);
    lines.push(`- Cost estimation quality: flagged=${independent.budget.flaggedCostAccuracy}, avg_error_pct=${round2(independent.budget.avgCostAccuracyPct)}`);
    lines.push(`- Skill degradation delta (7d): ${round2(independent.degradation.deltaSuccessRate * 100)} pts`);
    lines.push(`- Routing drift (24h): ${Math.round(independent.drift.mismatchRate24h * 100)}% (${independent.drift.mismatchCount24h}/${independent.drift.decisionCount24h})`);
    lines.push(`- Offline audit confidence: ${Math.round(independent.offlineAudit.avgConfidence * 100)}% (${independent.offlineAudit.lowConfidenceCount} low-confidence samples)`);
    lines.push("");
    lines.push("### Independent Findings");
    for (const finding of independent.findings) {
      lines.push(`- ${finding}`);
    }

    return lines.join("\n");
  }

  private renderIndependentEvaluationMarkdown(summary: IndependentEvaluationSummary): string {
    const lines: string[] = [];
    lines.push(`# Independent Evaluation — ${summary.reviewDate}`);
    lines.push("");
    lines.push(`Generated: ${summary.generatedAt}`);
    lines.push(`Group: ${summary.groupKey}`);
    lines.push("");
    lines.push("## Signals");
    lines.push(`- HotMD roots scanned: ${summary.hotmd.rootsScanned}`);
    lines.push(`- HotMD total files: ${summary.hotmd.totalFiles}`);
    lines.push(`- HotMD fallback files: ${summary.hotmd.fallbackFiles} (${Math.round(summary.hotmd.fallbackRate * 100)}%)`);
    lines.push(`- Budget tokens: ${summary.budget.totalTokens}`);
    lines.push(`- Budget external calls: ${summary.budget.externalCalls}`);
    lines.push(`- Budget stopped tasks: ${summary.budget.stoppedTasks}`);
    lines.push(`- Cost accuracy flags: ${summary.budget.flaggedCostAccuracy}`);
    lines.push(`- Skill success rate delta (7d): ${round2(summary.degradation.deltaSuccessRate * 100)} pts`);
    lines.push(`- Routing drift 24h: ${Math.round(summary.drift.mismatchRate24h * 100)}%`);
    lines.push(`- Offline audit confidence: ${Math.round(summary.offlineAudit.avgConfidence * 100)}%`);
    lines.push(`- Offline low-confidence samples: ${summary.offlineAudit.lowConfidenceCount}`);
    lines.push("");
    lines.push("## Findings");
    for (const finding of summary.findings) {
      lines.push(`- ${finding}`);
    }
    return lines.join("\n");
  }

  private renderWeeklyRollupMarkdown(rollup: WeeklyIndependentRollup): string {
    const lines: string[] = [];
    lines.push(`# Weekly Independent Rollup — ${rollup.endDate}`);
    lines.push("");
    lines.push(`Generated: ${rollup.generatedAt}`);
    lines.push(`Group: ${rollup.groupKey}`);
    lines.push(`Reviewer: ${rollup.reviewerRole}`);
    lines.push("");
    lines.push("## Window Coverage");
    lines.push(`- Recent days: ${rollup.windows.recentDays}`);
    lines.push(`- Prior days: ${rollup.windows.priorDays}`);
    lines.push("");
    lines.push("## Delta (Recent - Prior)");
    lines.push(`- Efficiency: ${round2(rollup.delta.avgEfficiency)}`);
    lines.push(`- Automation potential: ${round2(rollup.delta.avgAutomationPotential)}`);
    lines.push(`- HotMD fallback rate: ${round2(rollup.delta.avgHotmdFallbackRate)}`);
    lines.push(`- Routing mismatch rate: ${round2(rollup.delta.avgRoutingMismatchRate)}`);
    lines.push(`- Degradation delta: ${round2(rollup.delta.avgDegradationDelta)}`);
    lines.push(`- Offline confidence: ${round2(rollup.delta.avgOfflineConfidence)}`);
    lines.push(`- Findings count delta: ${rollup.delta.findingsCount}`);
    lines.push("");
    lines.push("## Weekly Findings");
    for (const finding of rollup.findings) {
      lines.push(`- ${finding}`);
    }
    return lines.join("\n");
  }

  private collectHotMdSignals(): IndependentEvaluationSummary["hotmd"] {
    const roots = this.resolveWorkspaceRoots();
    let totalFiles = 0;
    let fallbackFiles = 0;

    for (const root of roots) {
      const hotmd = path.join(root, ".HotMD");
      if (!fs.existsSync(hotmd)) continue;

      const stack = [hotmd];
      while (stack.length > 0) {
        const current = stack.pop() as string;
        const entries = fs.readdirSync(current, { withFileTypes: true });
        for (const entry of entries) {
          const abs = path.join(current, entry.name);
          if (entry.isDirectory()) {
            stack.push(abs);
            continue;
          }
          if (!entry.isFile() || !entry.name.toLowerCase().endsWith(".md")) continue;
          totalFiles += 1;
          if (abs.toLowerCase().includes("\\.fallback\\")) {
            fallbackFiles += 1;
          }
        }
      }
    }

    return {
      rootsScanned: roots.length,
      totalFiles,
      fallbackFiles,
      fallbackRate: totalFiles > 0 ? fallbackFiles / totalFiles : 0,
    };
  }

  private collectBudgetSignals(): IndependentEvaluationSummary["budget"] {
    let totalTokens = 0;
    let externalCalls = 0;
    let stoppedTasks = 0;
    let flaggedCostAccuracy = 0;
    let avgCostAccuracyPct = 0;

    if (this.tableExists("budget_states")) {
      const row = this.db
        .prepare(
          `SELECT
            COALESCE(SUM(tokens_used), 0) AS total_tokens,
            COALESCE(SUM(external_calls), 0) AS external_calls,
            COALESCE(SUM(CASE WHEN stopped = 1 THEN 1 ELSE 0 END), 0) AS stopped_tasks
           FROM budget_states`,
        )
        .get() as { total_tokens: number; external_calls: number; stopped_tasks: number };
      totalTokens = Number(row?.total_tokens ?? 0);
      externalCalls = Number(row?.external_calls ?? 0);
      stoppedTasks = Number(row?.stopped_tasks ?? 0);
    }

    if (this.tableExists("cost_accuracy")) {
      const row = this.db
        .prepare(
          `SELECT
            COALESCE(SUM(CASE WHEN flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged,
            COALESCE(AVG(accuracy_pct), 0) AS avg_accuracy
           FROM cost_accuracy`,
        )
        .get() as { flagged: number; avg_accuracy: number };
      flaggedCostAccuracy = Number(row?.flagged ?? 0);
      avgCostAccuracyPct = Number(row?.avg_accuracy ?? 0);
    }

    return {
      totalTokens,
      externalCalls,
      stoppedTasks,
      flaggedCostAccuracy,
      avgCostAccuracyPct: round2(avgCostAccuracyPct),
    };
  }

  private collectDegradationSignals(): IndependentEvaluationSummary["degradation"] {
    if (!this.tableExists("task_outcomes")) {
      return {
        current7dSuccessRate: 0,
        previous7dSuccessRate: 0,
        deltaSuccessRate: 0,
        isDegrading: false,
      };
    }

    const row = this.db
      .prepare(
        `SELECT
          AVG(CASE WHEN recorded_at >= datetime('now', '-7 day') THEN succeeded ELSE NULL END) AS current_rate,
          AVG(CASE WHEN recorded_at < datetime('now', '-7 day')
                    AND recorded_at >= datetime('now', '-14 day') THEN succeeded ELSE NULL END) AS previous_rate
         FROM task_outcomes`,
      )
      .get() as { current_rate: number | null; previous_rate: number | null };

    const current = Number(row?.current_rate ?? 0);
    const previous = Number(row?.previous_rate ?? 0);
    const delta = current - previous;

    return {
      current7dSuccessRate: round2(current),
      previous7dSuccessRate: round2(previous),
      deltaSuccessRate: round2(delta),
      isDegrading: previous > 0 && delta <= -0.05,
    };
  }

  private collectDriftSignals(): IndependentEvaluationSummary["drift"] {
    if (!this.tableExists("routing_decisions")) {
      return { mismatchCount24h: 0, decisionCount24h: 0, mismatchRate24h: 0 };
    }

    const row = this.db
      .prepare(
        `SELECT
          COUNT(*) AS decisions,
          COALESCE(SUM(CASE WHEN routing_reconciliation = 'mismatch' THEN 1 ELSE 0 END), 0) AS mismatches
         FROM routing_decisions
         WHERE ts >= datetime('now', '-1 day')`,
      )
      .get() as { decisions: number; mismatches: number };

    const decisions = Number(row?.decisions ?? 0);
    const mismatches = Number(row?.mismatches ?? 0);
    return {
      mismatchCount24h: mismatches,
      decisionCount24h: decisions,
      mismatchRate24h: decisions > 0 ? round2(mismatches / decisions) : 0,
    };
  }

  private collectOfflineAuditSignals(): IndependentEvaluationSummary["offlineAudit"] {
    const latest = readLatestOfflineValueAudit();
    const enabled = loadRuntimeRoutingControls().offlineAuditEnabled;

    if (!latest) {
      return {
        enabled,
        available: false,
        model: process.env.GEN_OLLAMA_MODEL || "qwen3:4b",
        sampledFiles: 0,
        successCount: 0,
        failureCount: 0,
        avgConfidence: 0,
        lowConfidenceCount: 0,
      };
    }

    return {
      enabled,
      available: true,
      generatedAt: latest.generatedAt,
      model: latest.model,
      sampledFiles: latest.sampleCount,
      successCount: latest.successCount,
      failureCount: latest.failureCount,
      avgConfidence: round2(latest.avgConfidence),
      lowConfidenceCount: latest.lowConfidenceCount,
    };
  }

  private resolveWorkspaceRoots(): string[] {
    const iniPath = "C:\\AI-DJ\\workspace-map.ini";
    const fallback = [path.resolve(__dirname, "../../..")];
    if (!fs.existsSync(iniPath)) return fallback;

    const raw = fs.readFileSync(iniPath, "utf-8");
    const lines = raw.split(/\r?\n/);
    let inSection = false;
    const out: string[] = [];

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
        inSection = trimmed.toLowerCase() === "[workspaces]";
        continue;
      }
      if (!inSection || trimmed.length === 0 || trimmed.startsWith(";")) continue;
      const eq = trimmed.indexOf("=");
      if (eq <= 0) continue;
      const value = trimmed.slice(eq + 1).trim();
      if (value.length === 0) continue;
      out.push(value);
    }

    return out.length > 0 ? out : fallback;
  }

  private tableExists(name: string): boolean {
    const row = this.db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1")
      .get(name) as { name: string } | undefined;
    return Boolean(row?.name);
  }
}

function rowToAnalyticsRow(row: Record<string, unknown>): MaintenanceAnalyticsRow {
  return {
    recordId: String(row.record_id ?? ""),
    computedAt: String(row.computed_at ?? ""),
    helpfulnessScore: Number(row.helpfulness_score ?? 0),
    timeCostScore: Number(row.time_cost_score ?? 0),
    efficiencyScore: Number(row.efficiency_score ?? 0),
    automationPotential: Number(row.automation_potential ?? 0),
    evidenceCount: Number(row.evidence_count ?? 0),
    recommendationCount: Number(row.recommendation_count ?? 0),
  };
}

function rowToDailyReview(row: Record<string, unknown>): MaintenanceDailyReview {
  return {
    id: String(row.id ?? ""),
    reviewDate: String(row.review_date ?? ""),
    groupKey: String(row.group_key ?? ""),
    reviewerRole: String(row.reviewer_role ?? ""),
    generatedAt: String(row.generated_at ?? ""),
    summaryMarkdown: String(row.summary_markdown ?? ""),
    intelligenceJson: String(row.intelligence_json ?? "{}"),
  };
}

function parseIntelligenceReport(raw: string): MaintenanceIntelligenceReport | null {
  try {
    const parsed = JSON.parse(raw) as MaintenanceIntelligenceReport;
    if (!parsed || typeof parsed !== "object") return null;
    return parsed;
  } catch {
    return null;
  }
}

function extractResponseTemplates(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const out: string[] = [];
    for (const item of parsed) {
      if (typeof item === "string") {
        out.push(item);
        continue;
      }
      if (item && typeof item === "object") {
        const maybeText = (item as Record<string, unknown>).text;
        const maybeRecommendation = (item as Record<string, unknown>).recommendation;
        if (typeof maybeText === "string") out.push(maybeText);
        else if (typeof maybeRecommendation === "string") out.push(maybeRecommendation);
      }
    }
    return out;
  } catch {
    return [];
  }
}

function normalizeTemplate(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[.!,;:]+$/g, "");
}

function safeJsonArrayLength(raw: string): number {
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.length : 0;
  } catch {
    return 0;
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function rowToRecord(row: Record<string, unknown>): MaintenanceRecord {
  return {
    id: row.id as string,
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
    groupKey: row.group_key as string,
    category: row.category as string,
    title: row.title as string,
    summary: (row.summary as string | null) ?? undefined,
    severity: row.severity as MaintenanceSeverity,
    priority: row.priority as MaintenancePriority,
    status: row.status as MaintenanceStatus,
    confidence: row.confidence as MaintenanceConfidence,
    source: (row.source as string | null) ?? undefined,
    sourceRef: (row.source_ref as string | null) ?? undefined,
    workflowId: (row.workflow_id as string | null) ?? undefined,
    component: (row.component as string | null) ?? undefined,
    environment: (row.environment as string | null) ?? undefined,
    ownerRole: (row.owner_role as string | null) ?? undefined,
    assignee: (row.assignee as string | null) ?? undefined,
    dueDate: (row.due_date as string | null) ?? undefined,
    sessionId: (row.session_id as string | null) ?? undefined,
    taskId: (row.task_id as string | null) ?? undefined,
    impactScore: Number(row.impact_score ?? 0),
    effortScore: Number(row.effort_score ?? 0),
    riskScore: Number(row.risk_score ?? 0),
    evidenceJson: (row.evidence_json as string) ?? "[]",
    recommendationJson: (row.recommendation_json as string) ?? "[]",
    tagsJson: (row.tags_json as string) ?? "[]",
    isArchived: Boolean(row.is_archived),
    closedAt: (row.closed_at as string | null) ?? undefined,
  };
}
