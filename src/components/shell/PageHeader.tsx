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
