import { Badge, Card } from "flowbite-react";
import { Bot, Database, FileJson, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";
import InfoCard from "./components/InfoCard";
import MetricTile from "./components/MetricTile";
import ResultPanel from "./components/ResultPanel";
import WorkflowPanel from "./components/WorkflowPanel";
import {
  compareBackends,
  evaluateExport,
  exportDiscord,
  fetchHealth,
  ingestExport,
  searchExport,
  timelineExport,
} from "./lib/api";
import type { ComparisonSummary, EvaluationSummary, SearchResult, ServiceConfig, TimelineEvent } from "./types";

type ViewState =
  | { kind: "empty" }
  | { kind: "export"; payload: any }
  | { kind: "ingest"; payload: any }
  | { kind: "search"; results: SearchResult[] }
  | { kind: "timeline"; events: TimelineEvent[] }
  | { kind: "evaluate"; summary: EvaluationSummary; perQuery: any[] }
  | { kind: "compare"; comparisons: ComparisonSummary[]; failures: { label: string; error: string }[] };

type HealthState = {
  status: string;
  index_size: number;
  backend: string;
  embedding_backend: string;
};

const SAMPLE_EXPORT = "examples/sample-discord-export.json";
const SAMPLE_EVAL = "examples/sample-evaluation.json";

export default function App() {
  const [tokenKind, setTokenKind] = useState<"bot" | "user">("bot");
  const [token, setToken] = useState("");
  const [channelId, setChannelId] = useState("");
  const [outputPath, setOutputPath] = useState("exports/channel-export.json");
  const [exportPath, setExportPath] = useState(SAMPLE_EXPORT);
  const [evaluationPath, setEvaluationPath] = useState(SAMPLE_EVAL);
  const [query, setQuery] = useState("What did we do with mapping?");
  const [limit, setLimit] = useState(5);
  const [compareSpecs, setCompareSpecs] = useState(
    "hash, sentence-transformers:all-MiniLM-L6-v2, openai:text-embedding-3-small",
  );
  const [config, setConfig] = useState<ServiceConfig>({
    backend: "auto",
    embedding_backend: "hash",
    embedding_model: "all-MiniLM-L6-v2",
    embedding_batch_size: 32,
    embedding_cache_path: "neurallog-embeddings.sqlite3",
  });
  const [view, setView] = useState<ViewState>({ kind: "empty" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<HealthState>({
    status: "loading",
    index_size: 0,
    backend: "unknown",
    embedding_backend: "unknown",
  });

  useMemo(() => {
    void refreshHealth();
  }, []);

  async function refreshHealth() {
    try {
      const payload = await fetchHealth();
      setHealth(payload);
    } catch (apiError) {
      setHealth({
        status: "offline",
        index_size: 0,
        backend: "unknown",
        embedding_backend: "unknown",
      });
      setError(getErrorMessage(apiError));
    }
  }

  async function run(task: () => Promise<void>) {
    setLoading(true);
    setError(null);
    try {
      await task();
      await refreshHealth();
    } catch (apiError) {
      setError(getErrorMessage(apiError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen px-4 py-6 text-white md:px-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
        <section className="grid gap-5 xl:grid-cols-[1.45fr_0.95fr]">
          <Card className="border border-white/10 bg-neurallog-panel/90 shadow-panel">
            <div className="mb-3 text-xs uppercase tracking-[0.28em] text-neurallog-mint">Engineering Memory System</div>
            <h1 className="font-display text-5xl text-white md:text-7xl">NeuralLog</h1>
            <p className="mt-5 max-w-3xl text-base leading-7 text-neurallog-fog md:text-lg">
              Search Discord exports, reconstruct timelines, evaluate retrieval quality, and compare
              embedding backends from a frontend built for engineering workflows instead of raw debug output.
            </p>
          </Card>

          <Card className="border border-white/10 bg-neurallog-panel/90 shadow-panel">
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricTile label="Service" value={health.status} />
              <MetricTile label="Index Size" value={health.index_size} />
              <MetricTile label="Stack" value={`${health.backend} / ${health.embedding_backend}`} />
            </div>
          </Card>
        </section>

        <section className="grid gap-5 lg:grid-cols-3">
          <InfoCard eyebrow="Try First" title="Use the sample dataset">
            <p>Leave the sample export and sample evaluation paths in place if you just want to see the app work immediately.</p>
            <div className="flex flex-wrap gap-2 pt-2">
              <Badge color="success">Search Export</Badge>
              <Badge color="success">Timeline</Badge>
              <Badge color="success">Evaluate</Badge>
            </div>
          </InfoCard>

          <InfoCard eyebrow="Discord Export" title="Token and channel workflow">
            <p>Use a bot token when possible. The token and channel ID are only needed for creating a new export file from Discord.</p>
            <p>User tokens are riskier and can violate Discord policy.</p>
          </InfoCard>

          <InfoCard eyebrow="What NeuralLog Does" title="After the export exists">
            <p>Once a JSON export is available, NeuralLog can ingest it, search it semantically, reconstruct timelines, and evaluate retrieval quality.</p>
          </InfoCard>
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.03fr_1.17fr]">
          <WorkflowPanel
            tokenKind={tokenKind}
            setTokenKind={setTokenKind}
            token={token}
            setToken={setToken}
            channelId={channelId}
            setChannelId={setChannelId}
            outputPath={outputPath}
            setOutputPath={setOutputPath}
            exportPath={exportPath}
            setExportPath={setExportPath}
            evaluationPath={evaluationPath}
            setEvaluationPath={setEvaluationPath}
            query={query}
            setQuery={setQuery}
            limit={limit}
            setLimit={setLimit}
            compareSpecs={compareSpecs}
            setCompareSpecs={setCompareSpecs}
            config={config}
            setConfig={setConfig}
            onExport={() =>
              run(async () => {
                const payload = await exportDiscord({
                  token,
                  token_kind: tokenKind,
                  channel_id: channelId,
                  output_path: outputPath,
                  config,
                });
                setExportPath(payload.output_path ?? outputPath);
                setView({ kind: "export", payload });
              })
            }
            onIngest={() =>
              run(async () => {
                const payload = await ingestExport({
                  export_path: exportPath,
                  config,
                });
                setView({ kind: "ingest", payload });
              })
            }
            onSearch={() =>
              run(async () => {
                const payload = await searchExport({
                  export_path: exportPath,
                  query,
                  limit,
                  config,
                });
                setView({ kind: "search", results: payload.results });
              })
            }
            onTimeline={() =>
              run(async () => {
                const payload = await timelineExport({
                  export_path: exportPath,
                  query,
                  limit,
                  config,
                });
                setView({ kind: "timeline", events: payload.events });
              })
            }
            onEvaluate={() =>
              run(async () => {
                const payload = await evaluateExport({
                  export_path: exportPath,
                  evaluation_set_path: evaluationPath,
                  limit,
                  config,
                });
                setView({ kind: "evaluate", summary: payload.summary, perQuery: payload.per_query });
              })
            }
            onCompare={() =>
              run(async () => {
                const payload = await compareBackends({
                  export_path: exportPath,
                  evaluation_set_path: evaluationPath,
                  specs: compareSpecs.split(",").map((value) => value.trim()).filter(Boolean),
                  limit,
                  skip_unavailable: true,
                  config,
                });
                setView({ kind: "compare", comparisons: payload.comparisons, failures: payload.failures });
              })
            }
          />

          <ResultPanel loading={loading} error={error} content={renderView(view)} />
        </section>
      </div>
    </div>
  );
}

function renderView(view: ViewState) {
  if (view.kind === "empty") {
    return (
      <div className="grid min-h-[560px] place-items-center rounded-3xl border border-dashed border-white/10 bg-black/20 text-center">
        <div className="max-w-xl space-y-3 p-6">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-neurallog-mint/30 bg-neurallog-mint/10">
            <FileJson className="h-7 w-7 text-neurallog-mint" />
          </div>
          <h3 className="font-display text-3xl text-white">Ready to explore</h3>
          <p className="text-sm leading-7 text-neurallog-fog">
            Start with the sample export and sample evaluation set if you want a safe first run without needing a Discord token.
          </p>
        </div>
      </div>
    );
  }

  if (view.kind === "export") {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge color="success">Saved export</Badge>
          <Badge color="success">{view.payload.output_path}</Badge>
          <Badge color="success">Channel {view.payload.channel_id}</Badge>
        </div>
        <Card className="border border-white/10 bg-black/20">
          <h3 className="font-display text-2xl text-white">Discord export complete</h3>
          <p className="mt-2 text-sm leading-7 text-neurallog-fog">
            NeuralLog can now ingest or analyze the newly exported JSON file.
          </p>
        </Card>
      </div>
    );
  }

  if (view.kind === "ingest") {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricTile label="Messages Indexed" value={view.payload.messages_indexed} />
          <MetricTile label="Chunks Created" value={view.payload.chunks_created} />
          <MetricTile label="Index Size" value={view.payload.index_size} />
          <MetricTile label="Embedding Backend" value={view.payload.embedding_backend} />
        </div>
      </div>
    );
  }

  if (view.kind === "search") {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Badge color="success">{view.results.length} matches</Badge>
        </div>
        <div className="space-y-3">
          {view.results.map((result, index) => (
            <Card key={result.chunk_id} className="border border-white/10 bg-black/20">
              <div className="mb-2 text-xs uppercase tracking-[0.2em] text-neurallog-mint">Search Result {index + 1}</div>
              <h3 className="font-display text-2xl text-white">{headlineFromPreview(result.preview)}</h3>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <Badge color="gray">Score {result.score.toFixed(3)}</Badge>
                <Badge color="gray">{result.channel_name}</Badge>
                <Badge color="gray">{new Date(result.start_time).toLocaleString()}</Badge>
                <Badge color="gray">{result.participants.join(", ") || "No participants"}</Badge>
              </div>
              <p className="mt-4 text-sm leading-7 text-neurallog-fog">{result.preview}</p>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (view.kind === "timeline") {
    return (
      <div className="space-y-3">
        {view.events.map((event, index) => (
          <Card key={`${event.timestamp}-${index}`} className="border border-white/10 bg-black/20">
            <div className="mb-2 text-xs uppercase tracking-[0.2em] text-neurallog-mint">Timeline Event {index + 1}</div>
            <h3 className="font-display text-2xl text-white">{headlineFromPreview(event.summary)}</h3>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <Badge color="gray">{new Date(event.timestamp).toLocaleString()}</Badge>
              <Badge color="gray">{event.channel_name}</Badge>
              <Badge color="gray">{event.participants.join(", ") || "No participants"}</Badge>
            </div>
            <p className="mt-4 text-sm leading-7 text-neurallog-fog">{event.summary}</p>
          </Card>
        ))}
      </div>
    );
  }

  if (view.kind === "evaluate") {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricTile label="Queries" value={view.summary.queries_evaluated} />
          <MetricTile label="Mean Precision@K" value={view.summary.mean_precision_at_k.toFixed(3)} />
          <MetricTile label="Mean Recall@K" value={view.summary.mean_recall_at_k.toFixed(3)} />
          <MetricTile label="Mean Reciprocal Rank" value={view.summary.mean_reciprocal_rank.toFixed(3)} />
        </div>
        <div className="space-y-3">
          {view.perQuery.map((item, index) => (
            <Card key={`${item.query}-${index}`} className="border border-white/10 bg-black/20">
              <div className="mb-2 text-xs uppercase tracking-[0.2em] text-neurallog-mint">Query {index + 1}</div>
              <h3 className="font-display text-xl text-white">{item.query}</h3>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <Badge color="gray">Precision {Number(item.precision_at_k).toFixed(3)}</Badge>
                <Badge color="gray">Recall {Number(item.recall_at_k).toFixed(3)}</Badge>
                <Badge color="gray">MRR {Number(item.reciprocal_rank).toFixed(3)}</Badge>
              </div>
              <p className="mt-4 text-sm text-neurallog-fog">Relevant: {item.relevant_message_ids.join(", ")}</p>
              <p className="mt-2 text-sm text-neurallog-fog">Retrieved: {item.retrieved_message_ids.join(", ")}</p>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {view.comparisons.map((comparison, index) => (
          <Card key={`${comparison.label}-${index}`} className="border border-white/10 bg-black/20">
            <div className="mb-2 text-xs uppercase tracking-[0.2em] text-neurallog-mint">Rank {index + 1}</div>
            <h3 className="font-display text-2xl text-white">{comparison.label}</h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <MetricTile label="Precision@K" value={comparison.summary.mean_precision_at_k.toFixed(3)} />
              <MetricTile label="Recall@K" value={comparison.summary.mean_recall_at_k.toFixed(3)} />
              <MetricTile label="MRR" value={comparison.summary.mean_reciprocal_rank.toFixed(3)} />
            </div>
          </Card>
        ))}
      </div>

      {view.failures.length > 0 && (
        <Card className="border border-red-400/20 bg-red-500/10">
          <div className="mb-3 flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-red-300" />
            <h3 className="font-display text-xl text-white">Unavailable backends</h3>
          </div>
          <div className="space-y-2 text-sm text-neurallog-fog">
            {view.failures.map((failure) => (
              <p key={failure.label}>
                <strong className="text-white">{failure.label}:</strong> {failure.error}
              </p>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Something went wrong while talking to the NeuralLog API.";
}

function headlineFromPreview(text: string) {
  const cleaned = text.replace(/^\[[^\]]+\]\s*/, "").trim();
  const sentence = cleaned.split(".")[0]?.trim();
  return sentence && sentence.length > 0 ? sentence : cleaned || "Untitled result";
}
