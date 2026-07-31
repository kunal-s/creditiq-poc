import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { ArrowRight, RefreshCw, Search, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { BORROWERS, type BorrowerRecord } from "@/data/portfolio";
import { ROUTING, useMemoState } from "@/data/memo";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/memos")({
  head: () => {
    const title = "Memo Library — CreditIQ";
    const description =
      "Every borrower's Credit Appraisal Memoranda and versions for the West Region book, with status, internal rating, last update and next review date.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary" },
      ],
    };
  },
  component: MemoLibrary,
});

const RATING_TONE: Record<string, string> = {
  "CCB-1": "border-positive/40 bg-positive-soft text-positive",
  "CCB-2": "border-positive/40 bg-positive-soft text-positive",
  "CCB-3": "border-border bg-muted text-foreground",
  "CCB-4": "border-flag/40 bg-flag-soft text-flag",
  "CCB-5": "border-flag/40 bg-flag-soft text-flag",
  "CCB-6": "border-critical/40 bg-critical-soft text-critical",
};

const STATUS_TONE: Record<string, string> = {
  "In committee review": "text-info",
  Completed: "text-positive",
  Drafting: "text-foreground",
  "In preparation": "text-muted-foreground",
  "Refresh due": "text-flag",
};

function MemoLibrary() {
  const m = useMemoState();
  const [q, setQ] = useState("");
  const [rating, setRating] = useState("all");
  const [status, setStatus] = useState("all");
  const [review, setReview] = useState("all");
  const [sort, setSort] = useState<"updated" | "review" | "name">("updated");

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const filtered = BORROWERS.filter((b) => {
      if (needle && ![b.name, b.appraisalId, b.sector, b.gstin, b.rm].some((v) => v.toLowerCase().includes(needle)))
        return false;
      if (rating !== "all" && b.rating !== rating) return false;
      if (status !== "all" && b.status !== status) return false;
      if (review === "60" && b.nextReviewSort > 20260930) return false;
      if (review === "none" && b.nextReviewSort !== 99999999) return false;
      return true;
    });
    const sorted = [...filtered];
    if (sort === "updated") sorted.sort((a, b) => b.lastUpdatedSort - a.lastUpdatedSort);
    if (sort === "review") sorted.sort((a, b) => a.nextReviewSort - b.nextReviewSort);
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    return sorted;
  }, [q, rating, status, review, sort]);

  const ratings = [...new Set(BORROWERS.map((b) => b.rating))].sort();
  const statuses = [...new Set(BORROWERS.map((b) => b.status))];
  const totalMemos = BORROWERS.reduce((n, b) => n + b.memos, 0);

  return (
    <div className="pb-10">
      <PageHeader
        eyebrow="Portfolio"
        title="Memo Library"
        purpose="Every borrower on the West Region book with its memo history, current internal rating and next review date. Open a dossier to see the versions and run a refresh."
        actions={
          <Link
            to="/borrowers/$slug"
            params={{ slug: "northwind-manufacturing" }}
            className="flex h-8 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:opacity-90"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh Northwind
          </Link>
        }
      />

      <div className="space-y-4 px-6 py-5">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            { label: "Borrowers on the book", value: `${BORROWERS.length} in West Region`, note: `${totalMemos} memos on record` },
            {
              label: "Awaiting a decision",
              value: m.submitted ? "1 with the credit manager" : "1 in committee review",
              note: m.submitted
                ? `CAM-2026-0418 submitted ${m.submitted.at} to ${ROUTING.reviewer}`
                : `Northwind Manufacturing Ltd, rated ${m.rating}, with ${ROUTING.reviewer}`,
            },
            { label: "Review falling due", value: "1 within 60 days", note: "Northwind Manufacturing Ltd, 31 August 2026" },
            { label: "Retention", value: "10 years from sanction", note: "Per the bank's record-retention policy" },
          ].map((c) => (
            <div key={c.label} className="rounded border border-border bg-surface px-4 py-3">
              <p className="field-label">{c.label}</p>
              <p className="mt-1 text-[14px] font-semibold text-foreground">{c.value}</p>
              <p className="mt-0.5 text-[12px] text-muted-foreground">{c.note}</p>
            </div>
          ))}
        </div>

        <Panel
          title="Borrowers and memos"
          subtitle={`${rows.length} of ${BORROWERS.length} borrowers shown`}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Borrower, reference, GSTIN, RM"
                  aria-label="Search the memo library"
                  className="h-8 w-56 rounded border border-border bg-background pl-7 pr-2 text-[12.5px] text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                />
              </div>
              <Select label="Rating" value={rating} onChange={setRating} options={[["all", "All ratings"], ...ratings.map((r) => [r, r] as [string, string])]} />
              <Select label="Stage" value={status} onChange={setStatus} options={[["all", "All stages"], ...statuses.map((s) => [s, s] as [string, string])]} />
              <Select
                label="Review"
                value={review}
                onChange={setReview}
                options={[
                  ["all", "Any review date"],
                  ["60", "Due within 60 days"],
                  ["none", "No review set"],
                ]}
              />
              <Select
                label="Sort"
                value={sort}
                onChange={(v) => setSort(v as typeof sort)}
                options={[
                  ["updated", "Last updated"],
                  ["review", "Next review"],
                  ["name", "Borrower A–Z"],
                ]}
              />
            </div>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-[13px]">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Borrower</th>
                  <th className="px-4 py-2 font-medium">Latest memo</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Rating</th>
                  <th className="px-4 py-2 text-right font-medium">Exposure</th>
                  <th className="px-4 py-2 font-medium">Last updated</th>
                  <th className="px-4 py-2 font-medium">Next review</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((b) => (
                  <Row key={b.slug} b={b} />
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-[13px] text-muted-foreground">
                      No borrower matches those filters. Clear the search or widen the rating and stage filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="rounded border border-info/30 bg-info-soft/50 px-4 py-3">
          <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-foreground">
            <Sparkles className="h-3.5 w-3.5 text-info" /> Copilot on this library
          </p>
          <p className="mt-1 text-[12.5px] text-muted-foreground">
            Ask which borrowers are due for review, or what changed for a borrower since its last memo. Open the{" "}
            <Link to="/borrowers/$slug" params={{ slug: "northwind-manufacturing" }} className="font-medium text-primary hover:underline">
              Northwind dossier
            </Link>{" "}
            to run a refresh and see the change highlight against v4.
          </p>
        </div>
      </div>
    </div>
  );
}

function Row({ b }: { b: BorrowerRecord }) {
  const dueSoon = b.nextReviewSort <= 20260930;
  return (
    <tr className="group hover:bg-muted/50">
      <td className="px-4 py-2.5">
        <Link to="/borrowers/$slug" params={{ slug: b.slug }} className="font-medium text-foreground hover:text-primary">
          {b.name}
        </Link>
        <div className="mt-0.5 text-[11.5px] text-muted-foreground">
          {b.sector} · {b.branch}
        </div>
      </td>
      <td className="px-4 py-2.5">
        <Link
          to="/appraisals/$id/draft"
          params={{ id: b.appraisalId }}
          className="tabular text-foreground hover:text-primary hover:underline"
        >
          {b.appraisalId}
        </Link>
        <div className="mt-0.5 text-[11.5px] text-muted-foreground">
          {b.memos} version{b.memos === 1 ? "" : "s"} · {b.analyst}
        </div>
      </td>
      <td className={cn("px-4 py-2.5 text-[12.5px] font-medium", STATUS_TONE[b.status])}>{b.status}</td>
      <td className="px-4 py-2.5">
        <span className={cn("inline-flex items-center rounded border px-1.5 py-0.5 text-[11.5px] font-medium", RATING_TONE[b.rating] ?? "border-border bg-muted")}>
          {b.rating}
        </span>
        <span className="ml-1.5 text-[11.5px] text-muted-foreground">{b.ratingLabel}</span>
      </td>
      <td className="px-4 py-2.5 text-right tabular">{b.exposure}</td>
      <td className="px-4 py-2.5 tabular text-muted-foreground">{b.lastUpdated}</td>
      <td className={cn("px-4 py-2.5 tabular", dueSoon ? "font-medium text-flag" : "text-muted-foreground")}>{b.nextReview}</td>
      <td className="px-4 py-2.5 text-right">
        <Link
          to="/borrowers/$slug"
          params={{ slug: b.slug }}
          className="inline-flex items-center gap-1 text-[12px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
        >
          Open dossier <ArrowRight className="h-3 w-3" />
        </Link>
      </td>
    </tr>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <label className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 rounded border border-border bg-background px-2 text-[12.5px] normal-case tracking-normal text-foreground focus:border-primary focus:outline-none"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}
