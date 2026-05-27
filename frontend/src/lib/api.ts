import type { ServiceConfig } from "../types";

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

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
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
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error("Unable to reach NeuralLog API");
  }
  return response.json();
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
  return post("/workflow/export-discord", input);
}

export async function ingestExport(input: { export_path: string; config: ServiceConfig }) {
  return post<{
    messages_indexed: number;
    chunks_created: number;
    index_size: number;
    backend: string;
    embedding_backend: string;
  }>("/ingest/discord-export", input);
}

export async function searchExport(input: {
  export_path: string;
  query: string;
  limit: number;
  config: ServiceConfig;
}): Promise<{ results: import("../types").SearchResult[] }> {
  return post("/workflow/search-export", input);
}

export async function timelineExport(input: {
  export_path: string;
  query: string;
  limit: number;
  config: ServiceConfig;
}): Promise<{ events: import("../types").TimelineEvent[] }> {
  return post("/workflow/timeline-export", input);
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
  return post("/workflow/evaluate", input);
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
  return post("/workflow/compare-backends", input);
}
