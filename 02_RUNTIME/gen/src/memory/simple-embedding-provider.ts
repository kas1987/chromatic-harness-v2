export interface IEmbeddingProvider {
  embed(text: string): Promise<Float32Array>;
  embedBatch(texts: string[]): Promise<Float32Array[]>;
}

export class SimpleEmbeddingProvider implements IEmbeddingProvider {
  private seed: number;

  constructor(seed: number = 42) {
    this.seed = seed;
  }

  async embed(text: string): Promise<Float32Array> {
    const [vec] = await this.embedBatch([text]);
    return vec;
  }

  async embedBatch(texts: string[]): Promise<Float32Array[]> {
    return texts.map((text) => {
      // Simple seeded random for deterministic dev/test vectors
      const hash = this.hashString(text);
      const rng = new SeededRandom(hash ^ this.seed);

      const vec = new Float32Array(128);
      for (let i = 0; i < 128; i++) {
        vec[i] = rng.next() - 0.5;
      }

      return this.normalize(vec);
    });
  }

  private normalize(vec: Float32Array): Float32Array {
    let norm = 0;
    for (let i = 0; i < vec.length; i++) {
      norm += vec[i] * vec[i];
    }
    norm = Math.sqrt(norm);
    if (norm === 0) return vec;

    for (let i = 0; i < vec.length; i++) {
      vec[i] /= norm;
    }
    return vec;
  }

  private hashString(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }
}

class SeededRandom {
  private seed: number;

  constructor(seed: number) {
    this.seed = seed % 2147483647;
    if (this.seed <= 0) this.seed += 2147483646;
  }

  next(): number {
    this.seed = (this.seed * 16807) % 2147483647;
    return this.seed / 2147483647;
  }
}
