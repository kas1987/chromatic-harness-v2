import { describe, it, expect } from "vitest";
import { SimpleEmbeddingProvider } from "../../src/memory/simple-embedding-provider";

describe("Embedding Providers", () => {
  it("SimpleEmbeddingProvider returns vectors of fixed length", async () => {
    const provider = new SimpleEmbeddingProvider();
    const vec = await provider.embed("hello world");

    expect(vec).toBeInstanceOf(Float32Array);
    expect(vec.length).toBe(128);
  });

  it("SimpleEmbeddingProvider returns normalized vectors", async () => {
    const provider = new SimpleEmbeddingProvider();
    const vec = await provider.embed("test text");

    let norm = 0;
    for (let i = 0; i < vec.length; i++) {
      norm += vec[i] * vec[i];
    }
    norm = Math.sqrt(norm);

    expect(norm).toBeCloseTo(1.0, 5);
  });

  it("SimpleEmbeddingProvider produces deterministic embeddings with same seed", async () => {
    const provider1 = new SimpleEmbeddingProvider(42);
    const provider2 = new SimpleEmbeddingProvider(42);

    const vec1 = await provider1.embed("deterministic text");
    const vec2 = await provider2.embed("deterministic text");

    for (let i = 0; i < vec1.length; i++) {
      expect(vec1[i]).toBe(vec2[i]);
    }
  });

  it("SimpleEmbeddingProvider.embedBatch returns array of vectors", async () => {
    const provider = new SimpleEmbeddingProvider();
    const vecs = await provider.embedBatch(["text1", "text2", "text3"]);

    expect(vecs).toHaveLength(3);
    for (const vec of vecs) {
      expect(vec).toBeInstanceOf(Float32Array);
      expect(vec.length).toBe(128);
    }
  });
});
