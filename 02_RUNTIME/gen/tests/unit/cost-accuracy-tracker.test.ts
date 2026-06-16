import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { CostAccuracyTracker } from "../../src/budget/cost-accuracy-tracker.js";

function makeTracker(): { tracker: CostAccuracyTracker; db: Database.Database } {
  const db = new Database(":memory:");
  const tracker = new CostAccuracyTracker(db);
  return { tracker, db };
}

describe("CostAccuracyTracker", () => {
  it("RecordCompletion_ExactMatch_AccuracyZeroNotFlagged: estimate equals actual → accuracyPct=0, flagged=false", () => {
    const { tracker } = makeTracker();
    const record = tracker.recordCompletion("task-1", "gpt", 0.0050, 0.0050);
    expect(record.accuracyPct).toBe(0);
    expect(record.flagged).toBe(false);
    expect(record.taskId).toBe("task-1");
    expect(record.model).toBe("gpt");
  });

  it("RecordCompletion_50PctOff_FlaggedTrue: estimate 50% over actual → accuracyPct=50, flagged=true", () => {
    const { tracker } = makeTracker();
    const record = tracker.recordCompletion("task-2", "gpt", 0.0075, 0.0050);
    expect(record.accuracyPct).toBeCloseTo(50, 5);
    expect(record.flagged).toBe(true);
  });

  it("RecordCompletion_Exactly20PctOff_NotFlagged: threshold is strictly > 20%, so 20% is not flagged", () => {
    const { tracker } = makeTracker();
    // actual=0.01, estimate=0.012 → |0.012-0.01|/0.01*100 = 20.0 exactly
    const record = tracker.recordCompletion("task-3", "gemini", 0.012, 0.010);
    expect(record.accuracyPct).toBeCloseTo(20, 5);
    expect(record.flagged).toBe(false);
  });

  it("RecordCompletion_21PctOff_Flagged: 21% off crosses the threshold → flagged=true", () => {
    const { tracker } = makeTracker();
    // actual=0.01, estimate=0.0121 → |0.0121-0.01|/0.01*100 = 21.0
    const record = tracker.recordCompletion("task-4", "gemini", 0.0121, 0.010);
    expect(record.accuracyPct).toBeCloseTo(21, 5);
    expect(record.flagged).toBe(true);
  });

  it("GetFlaggedRecords_ReturnsOnlyFlagged: unflagged records are excluded", () => {
    const { tracker } = makeTracker();
    // Flagged (50% off)
    tracker.recordCompletion("task-a", "gpt", 0.015, 0.010);
    // Not flagged (exact match)
    tracker.recordCompletion("task-b", "gpt", 0.010, 0.010);
    // Flagged (30% off)
    tracker.recordCompletion("task-c", "gpt", 0.013, 0.010);

    const flagged = tracker.getFlaggedRecords();
    expect(flagged).toHaveLength(2);
    expect(flagged.every(r => r.flagged)).toBe(true);
    const taskIds = flagged.map(r => r.taskId);
    expect(taskIds).toContain("task-a");
    expect(taskIds).toContain("task-c");
  });

  it("GetAverageAccuracy_AllRecords_ReturnsCorrectAverage", () => {
    const { tracker } = makeTracker();
    // accuracyPct = 0
    tracker.recordCompletion("t1", "gpt", 0.010, 0.010);
    // accuracyPct = 50
    tracker.recordCompletion("t2", "gpt", 0.015, 0.010);
    // avg = (0 + 50) / 2 = 25
    const avg = tracker.getAverageAccuracy();
    expect(avg).toBeCloseTo(25, 5);
  });

  it("GetAverageAccuracy_FilteredByModel_OnlyThatModelsRecords", () => {
    const { tracker } = makeTracker();
    // gpt records: 0% + 50% = avg 25%
    tracker.recordCompletion("t1", "gpt", 0.010, 0.010);
    tracker.recordCompletion("t2", "gpt", 0.015, 0.010);
    // gemini record: 10%
    tracker.recordCompletion("t3", "gemini", 0.011, 0.010);

    const gptAvg = tracker.getAverageAccuracy("gpt");
    expect(gptAvg).toBeCloseTo(25, 5);

    const geminiAvg = tracker.getAverageAccuracy("gemini");
    expect(geminiAvg).toBeCloseTo(10, 5);
  });

  it("GetAccuracySummary_CorrectCountsAndModelBreakdown", () => {
    const { tracker } = makeTracker();
    // gpt: 0% (not flagged)
    tracker.recordCompletion("s1", "gpt", 0.010, 0.010);
    // gpt: 50% (flagged)
    tracker.recordCompletion("s2", "gpt", 0.015, 0.010);
    // gemini: 30% (flagged)
    tracker.recordCompletion("s3", "gemini", 0.013, 0.010);

    const summary = tracker.getAccuracySummary();
    expect(summary.totalRecords).toBe(3);
    expect(summary.flaggedCount).toBe(2);
    // avg of 0 + 50 + 30 = 80 / 3 ≈ 26.67
    expect(summary.avgAccuracyPct).toBeCloseTo(80 / 3, 4);
    expect(summary.byModel["gpt"]).toBeCloseTo(25, 5);
    expect(summary.byModel["gemini"]).toBeCloseTo(30, 5);
  });
});
