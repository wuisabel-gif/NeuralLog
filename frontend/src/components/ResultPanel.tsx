import { Alert, Badge, Card } from "flowbite-react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

type Props = {
  content: React.ReactNode;
  error?: string | null;
  loading?: boolean;
};

export default function ResultPanel({ content, error, loading }: Props) {
  if (loading) {
    return (
      <div className="rounded-3xl border border-white/10 bg-neurallog-panel/90 p-6 shadow-panel">
        <div className="flex items-center gap-3 text-neurallog-fog">
          <CheckCircle2 className="h-5 w-5 text-neurallog-mint" />
          <span>NeuralLog is processing your request.</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert color="failure" icon={AlertTriangle} className="border border-red-400/30 bg-red-500/10">
        <span className="font-display text-base">Request failed</span>
        <p className="mt-2 text-sm">{error}</p>
      </Alert>
    );
  }

  return (
    <Card className="border border-white/10 bg-neurallog-panel/90 shadow-panel">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl text-white">Results</h2>
          <p className="mt-1 text-sm text-neurallog-fog">Readable summaries first, raw data only when you need it.</p>
        </div>
        <Badge color="success" className="border border-neurallog-mint/30 bg-neurallog-mint/10 text-neurallog-mint">
          Live API
        </Badge>
      </div>
      {content}
    </Card>
  );
}
