import { createFileRoute, Link, notFound, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { ArrowRight, FileCheck2, FileUp, Info, Sparkles, Trash2, UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel, SourceChip } from "@/components/identity/chips";
import { getAppraisal } from "@/data/seed";
import {
  ACCEPTED_UPLOADS,
  INGESTED_UPLOADS,
  addFallbackUpload,
  setAcqState,
  useAcqState,
} from "@/data/acquisition";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/appraisals/$id/upload")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Manual upload fallback — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description =
      "Accept supplied statements when Account Aggregator consent is declined or a bank is unreachable. Anything supplied here is retained with provenance 'fallback' rather than 'consent'.";
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
  component: ManualUpload,
});

function ManualUpload() {
  const { id } = Route.useParams();
  const a = getAppraisal(id);
  if (!a) throw notFound();
  const acq = useAcqState();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [removed, setRemoved] = useState<string[]>([]);

  const ingest = (name: string) => {
    addFallbackUpload(name, "Bank statement · fallback");
    toast("Document ingested by fallback", {
      description: `${name} retained against ${a.id} with provenance 'fallback'. The bank-data row on the console is now received.`,
    });
  };

  const existing = INGESTED_UPLOADS.filter((u) => !removed.includes(u.id));

  return (
    <div>
      <PageHeader
        eyebrow={`Appraisal ${a.id} · Data · Fallback`}
        title="Manual upload fallback"
        purpose="For when consent is declined or a bank cannot be reached. Documents supplied here are usable, but they carry lower assurance than data fetched under consent and are labelled accordingly everywhere they are used."
        actions={
          <Link
            to="/appraisals/$id/data"
            params={{ id: a.id }}
            className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
          >
            Back to acquisition console <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        }
      />

      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          {acq.bank === "declined" && (
            <div className="flex items-start gap-2 rounded border border-flag/35 bg-flag-soft px-3 py-2.5 text-[12.5px] text-flag-foreground">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              The borrower declined the Account Aggregator request for accounts 4471 and 2205. Supply
              the statements here to unblock the spread.
            </div>
          )}

          <Panel title="Supply a document" subtitle={`${a.borrower} · PAN ${a.pan}`}>
            <div className="p-4">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  const f = e.dataTransfer.files?.[0];
                  ingest(f?.name ?? "Meridian_Bank_4471_Apr2025-Mar2026.pdf");
                }}
                className={cn(
                  "flex flex-col items-center justify-center rounded border border-dashed border-border bg-surface-muted px-6 py-10 text-center",
                  dragging && "border-primary bg-primary/5",
                )}
              >
                <UploadCloud className="h-6 w-6 text-muted-foreground" />
                <p className="mt-2 text-[13px] font-medium text-foreground">
                  Drop a statement or document here
                </p>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  PDF, XLSX or CSV up to 40 MB · bank-issued files must be password free
                </p>
                <input
                  ref={inputRef}
                  type="file"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) ingest(f.name);
                    e.target.value = "";
                  }}
                />
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    <FileUp className="h-3.5 w-3.5" /> Upload
                  </button>
                  <button
                    type="button"
                    onClick={() => ingest("Meridian_Bank_4471_Apr2025-Mar2026.pdf")}
                    className="flex h-9 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
                  >
                    Use the statement Marcus emailed
                  </button>
                </div>
              </div>

              <div className="mt-3 flex items-start gap-2 rounded border border-border bg-surface-muted px-3 py-2.5 text-[12px] text-muted-foreground">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Provenance note: anything supplied here is recorded as{" "}
                <span className="font-medium text-foreground">fallback</span>, not{" "}
                <span className="font-medium text-foreground">consent</span>. Figures traced to it
                carry that label in the spread, the memo citation trail and the audit walk-through.
              </div>
            </div>
          </Panel>

          <Panel title="Accepted document types">
            <ul className="divide-y divide-border">
              {ACCEPTED_UPLOADS.map((t) => (
                <li key={t} className="px-4 py-2 text-[12.5px] text-muted-foreground">
                  {t}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel
            title="Already ingested for this appraisal"
            subtitle={`${existing.length + acq.fallbackUploads.length} documents held against ${a.id}`}
          >
            <ul className="divide-y divide-border">
              {existing.map((u) => (
                <li key={u.id} className="flex items-start gap-3 px-4 py-3">
                  <FileCheck2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] font-medium text-foreground">{u.name}</p>
                    <p className="text-[11.5px] text-muted-foreground">
                      {u.kind} · {u.size} · {u.uploadedBy} · {u.uploadedAt}
                    </p>
                    <p className="text-[11.5px] text-muted-foreground">{u.detail}</p>
                  </div>
                  <SourceChip source={u.provenance} />
                  <button
                    type="button"
                    onClick={() => {
                      setRemoved((r) => [...r, u.id]);
                      toast("Document removed", { description: `${u.name} detached from ${a.id}.` });
                    }}
                    className="flex h-7 items-center gap-1 rounded border border-border px-2 text-[11.5px] text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <Trash2 className="h-3 w-3" /> Remove
                  </button>
                </li>
              ))}
              {acq.fallbackUploads.map((u) => (
                <li key={u.id} className="flex items-start gap-3 px-4 py-3">
                  <FileCheck2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] font-medium text-foreground">{u.name}</p>
                    <p className="text-[11.5px] text-muted-foreground">
                      {u.kind} · Elena Rossi · {u.uploadedAt}
                    </p>
                  </div>
                  <SourceChip source="Fallback" />
                </li>
              ))}
            </ul>
            {acq.fallbackUploads.length > 0 && (
              <div className="border-t border-border px-4 py-3">
                <button
                  type="button"
                  onClick={() => navigate({ to: "/appraisals/$id/data", params: { id: a.id } })}
                  className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Return to console — bank data received by fallback{" "}
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </Panel>
        </div>

        <div className="space-y-3">
          <div className="rounded border border-border bg-surface p-4">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> Inline AI action
            </p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
              Check that a supplied document belongs to the borrower on file — name, PAN, account
              numbers and period — before it is used in the spread.
            </p>
            <button
              type="button"
              onClick={() =>
                toast("Upload matched to borrower", {
                  description:
                    "Account holder 'Northwind Manufacturing Ltd', PAN AABCN4521Q and account 4471 all match the confirmed entity. Period covers 01 April 2025 to 31 March 2026 with no missing months.",
                })
              }
              className="mt-3 flex h-8 w-full items-center justify-center rounded bg-primary text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              Check this upload matches the borrower on file
            </button>
          </div>

          <div className="rounded border border-border bg-surface p-4 text-[12.5px] leading-relaxed text-muted-foreground">
            Prefer consent where it is available — it is faster and carries higher assurance. Reopen
            the{" "}
            <Link
              to="/appraisals/$id/consent"
              params={{ id: a.id }}
              onClick={() => setAcqState({ bank: "requested" })}
              className="font-medium text-primary hover:underline"
            >
              consent journey
            </Link>{" "}
            to send the borrower a fresh request.
          </div>
        </div>
      </div>
    </div>
  );
}
