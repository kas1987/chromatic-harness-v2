import { describe, it, expect } from "vitest";
import { cosineSimilarity } from "../../src/memory/memory-retrieve";

describe("Memory Retrieval - Cosine Similarity", () => {
  it("cosineSimilarity returns 1.0 for identical vectors", () => {
    const vec = new Float32Array([1, 0, 0, 0]);
    const similarity = cosineSimilarity(vec, vec);
    expect(similarity).toBeCloseTo(1.0);
  });

  it("cosineSimilarity returns 0.0 for orthogonal vectors", () => {
    const vec1 = new Float32Array([1, 0, 0, 0]);
    const vec2 = new Float32Array([0, 1, 0, 0]);
    const similarity = cosineSimilarity(vec1, vec2);
    expect(Math.abs(similarity)).toBeCloseTo(0.0, 5);
  });

  it("cosineSimilarity handles normalized vectors correctly", () => {
    const vec1 = new Float32Array([0.6, 0.8]); // normalized
    const vec2 = new Float32Array([0.6, 0.8]); // normalized
    const similarity = cosineSimilarity(vec1, vec2);
    expect(similarity).toBeCloseTo(1.0);
  });

  it("cosineSimilarity returns 0 for mismatched lengths", () => {
    const vec1 = new Float32Array([1, 0, 0]);
    const vec2 = new Float32Array([1, 0]);
    const similarity = cosineSimilarity(vec1, vec2);
    expect(similarity).toBe(0);
  });

  it("cosineSimilarity handles zero vectors", () => {
    const zero = new Float32Array([0, 0, 0, 0]);
    const nonZero = new Float32Array([1, 0, 0, 0]);
    const similarity = cosineSimilarity(zero, nonZero);
    expect(similarity).toBe(0);
  });

  it("cosineSimilarity is symmetric", () => {
    const vec1 = new Float32Array([1, 2, 3]);
    const vec2 = new Float32Array([4, 5, 6]);
    const sim1 = cosineSimilarity(vec1, vec2);
    const sim2 = cosineSimilarity(vec2, vec1);
    expect(sim1).toBeCloseTo(sim2);
  });
});
