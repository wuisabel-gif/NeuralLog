export type ServiceConfig = {
  backend: "auto" | "inmemory" | "faiss";
  embedding_backend: "hash" | "sentence-transformers" | "openai";
  embedding_model: string | null;
  embedding_dimensions?: number | null;
  embedding_batch_size?: number | null;
  embedding_cache_path?: string | null;
};

export type SearchResult = {
  chunk_id: string;
  score: number;
  channel_name: string;
  start_time: string;
  end_time: string;
  participants: string[];
  preview: string;
  message_ids: string[];
};

export type TimelineEvent = {
  timestamp: string;
  title: string;
  summary: string;
  channel_name: string;
  participants: string[];
  message_ids: string[];
};

export type EvaluationSummary = {
  queries_evaluated: number;
  mean_precision_at_k: number;
  mean_recall_at_k: number;
  mean_reciprocal_rank: number;
};

export type ComparisonSummary = {
  label: string;
  embedding_backend: string;
  embedding_model: string | null;
  summary: EvaluationSummary;
};
