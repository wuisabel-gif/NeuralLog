type Props = {
  label: string;
  value: string | number;
};

export default function MetricTile({ label, value }: Props) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="mb-2 text-[11px] uppercase tracking-[0.2em] text-neurallog-fog">{label}</div>
      <div className="font-display text-2xl text-white">{value}</div>
    </div>
  );
}
