import { Link } from "@tanstack/react-router";
import { Sparkles } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  purpose,
  actions,
}: {
  eyebrow?: string;
  title: string;
  purpose: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border bg-surface px-6 py-4">
      <div className="min-w-0">
        {eyebrow && <p className="field-label">{eyebrow}</p>}
        <h1 className="text-[19px] font-semibold tracking-tight text-foreground">{title}</h1>
        <p className="mt-1 max-w-3xl text-[13px] text-muted-foreground">{purpose}</p>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function PlaceholderPage({
  eyebrow,
  title,
  purpose,
  facts,
  aiAction,
}: {
  eyebrow: string;
  title: string;
  purpose: string;
  facts: { label: string; value: ReactNode }[];
  aiAction: string;
}) {
  return (
    <div>
      <PageHeader eyebrow={eyebrow} title={title} purpose={purpose} />
      <div className="grid gap-4 px-6 py-5 lg:grid-cols-3">
        <div className="rounded border border-border bg-surface lg:col-span-2">
          <p className="border-b border-border px-4 py-2.5 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
            Working context
          </p>
          <dl className="divide-y divide-border">
            {facts.map((f) => (
              <div key={f.label} className="flex gap-4 px-4 py-2.5 text-[13px]">
                <dt className="w-52 shrink-0 text-muted-foreground">{f.label}</dt>
                <dd className="min-w-0 flex-1 text-foreground">{f.value}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="space-y-3">
          <div className="rounded border border-border bg-surface p-4">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> Inline AI action
            </p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">{aiAction}</p>
            <button className="mt-3 w-full rounded bg-primary px-3 py-1.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90">
              Run with copilot
            </button>
          </div>
          <div className="rounded border border-border bg-surface p-4 text-[12.5px] leading-relaxed text-muted-foreground">
            Return to the{" "}
            <Link to="/" className="font-medium text-primary hover:underline">
              Credit Workbench
            </Link>{" "}
            or open{" "}
            <Link to="/appraisals" className="font-medium text-primary hover:underline">
              My Appraisals
            </Link>
            .
          </div>
        </div>
      </div>
    </div>
  );
}