import { ReactNode } from "react";

type Props = {
  eyebrow: string;
  title: string;
  children: ReactNode;
};

export default function InfoCard({ eyebrow, title, children }: Props) {
  return (
    <article className="rounded-3xl border border-white/10 bg-white/5 p-5 shadow-panel">
      <div className="mb-3 text-xs uppercase tracking-[0.25em] text-neurallog-mint">{eyebrow}</div>
      <h3 className="mb-3 font-display text-xl text-white">{title}</h3>
      <div className="space-y-2 text-sm leading-6 text-neurallog-fog">{children}</div>
    </article>
  );
}
