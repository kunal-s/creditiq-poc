import { Link } from "@tanstack/react-router";
import { CITATIONS, type CiteTarget, type Citation } from "@/data/memo";
import { cn } from "@/lib/utils";

const TARGET_LABEL: Record<CiteTarget, string> = {
  spread: "Financial spread",
  "cross-verification": "Cross-verification",
  data: "Data acquisition",
  identity: "Entity resolution",
  policy: "Ratio and policy",
};

export type { Citation };

/** Stable display number for each citation, in registry order — reads like a footnote. */
const CITE_NUMBER: Record<string, number> = Object.fromEntries(
  Object.keys(CITATIONS).map((k, i) => [k, i + 1]),
);

export function CiteRef({
  cite,
  appraisalId,
  onInspect,
  active,
}: {
  cite: string;
  appraisalId: string;
  onInspect: (id: string) => void;
  active?: boolean;
}) {
  const c = CITATIONS[cite];
  if (!c) return null;
  void appraisalId;
  return (
    <button
      type="button"
      onClick={() => onInspect(cite)}
      title={`${c.claim} — ${c.source}`}
      className={cn(
        "mx-0.5 inline-flex h-[15px] translate-y-[-1px] items-center rounded-sm border px-1 align-middle text-[10px] font-medium leading-none transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-info/35 bg-info-soft text-info hover:border-info hover:bg-info hover:text-background",
      )}
    >
      {CITE_NUMBER[c.id] ?? "•"}
    </button>
  );
}

/** Renders a paragraph, turning [[citationId]] markers into clickable citations. */
export function CitedText({
  text,
  appraisalId,
  onInspect,
  activeCite,
}: {
  text: string;
  appraisalId: string;
  onInspect: (id: string) => void;
  activeCite?: string | null;
}) {
  const parts = text.split(/(\[\[[a-z0-9-]+\]\])/gi);
  return (
    <>
      {parts.map((p, i) => {
        const m = /^\[\[([a-z0-9-]+)\]\]$/i.exec(p);
        if (!m) return <span key={i}>{p}</span>;
        return (
          <CiteRef
            key={i}
            cite={m[1]!}
            appraisalId={appraisalId}
            onInspect={onInspect}
            active={activeCite === m[1]}
          />
        );
      })}
    </>
  );
}

export function stripCitations(text: string) {
  return text.replace(/\[\[[a-z0-9-]+\]\]/gi, "").replace(/\s+([.,;])/g, "$1").replace(/\s{2,}/g, " ").trim();
}

export function CitationInspector({
  cite,
  appraisalId,
  onClose,
}: {
  cite: string;
  appraisalId: string;
  onClose: () => void;
}) {
  const c = CITATIONS[cite];
  if (!c) return null;
  return (
    <div className="rounded border border-info/30 bg-info-soft/40 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[12.5px] font-semibold text-foreground">{c.claim}</p>
          <p className="mt-0.5 text-[11.5px] text-muted-foreground">{c.source}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-border bg-surface px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-muted"
        >
          Close
        </button>
      </div>
      <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90">{c.detail}</p>
      <div className="mt-2">
        {c.to !== "policy" ? (
          <Link
            to={`/appraisals/$id/${c.to}`}
            params={{ id: appraisalId }}
            {...(c.anchor ? { hash: c.anchor.slice(1) } : {})}
            className="text-[12px] font-medium text-primary hover:underline"
          >
            Open in {TARGET_LABEL[c.to]} →
          </Link>
        ) : (
          <Link to="/admin/policy" className="text-[12px] font-medium text-primary hover:underline">
            Open in {TARGET_LABEL[c.to]} →
          </Link>
        )}
      </div>
    </div>
  );
}
