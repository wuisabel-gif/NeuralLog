import type { ServiceConfig } from "../types";
import {
  demoCompare,
  demoEvaluate,
  demoExportMessage,
  demoHealth,
  demoIngest,
  demoSearch,
  demoTimeline,
} from "./demo";

function resolveApiBase() {
  const override = (window as typeof window & { NEURALLOG_API_BASE?: string }).NEURALLOG_API_BASE?.trim();
  if (override) {
    return override.replace(/\/+$/, "");
  }

  if (window.location.protocol === "file:") {
    return "http://127.0.0.1:8000";
  }

  if (window.location.port === "5173") {
    return "http://127.0.0.1:8000";
  }

  return window.location.origin.replace(/\/+$/, "");
}

const API_BASE = resolveApiBase();

// When the NeuralLog API can't be reached (for example on a static GitHub Pages
// deployment) the app transparently switches to the in-browser demo engine so
// every workflow still works against the bundled sample dataset.
let demoMode = false;

export function isDemoMode(): boolean {
  return demoMode;
}

function enableDemoMode() {
  demoMode = true;
}

async function fetchWithTimeout(input: string, init?: RequestInit, timeoutMs = 3000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const raw = await response.text();
  let payload: Record<string, unknown> | null = null;
  if (raw) {
    try {
      payload = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    throw new Error(typeof payload?.detail === "string" ? payload.detail : "Request failed");
  }
  return payload as T;
}

export async function fetchHealth(): Promise<{
  status: string;
  index_size: number;
  backend: string;
  embedding_backend: string;
}> {
  try {
    const response = await fetchWithTimeout(`${API_BASE}/health`);
    if (!response.ok) {
      throw new Error("Unable to reach NeuralLog API");
    }
    return await response.json();
  } catch {
    enableDemoMode();
    return demoHealth();
  }
}

export async function exportDiscord(input: {
  token: string;
  token_kind: "bot" | "user";
  channel_id: string;
  output_path?: string | null;
  config: ServiceConfig;
}): Promise<{
  status: string;
  channel_id: string;
  token_kind: string;
  output_path: string;
  stdout?: string;
}> {
  try {
    return await post("/workflow/export-discord", input);
  } catch (error) {
    if (demoMode) {
      throw new Error(
        "Exporting from Discord needs the NeuralLog API running locally. The live demo already includes a sample export you can search, time-line, and evaluate right away.",
      );
    }
    throw error;
  }
}

export async function ingestExport(input: { export_path: string; config: ServiceConfig }) {
  return withFallback(
    () =>
      post<{
        messages_indexed: number;
        chunks_created: number;
        index_size: number;
        backend: string;
        embedding_backend: string;
      }>("/ingest/discord-export", input),
    () => demoIngest(),
  );
}

export async function searchExport(input: {
  export_path: string;
  query: string;
  limit: number;
  config: ServiceConfig;
}): Promise<{ results: import("../types").SearchResult[] }> {
  return withFallback(
    () => post("/workflow/search-export", input),
    () => demoSearch(input.query, input.limit),
  );
}

export async function timelineExport(input: {
  export_path: string;
  query: string;
  limit: number;
  config: ServiceConfig;
}): Promise<{ events: import("../types").TimelineEvent[] }> {
  return withFallback(
    () => post("/workflow/timeline-export", input),
    () => demoTimeline(input.query, input.limit),
  );
}

export async function evaluateExport(input: {
  export_path: string;
  evaluation_set_path: string;
  limit: number;
  config: ServiceConfig;
}): Promise<{
  summary: import("../types").EvaluationSummary;
  per_query: Array<Record<string, unknown>>;
}> {
  return withFallback(
    () => post("/workflow/evaluate", input),
    () => demoEvaluate(input.limit),
  );
}

export async function compareBackends(input: {
  export_path: string;
  evaluation_set_path: string;
  specs: string[];
  limit: number;
  skip_unavailable: boolean;
  config: ServiceConfig;
}): Promise<{
  comparisons: import("../types").ComparisonSummary[];
  failures: { label: string; error: string }[];
}> {
  return withFallback(
    () => post("/workflow/compare-backends", input),
    () => demoCompare(input.specs, input.limit),
  );
}

// Try the live API first; if it's unreachable, mark demo mode and use the
// in-browser engine instead. If the demo also fails, surface that error.
async function withFallback<T>(live: () => Promise<T>, demo: () => Promise<T>): Promise<T> {
  if (demoMode) {
    return demo();
  }
  try {
    return await live();
  } catch {
    enableDemoMode();
    return demo();
  }
}

export { demoExportMessage };
