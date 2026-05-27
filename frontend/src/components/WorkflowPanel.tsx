import { Button, Card, Label, Select, TextInput, Textarea } from "flowbite-react";
import { Download, GitCompare, Radar, Search, TestTube2, Waypoints } from "lucide-react";
import type { ServiceConfig } from "../types";

type Props = {
  tokenKind: "bot" | "user";
  setTokenKind: (value: "bot" | "user") => void;
  token: string;
  setToken: (value: string) => void;
  channelId: string;
  setChannelId: (value: string) => void;
  outputPath: string;
  setOutputPath: (value: string) => void;
  exportPath: string;
  setExportPath: (value: string) => void;
  evaluationPath: string;
  setEvaluationPath: (value: string) => void;
  query: string;
  setQuery: (value: string) => void;
  limit: number;
  setLimit: (value: number) => void;
  compareSpecs: string;
  setCompareSpecs: (value: string) => void;
  config: ServiceConfig;
  setConfig: (updater: (current: ServiceConfig) => ServiceConfig) => void;
  onExport: () => void;
  onIngest: () => void;
  onSearch: () => void;
  onTimeline: () => void;
  onEvaluate: () => void;
  onCompare: () => void;
};

export default function WorkflowPanel(props: Props) {
  return (
    <Card className="border border-white/10 bg-neurallog-panel/90 shadow-panel">
      <div className="mb-5">
        <h2 className="font-display text-2xl text-white">Workflow Controls</h2>
        <p className="mt-1 text-sm text-neurallog-fog">
          Start with the sample export and sample evaluation set if you just want to try the system first.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Token Type">
          <Select
            value={props.tokenKind}
            onChange={(event) => props.setTokenKind(event.target.value as "bot" | "user")}
            color="gray"
          >
            <option value="bot">bot token</option>
            <option value="user">user token</option>
          </Select>
        </Field>

        <Field label="Discord Token">
          <TextInput
            type="password"
            placeholder="Paste bot or user token"
            value={props.token}
            onChange={(event) => props.setToken(event.target.value)}
            color="gray"
          />
        </Field>

        <Field label="Channel ID">
          <TextInput
            placeholder="123456789012345678"
            value={props.channelId}
            onChange={(event) => props.setChannelId(event.target.value)}
            color="gray"
          />
        </Field>

        <Field label="Export Output Path">
          <TextInput value={props.outputPath} onChange={(event) => props.setOutputPath(event.target.value)} color="gray" />
        </Field>

        <Field label="Discord Export Path" full>
          <TextInput value={props.exportPath} onChange={(event) => props.setExportPath(event.target.value)} color="gray" />
        </Field>

        <Field label="Evaluation Set Path" full>
          <TextInput value={props.evaluationPath} onChange={(event) => props.setEvaluationPath(event.target.value)} color="gray" />
        </Field>

        <Field label="Query" full>
          <Textarea rows={3} value={props.query} onChange={(event) => props.setQuery(event.target.value)} color="gray" />
        </Field>

        <Field label="Limit">
          <TextInput
            type="number"
            value={String(props.limit)}
            onChange={(event) => props.setLimit(Number(event.target.value || 5))}
            color="gray"
          />
        </Field>

        <Field label="Vector Backend">
          <Select
            value={props.config.backend}
            onChange={(event) => props.setConfig((current) => ({ ...current, backend: event.target.value as ServiceConfig["backend"] }))}
            color="gray"
          >
            <option value="auto">auto</option>
            <option value="inmemory">inmemory</option>
            <option value="faiss">faiss</option>
          </Select>
        </Field>

        <Field label="Embedding Backend">
          <Select
            value={props.config.embedding_backend}
            onChange={(event) =>
              props.setConfig((current) => ({
                ...current,
                embedding_backend: event.target.value as ServiceConfig["embedding_backend"],
              }))
            }
            color="gray"
          >
            <option value="hash">hash</option>
            <option value="sentence-transformers">sentence-transformers</option>
            <option value="openai">openai</option>
          </Select>
        </Field>

        <Field label="Embedding Model">
          <TextInput
            value={props.config.embedding_model ?? ""}
            onChange={(event) => props.setConfig((current) => ({ ...current, embedding_model: event.target.value }))}
            color="gray"
          />
        </Field>

        <Field label="Batch Size">
          <TextInput
            type="number"
            value={String(props.config.embedding_batch_size ?? 32)}
            onChange={(event) =>
              props.setConfig((current) => ({
                ...current,
                embedding_batch_size: Number(event.target.value || 32),
              }))
            }
            color="gray"
          />
        </Field>

        <Field label="Cache Path" full>
          <TextInput
            value={props.config.embedding_cache_path ?? ""}
            onChange={(event) => props.setConfig((current) => ({ ...current, embedding_cache_path: event.target.value }))}
            color="gray"
          />
        </Field>

        <Field label="Compare Specs" full>
          <TextInput value={props.compareSpecs} onChange={(event) => props.setCompareSpecs(event.target.value)} color="gray" />
        </Field>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <ActionButton icon={Download} onClick={props.onExport}>Export from Discord</ActionButton>
        <ActionButton icon={Radar} onClick={props.onIngest}>Ingest</ActionButton>
        <ActionButton icon={Search} onClick={props.onSearch}>Search Export</ActionButton>
        <ActionButton icon={Waypoints} onClick={props.onTimeline}>Timeline</ActionButton>
        <ActionButton icon={TestTube2} onClick={props.onEvaluate}>Evaluate</ActionButton>
        <ActionButton icon={GitCompare} onClick={props.onCompare}>Compare Backends</ActionButton>
      </div>
    </Card>
  );
}

function Field({
  label,
  children,
  full = false,
}: {
  label: string;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <div className={full ? "md:col-span-2" : ""}>
      <div className="mb-2">
        <Label value={label} className="font-mono uppercase tracking-[0.16em] text-neurallog-fog" />
      </div>
      {children}
    </div>
  );
}

function ActionButton({
  icon: Icon,
  children,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <Button
      onClick={onClick}
      className="border-0 bg-neurallog-mint text-neurallog-ink hover:bg-lime-300 focus:ring-lime-300"
    >
      <Icon className="mr-2 h-4 w-4" />
      {children}
    </Button>
  );
}
