// In-browser NeuralLog engine.
//
// When the site is served as a static page (for example on GitHub Pages) there is
// no Python API to talk to. This module reproduces the same ingest -> chunk ->
// embed -> search/timeline/evaluate pipeline entirely in the browser using the
// bundled sample dataset, so visitors can try the full workflow with no setup.

import sampleExport from "../data/sample-export.json";
import sampleEvaluation from "../data/sample-evaluation.json";
import type {
  ComparisonSummary,
  EvaluationSummary,
  SearchResult,
  TimelineEvent,
} from "../types";

type RawMessage = {
  id: string | number;
  timestamp: string;
  content?: string;
  author?: { id?: string; name?: string };
};

type Message = {
  id: string;
  channelId: string;
  channelName: string;
  author: string;
  timestamp: Date;
  content: string;
};

type Chunk = {
  id: string;
  messageIds: string[];
  channelId: string;
  channelName: string;
  participants: string[];
  startTime: Date;
  endTime: Date;
  text: string;
};

const EMBEDDING_DIMENSIONS = 384;
const EMBED_TOKEN_PATTERN = /[A-Za-z0-9_./:-]+/g;
const SCORE_TOKEN_PATTERN = /[a-z0-9]+/g;
const STOP_WORDS = new Set([
  "a", "an", "and", "are", "can", "did", "do", "for", "how", "in", "is", "it",
  "of", "on", "the", "to", "was", "we", "what", "when", "why", "with",
]);

// ---------------------------------------------------------------------------
// Ingest + chunking (mirrors neurallog/discord_ingest.py and chunking.py)
// ---------------------------------------------------------------------------

function loadMessages(): Message[] {
  const payload = sampleExport as {
    guild?: { name?: string };
    channel?: { id?: string; name?: string; topic?: string };
    messages: RawMessage[];
  };

  const channelName =
    payload.channel?.name || payload.channel?.topic || payload.guild?.name || "channel";
  const channelId = String(payload.channel?.id || "channel");

  const messages: Message[] = [];
  for (const raw of payload.messages ?? []) {
    const content = (raw.content ?? "").trim();
    if (!content) continue;
    messages.push({
      id: String(raw.id),
      channelId,
      channelName: String(channelName),
      author: raw.author?.name ? String(raw.author.name) : "unknown",
      timestamp: new Date(raw.timestamp.replace("Z", "+00:00")),
      content,
    });
  }

  messages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
  return messages;
}

async function chunkMessages(messages: Message[]): Promise<Chunk[]> {
  if (messages.length === 0) return [];

  const maxMessages = 8;
  const maxCharacters = 2000;
  const maxGapMs = 90 * 60 * 1000;

  const groups: Message[][] = [];
  let current: Message[] = [];
  let currentChars = 0;

  for (const message of messages) {
    if (current.length === 0) {
      current = [message];
      currentChars = message.content.length;
      continue;
    }

    const previous = current[current.length - 1];
    const shouldSplit =
      message.channelId !== previous.channelId ||
      message.timestamp.getTime() - previous.timestamp.getTime() > maxGapMs ||
      current.length >= maxMessages ||
      currentChars + message.content.length > maxCharacters;

    if (shouldSplit) {
      groups.push(current);
      current = [message];
      currentChars = message.content.length;
    } else {
      current.push(message);
      currentChars += message.content.length;
    }
  }
  if (current.length > 0) groups.push(current);

  const chunks: Chunk[] = [];
  for (const group of groups) {
    const participants = uniqueOrdered(group.map((m) => m.author));
    const text = group.map((m) => `[${m.author}] ${m.content}`).join("\n");
    const digest = (await sha1Hex(group.map((m) => m.id).join("|"))).slice(0, 12);
    chunks.push({
      id: `${group[0].channelId}-${digest}`,
      messageIds: group.map((m) => m.id),
      channelId: group[0].channelId,
      channelName: group[0].channelName,
      participants,
      startTime: group[0].timestamp,
      endTime: group[group.length - 1].timestamp,
      text,
    });
  }
  return chunks;
}

// ---------------------------------------------------------------------------
// Hashing embedder + hybrid scoring (mirrors embeddings.py and index.py)
// ---------------------------------------------------------------------------

async function embed(text: string): Promise<Float64Array> {
  const counts = new Map<string, number>();
  for (const match of text.toLowerCase().matchAll(EMBED_TOKEN_PATTERN)) {
    const token = match[0];
    counts.set(token, (counts.get(token) ?? 0) + 1);
  }

  const vector = new Float64Array(EMBEDDING_DIMENSIONS);
  for (const [token, count] of counts) {
    const index = await sha256Mod(token, EMBEDDING_DIMENSIONS);
    vector[index] += count;
  }

  let norm = 0;
  for (const value of vector) norm += value * value;
  norm = Math.sqrt(norm);
  if (norm === 0) return vector;
  for (let i = 0; i < vector.length; i += 1) vector[i] /= norm;
  return vector;
}

function dot(left: Float64Array, right: Float64Array): number {
  let total = 0;
  for (let i = 0; i < left.length; i += 1) total += left[i] * right[i];
  return total;
}

function scoreTokens(text: string): string[] {
  const tokens: string[] = [];
  for (const match of text.toLowerCase().matchAll(SCORE_TOKEN_PATTERN)) {
    if (!STOP_WORDS.has(match[0])) tokens.push(match[0]);
  }
  return tokens;
}

function hybridScore(
  query: string,
  queryTerms: string[],
  chunk: Chunk,
  semanticScore: number,
): number {
  const chunkText = chunk.text.toLowerCase();
  if (queryTerms.length === 0) return semanticScore;

  const matches = queryTerms.filter((term) => chunkText.includes(term)).length;
  const coverage = matches / queryTerms.length;
  const phraseBonus = chunkText.includes(query.toLowerCase()) ? 0.15 : 0;
  const titleBonus = queryTerms.some((term) => chunk.channelName.toLowerCase().includes(term))
    ? 0.1
    : 0;

  return semanticScore + 0.35 * coverage + phraseBonus + titleBonus;
}

// ---------------------------------------------------------------------------
// Engine (ingests the sample dataset once and caches the chunk vectors)
// ---------------------------------------------------------------------------

type Engine = {
  messageCount: number;
  chunks: Chunk[];
  vectors: Float64Array[];
};

let enginePromise: Promise<Engine> | null = null;

function buildEngine(): Promise<Engine> {
  if (!enginePromise) {
    enginePromise = (async () => {
      const messages = loadMessages();
      const chunks = await chunkMessages(messages);
      const vectors = await Promise.all(chunks.map((chunk) => embed(chunk.text)));
      return { messageCount: messages.length, chunks, vectors };
    })();
  }
  return enginePromise;
}

async function rankedResults(query: string, limit: number): Promise<SearchResult[]> {
  const engine = await buildEngine();
  if (engine.chunks.length === 0) return [];

  const queryVector = await embed(query);
  const queryTerms = scoreTokens(query);

  const scored = engine.chunks.map((chunk, index) => ({
    chunk,
    score: hybridScore(query, queryTerms, chunk, dot(queryVector, engine.vectors[index])),
  }));
  scored.sort((a, b) => b.score - a.score);

  return scored.slice(0, limit).map(({ chunk, score }) => ({
    chunk_id: chunk.id,
    score,
    channel_name: chunk.channelName,
    start_time: chunk.startTime.toISOString(),
    end_time: chunk.endTime.toISOString(),
    participants: chunk.participants,
    preview: chunk.text.replace(/\n/g, " ").slice(0, 240),
    message_ids: chunk.messageIds,
  }));
}

// ---------------------------------------------------------------------------
// Public demo API (matches the shapes returned by lib/api.ts)
// ---------------------------------------------------------------------------

export async function demoHealth() {
  const engine = await buildEngine();
  return {
    status: "demo",
    index_size: engine.chunks.length,
    backend: "inmemory",
    embedding_backend: "hash",
  };
}

export async function demoIngest() {
  const engine = await buildEngine();
  return {
    messages_indexed: engine.messageCount,
    chunks_created: engine.chunks.length,
    index_size: engine.chunks.length,
    backend: "inmemory",
    embedding_backend: "hash",
  };
}

export async function demoSearch(query: string, limit: number) {
  return { results: await rankedResults(query, limit) };
}

export async function demoTimeline(query: string, limit: number) {
  const results = await rankedResults(query, limit);
  const grouped = new Map<string, SearchResult[]>();
  for (const result of results) {
    const dateKey = result.start_time.slice(0, 10);
    const bucket = grouped.get(dateKey) ?? [];
    bucket.push(result);
    grouped.set(dateKey, bucket);
  }

  const events: TimelineEvent[] = [];
  for (const dateKey of [...grouped.keys()].sort()) {
    const group = grouped.get(dateKey)!;
    group.sort((a, b) => a.start_time.localeCompare(b.start_time));
    const lead = group[0];
    const participants = uniqueOrdered(group.flatMap((result) => result.participants));
    events.push({
      timestamp: lead.start_time,
      title: `${lead.channel_name}: ${query}`,
      summary: group.map((result) => result.preview).join(" ").slice(0, 500),
      channel_name: lead.channel_name,
      participants,
      message_ids: group.flatMap((result) => result.message_ids),
    });
  }
  return { events };
}

export async function demoEvaluate(limit: number) {
  const evaluation = sampleEvaluation as {
    queries: { query: string; relevant_message_ids: (string | number)[] }[];
  };

  const perQuery = [];
  for (const item of evaluation.queries) {
    const relevant = item.relevant_message_ids.map(String);
    const results = await rankedResults(item.query, limit);
    const retrieved = uniqueOrdered(results.flatMap((result) => result.message_ids));

    perQuery.push({
      query: item.query,
      retrieved_message_ids: retrieved,
      relevant_message_ids: relevant,
      precision_at_k: precisionAtK(retrieved, relevant, limit),
      recall_at_k: recallAtK(retrieved, relevant, limit),
      reciprocal_rank: reciprocalRank(retrieved, relevant),
    });
  }

  const summary: EvaluationSummary = {
    queries_evaluated: perQuery.length,
    mean_precision_at_k: mean(perQuery.map((q) => q.precision_at_k)),
    mean_recall_at_k: mean(perQuery.map((q) => q.recall_at_k)),
    mean_reciprocal_rank: mean(perQuery.map((q) => q.reciprocal_rank)),
  };

  return { summary, per_query: perQuery };
}

export async function demoCompare(specs: string[], limit: number) {
  const comparisons: ComparisonSummary[] = [];
  const failures: { label: string; error: string }[] = [];

  for (const spec of specs) {
    const [backend, model] = spec.split(":").map((part) => part.trim());
    if (backend !== "hash") {
      failures.push({
        label: spec,
        error: `The ${backend} backend needs Python packages that aren't available in the browser demo. Run NeuralLog locally to compare it.`,
      });
      continue;
    }
    const report = await demoEvaluate(limit);
    comparisons.push({
      label: spec,
      embedding_backend: "hash",
      embedding_model: model ?? null,
      summary: report.summary,
    });
  }

  comparisons.sort(
    (a, b) =>
      b.summary.mean_reciprocal_rank - a.summary.mean_reciprocal_rank ||
      b.summary.mean_precision_at_k - a.summary.mean_precision_at_k,
  );

  return { comparisons, failures };
}

export function demoExportMessage(outputPath: string) {
  return {
    status: "demo",
    channel_id: String((sampleExport as { channel?: { id?: string } }).channel?.id ?? "channel"),
    token_kind: "bot",
    output_path: outputPath,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function uniqueOrdered(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    if (!seen.has(value)) {
      seen.add(value);
      result.push(value);
    }
  }
  return result;
}

function precisionAtK(retrieved: string[], relevant: string[], k: number): number {
  if (k <= 0) return 0;
  const topK = retrieved.slice(0, k);
  if (topK.length === 0) return 0;
  const relevantSet = new Set(relevant);
  const hits = topK.filter((id) => relevantSet.has(id)).length;
  return hits / topK.length;
}

function recallAtK(retrieved: string[], relevant: string[], k: number): number {
  if (relevant.length === 0) return 0;
  const relevantSet = new Set(relevant);
  const hits = retrieved.slice(0, k).filter((id) => relevantSet.has(id)).length;
  return hits / relevant.length;
}

function reciprocalRank(retrieved: string[], relevant: string[]): number {
  const relevantSet = new Set(relevant);
  for (let i = 0; i < retrieved.length; i += 1) {
    if (relevantSet.has(retrieved[i])) return 1 / (i + 1);
  }
  return 0;
}

function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

async function digestHex(algorithm: "SHA-1" | "SHA-256", text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const buffer = await crypto.subtle.digest(algorithm, bytes);
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sha1Hex(text: string): Promise<string> {
  return digestHex("SHA-1", text);
}

async function sha256Mod(text: string, modulus: number): Promise<number> {
  const hex = await digestHex("SHA-256", text);
  return Number(BigInt(`0x${hex}`) % BigInt(modulus));
}
