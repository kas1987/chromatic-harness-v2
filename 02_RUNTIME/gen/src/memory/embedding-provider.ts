import fetch from "node-fetch";

export interface IEmbeddingProvider {
  embed(text: string): Promise<Float32Array>;
  embedBatch(texts: string[]): Promise<Float32Array[]>;
}

class LRUCache<K, V> {
  private cache: Map<K, V>;
  private maxSize: number;

  constructor(maxSize: number = 100) {
    this.cache = new Map();
    this.maxSize = maxSize;
  }

  get(key: K): V | undefined {
    if (!this.cache.has(key)) return undefined;
    const value = this.cache.get(key)!;
    this.cache.delete(key);
    this.cache.set(key, value);
    return value;
  }

  set(key: K, value: V): void {
    if (this.cache.has(key)) this.cache.delete(key);
    this.cache.set(key, value);
    if (this.cache.size > this.maxSize) {
      const iterator = this.cache.keys();
      const firstKey = iterator.next().value;
      if (firstKey) this.cache.delete(firstKey);
    }
  }

  clear(): void {
    this.cache.clear();
  }

  size(): number {
    return this.cache.size;
  }
}

export class EmbeddingProvider implements IEmbeddingProvider {
  private authKey: string;
  private apiUrl: string;
  private model: string;
  private cache: LRUCache<string, Float32Array>;

  constructor(authKey: string, apiUrl?: string, cacheSize?: number, model?: string) {
    this.authKey = authKey;
    this.apiUrl = apiUrl ?? "https://api.openai.com/v1/embeddings";
    this.model = model ?? "text-embedding-3-small";
    this.cache = new LRUCache(cacheSize ?? 1000);
  }

  public async embed(text: string): Promise<Float32Array> {
    const [vec] = await this.embedBatch([text]);
    return vec;
  }

  public async embedBatch(texts: string[]): Promise<Float32Array[]> {
    const results: Float32Array[] = new Array(texts.length);
    const uncachedTexts: string[] = [];
    const uncachedIndices: number[] = [];

    for (let i = 0; i < texts.length; i++) {
      const cached = this.cache.get(texts[i]);
      if (cached) {
        results[i] = cached;
      } else {
        uncachedTexts.push(texts[i]);
        uncachedIndices.push(i);
      }
    }

    if (uncachedTexts.length > 0) {
      // Single batched request for all uncached texts — far cheaper than N sequential calls
      const response = await fetch(this.apiUrl, {
        method: "POST",
        headers: { "Authorization": `Bearer ${this.authKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({ input: uncachedTexts, model: this.model }),
      });

      if (!response.ok) throw new Error(`Embedding API error: ${response.status}`);

      const data = (await response.json()) as { data: Array<{ embedding: number[] }> };
      if (!data.data || data.data.length !== uncachedTexts.length) {
        throw new Error("Invalid embedding response length");
      }

      for (let i = 0; i < uncachedTexts.length; i++) {
        const embedding = new Float32Array(data.data[i].embedding);
        this.cache.set(uncachedTexts[i], embedding);
        results[uncachedIndices[i]] = embedding;
      }
    }

    return results;
  }

  public getCacheSize(): number {
    return this.cache.size();
  }

  public clearCache(): void {
    this.cache.clear();
  }
}
