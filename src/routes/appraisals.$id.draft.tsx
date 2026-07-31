import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileText,
  History,
  PenLine,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  Undo2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel, SourceChip } from "@/components/identity/chips";
import { CitationInspector, CitedText, stripCitations } from "@/components/memo/cited";
import { CURRENT_USER, getAppraisal } from "@/data/seed";
import { isBlocked, useXVState, FLAGS, OUTCOME_LABEL } from "@/data/crossverify";
import {
  REGENERATED,
  SECTIONS,
  bodyFor,
  isEdited,
  markRegenerated,
  recordOverride,
  revertSection,
  saveSectionEdit,
  useMemoState,
  type MemoSection,
} from "@/data/memo";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/appraisals/$id/draft")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `CAM draft and review — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description =
      "The full Credit Appraisal Memorandum in Continental Commercial Bank's template, every quantitative claim cited to its source, machine-drafted text separated from the analyst's own words.";
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
  component: DraftWorkspace,
});

function DraftWorkspace() {
  const { id } = Route.useParams();
  const a = getAppraisal(id);
  if (!a) throw notFound();

  const m = useMemoState();
  const xv = useXVState();
  const blocked = isBlocked(xv);

  const [sectionId, setSectionId] = useState(SECTIONS[0]!.id);
  const [cite, setCite] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [buffer, setBuffer] = useState("");
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [ovField, setOvField] = useState("");
  const [ovOriginal, setOvOriginal] = useState("");
  const [ovValue, setOvValue] = useState("");
  const [ovReason, setOvReason] = useState("");

  const section = useMemo(() => SECTIONS.find((s) => s.id === sectionId)!, [sectionId]);
  const body = bodyFor(m, section);
  const edited = isEdited(m, section.id);
  const sectionOverrides = m.overrides.filter((o) => o.scope === section.title);

  const startEdit = () => {
    setBuffer(body.join("\n\n"));
    setEditing(true);
  };

  const saveEdit = () => {
    const paras = buffer.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
    if (paras.length === 0) {
      toast.error("A section cannot be left empty.");
      return;
    }
    saveSectionEdit(section.id, paras, CURRENT_USER.name);
    setEditing(false);
    toast.success(`Section ${section.number} saved in your words`, {
      description: `Marked as analyst-authored, ${CURRENT_USER.name}, 31 July 2026 07:52.`,
    });
  };

  const regenerate = () => {
    const next = REGENERATED[section.id];
    if (!next) {
      toast.info("Copilot has no tighter draft for this section", {
        description: "Sections 1, 2, 3, 5 and 8 are already at the template's target length.",
      });
      return;
    }
    markRegenerated(section.id, next, CURRENT_USER.name);
    toast.success(`Section ${section.number} regenerated`, {
      description: "Tighter wording, every citation preserved. Edit it before you sign it off.",
    });
  };

  const applyOverride = () => {
    if (!ovField.trim() || !ovValue.trim() || ovReason.trim().length < 8) {
      toast.error("An override needs the figure, the new value and a reason of at least eight characters.");
      return;
    }
    recordOverride({
      scope: section.title,
      field: ovField.trim(),
      original: ovOriginal.trim() || "As drafted",
      override: ovValue.trim(),
      reason: ovReason.trim(),
      by: `${CURRENT_USER.name} · ${CURRENT_USER.role}`,
    });
    setOverrideOpen(false);
    setOvField("");
    setOvOriginal("");
    setOvValue("");
    setOvReason("");
    toast.success("Override recorded", { description: "The original value and your reason are both retained on the memo." });
  };

  const citedCount = SECTIONS.reduce(
    (n, s) => n + bodyFor(m, s).join(" ").split(/\[\[/).length - 1,
    0,
  );

  return (
    <div>
      <PageHeader
        eyebrow={`Appraisal ${a.id} · Draft and review`}
        title="CAM draft and review"
        purpose={`Continental Commercial Bank CAM template v4.2, drafted from the resolved evidence for ${a.borrower}. Every quantitative claim carries a citation you can follow. Machine-drafted text is marked; anything you change is recorded as yours.`}
        actions={
          <>
            <Link
              to="/appraisals/$id/cross-verification"
              params={{ id: a.id }}
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Cross-verification
            </Link>
            <Link
              to="/appraisals/$id/rating"
              params={{ id: a.id }}
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              Rating and recommendation
            </Link>
            <Link
              to="/appraisals/$id/submission"
              params={{ id: a.id }}
              className="flex h-9 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:opacity-90"
            >
              Submission <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </>
        }
      />

      <div className="grid gap-4 px-6 py-5 xl:grid-cols-[230px_minmax(0,1fr)_320px]">
        {/* section navigator */}
        <aside className="space-y-3">
          <div className="rounded border border-border bg-surface">
            <div className="border-b border-border px-3 py-2">
              <p className="field-label">CAM sections</p>
              <p className="mt-0.5 text-[11.5px] text-muted-foreground">Template v4.2 · 8 sections</p>
            </div>
            <nav className="p-1">
              {SECTIONS.map((s) => {
                const active = s.id === sectionId;
                const changed = isEdited(m, s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      setSectionId(s.id);
                      setEditing(false);
                      setCite(null);
                    }}
                    className={cn(
                      "flex w-full items-start gap-2 rounded px-2 py-1.5 text-left text-[12.5px] transition-colors",
                      active ? "bg-primary/10 text-foreground" : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    <span className={cn("mt-[1px] w-3 shrink-0 text-[11px] tabular-nums", active && "text-primary")}>
                      {s.number}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={cn("block leading-tight", active && "font-medium text-foreground")}>{s.title}</span>
                      {changed && (
                        <span className="mt-0.5 inline-flex items-center gap-1 text-[10.5px] text-positive">
                          <PenLine className="h-2.5 w-2.5" /> your words
                        </span>
                      )}
                    </span>
                  </button>
                );
              })}
            </nav>
          </div>

          <div className="rounded border border-border bg-surface p-3">
            <p className="field-label">Draft state</p>
            <dl className="mt-2 space-y-1.5 text-[12px]">
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Citations in memo</dt>
                <dd className="tabular-nums text-foreground">{citedCount}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Sections edited</dt>
                <dd className="tabular-nums text-foreground">
                  {Object.keys(m.edits).length} of {SECTIONS.length}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Overrides recorded</dt>
                <dd className="tabular-nums text-foreground">{m.overrides.length}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">First-cut rating</dt>
                <dd className="text-foreground">{m.rating}</dd>
              </div>
            </dl>
          </div>
        </aside>

        {/* memo body */}
        <div className="min-w-0 space-y-4">
          {blocked && (
            <div className="flex items-start gap-2 rounded border border-critical/30 bg-critical-soft px-3 py-2.5">
              <ShieldAlert className="mt-[2px] h-4 w-4 shrink-0 text-critical" />
              <p className="text-[12.5px] leading-relaxed text-foreground">
                The serious turnover finding is not yet adjudicated. You can draft and edit freely, but submission stays
                closed until it is dealt with.{" "}
                <Link
                  to="/appraisals/$id/cross-verification"
                  params={{ id: a.id }}
                  className="font-medium text-critical hover:underline"
                >
                  Open flag XV-0418-01 →
                </Link>
              </p>
            </div>
          )}

          <article className="rounded border border-border bg-surface">
            <header className="flex flex-wrap items-start justify-between gap-2 border-b border-border px-4 py-3">
              <div className="min-w-0">
                <p className="field-label">
                  Section {section.number} of {SECTIONS.length} · CCB CAM template v4.2
                </p>
                <h2 className="text-[15px] font-semibold text-foreground">{section.title}</h2>
                <p className="mt-0.5 text-[12px] text-muted-foreground">{section.summary}</p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {edited ? (
                  <span className="inline-flex items-center gap-1 rounded border border-positive/30 bg-positive-soft px-1.5 py-0.5 text-[10.5px] font-medium text-positive">
                    <PenLine className="h-2.5 w-2.5" /> Analyst-authored
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[10.5px] font-medium text-muted-foreground">
                    <Sparkles className="h-2.5 w-2.5" /> Machine-drafted
                  </span>
                )}
                <SourceChip source={`Drafted ${section.drafted}`} />
              </div>
            </header>

            <div className="border-b border-border px-4 py-2">
              <div className="flex flex-wrap items-center gap-2">
                {!editing ? (
                  <button
                    type="button"
                    onClick={startEdit}
                    className="flex h-8 items-center gap-1.5 rounded bg-primary px-2.5 text-[12px] font-medium text-primary-foreground hover:opacity-90"
                  >
                    <PenLine className="h-3.5 w-3.5" /> Edit in my words
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={saveEdit}
                      className="flex h-8 items-center gap-1.5 rounded bg-primary px-2.5 text-[12px] font-medium text-primary-foreground hover:opacity-90"
                    >
                      <Check className="h-3.5 w-3.5" /> Save as my wording
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditing(false)}
                      className="flex h-8 items-center rounded border border-border bg-surface px-2.5 text-[12px] text-foreground hover:bg-muted"
                    >
                      Cancel
                    </button>
                  </>
                )}
                <button
                  type="button"
                  onClick={regenerate}
                  className="flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] text-foreground hover:bg-muted"
                >
                  <Sparkles className="h-3.5 w-3.5 text-primary" /> Regenerate with copilot
                </button>
                <button
                  type="button"
                  onClick={() => setOverrideOpen((v) => !v)}
                  className="flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] text-foreground hover:bg-muted"
                >
                  <History className="h-3.5 w-3.5" /> Override a figure
                </button>
                <Link
                  to="/appraisals/$id/data"
                  params={{ id: a.id }}
                  className="flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] text-foreground hover:bg-muted"
                >
                  Request more data
                </Link>
                {edited && (
                  <button
                    type="button"
                    onClick={() => {
                      revertSection(section.id);
                      toast.info("Reverted to the machine draft", {
                        description: "Your version is dropped; the citation set is unchanged.",
                      });
                    }}
                    className="flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] text-muted-foreground hover:bg-muted"
                  >
                    <Undo2 className="h-3.5 w-3.5" /> Revert to draft
                  </button>
                )}
              </div>

              {overrideOpen && (
                <div className="mt-2 grid gap-2 rounded border border-flag/30 bg-flag-soft/40 p-3 md:grid-cols-2">
                  <label className="text-[11.5px] text-muted-foreground">
                    Figure being overridden
                    <input
                      value={ovField}
                      onChange={(e) => setOvField(e.target.value)}
                      placeholder="e.g. Assessed drawing power"
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                    />
                  </label>
                  <label className="text-[11.5px] text-muted-foreground">
                    Original value as drafted
                    <input
                      value={ovOriginal}
                      onChange={(e) => setOvOriginal(e.target.value)}
                      placeholder="e.g. INR 18.50 cr"
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                    />
                  </label>
                  <label className="text-[11.5px] text-muted-foreground">
                    Your value
                    <input
                      value={ovValue}
                      onChange={(e) => setOvValue(e.target.value)}
                      placeholder="e.g. INR 15.80 cr"
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                    />
                  </label>
                  <label className="text-[11.5px] text-muted-foreground">
                    Reason (retained with your name and the timestamp)
                    <input
                      value={ovReason}
                      onChange={(e) => setOvReason(e.target.value)}
                      placeholder="e.g. Sized on independently evidenced turnover"
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                    />
                  </label>
                  <div className="md:col-span-2">
                    <button
                      type="button"
                      onClick={applyOverride}
                      className="h-8 rounded bg-primary px-3 text-[12px] font-medium text-primary-foreground hover:opacity-90"
                    >
                      Record override
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="px-4 py-4">
              {editing ? (
                <>
                  <textarea
                    value={buffer}
                    onChange={(e) => setBuffer(e.target.value)}
                    rows={16}
                    className="w-full rounded border border-border bg-surface-muted p-3 text-[13px] leading-relaxed text-foreground"
                  />
                  <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                    Blank line separates paragraphs. Citation markers such as <code>[[dscr]]</code> stay live — keep them
                    where the number is still being claimed.
                  </p>
                </>
              ) : (
                <div className={cn("space-y-3", edited && "border-l-2 border-positive/60 pl-3")}>
                  {body.map((p, i) => (
                    <p key={i} className="text-[13.5px] leading-[1.75] text-foreground">
                      <CitedText text={p} appraisalId={a.id} onInspect={setCite} activeCite={cite} />
                    </p>
                  ))}
                </div>
              )}

              {section.facts && !editing && (
                <dl className="mt-4 grid gap-x-6 gap-y-1.5 border-t border-border pt-3 sm:grid-cols-2">
                  {section.facts.map((f) => (
                    <div key={f.label} className="flex items-baseline justify-between gap-3 text-[12.5px]">
                      <dt className="text-muted-foreground">{f.label}</dt>
                      <dd className="text-right font-medium text-foreground">
                        {f.value}
                        {f.cite && (
                          <button
                            type="button"
                            onClick={() => setCite(f.cite!)}
                            className="ml-1.5 text-[11px] font-normal text-info hover:underline"
                          >
                            source
                          </button>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}

              {sectionOverrides.length > 0 && (
                <div className="mt-4 rounded border border-flag/30 bg-flag-soft/40 p-3">
                  <p className="field-label">Overrides on this section</p>
                  <ul className="mt-2 space-y-2">
                    {sectionOverrides.map((o) => (
                      <li key={o.id} className="text-[12.5px] leading-relaxed text-foreground">
                        <span className="font-medium">{o.field}:</span>{" "}
                        <span className="text-muted-foreground line-through">{o.original}</span>{" "}
                        <ArrowRight className="inline h-3 w-3 text-muted-foreground" />{" "}
                        <span className="font-medium">{o.override}</span>
                        <span className="block text-[11.5px] text-muted-foreground">
                          {o.reason} · {o.by} · {o.at} · {o.id}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </article>

          <div className="flex items-center justify-between">
            <button
              type="button"
              disabled={section.number === "1"}
              onClick={() => {
                const i = SECTIONS.findIndex((s) => s.id === sectionId);
                if (i > 0) {
                  setSectionId(SECTIONS[i - 1]!.id);
                  setEditing(false);
                }
              }}
              className="flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] text-foreground hover:bg-muted disabled:opacity-40"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Previous section
            </button>
            <button
              type="button"
              disabled={sectionId === SECTIONS[SECTIONS.length - 1]!.id}
              onClick={() => {
                const i = SECTIONS.findIndex((s) => s.id === sectionId);
                if (i < SECTIONS.length - 1) {
                  setSectionId(SECTIONS[i + 1]!.id);
                  setEditing(false);
                }
              }}
              className="flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] text-foreground hover:bg-muted disabled:opacity-40"
            >
              Next section <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* right column: citation inspector + provenance */}
        <aside className="space-y-3">
          <Panel title="Citation" subtitle="Follow any claim to the evidence it came from.">
            <div className="p-3">
              {cite ? (
                <CitationInspector cite={cite} appraisalId={a.id} onClose={() => setCite(null)} />
              ) : (
                <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                  Click any citation marker in the memo body to see the claim, the source document and a link straight to
                  it. Nothing quantitative in this memo is uncited.
                </p>
              )}
            </div>
          </Panel>

          <Panel title="Findings carried into this memo">
            <ul className="divide-y divide-border">
              {FLAGS.map((f) => {
                const adj = xv.adjudications[f.id];
                return (
                  <li key={f.id} className="px-3 py-2">
                    <Link
                      to="/appraisals/$id/cross-verification"
                      params={{ id: a.id }}
                      className="text-[12.5px] font-medium text-foreground hover:underline"
                    >
                      {f.id} — {f.title}
                    </Link>
                    <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                      {adj ? `${OUTCOME_LABEL[adj.outcome]} · ${adj.by}` : "Open, not yet adjudicated"} · narrated in
                      section 6
                    </p>
                  </li>
                );
              })}
            </ul>
          </Panel>

          <Panel title="Provenance of this draft">
            <div className="space-y-2 p-3 text-[12px] leading-relaxed text-muted-foreground">
              <p>
                Drafted from the resolved entity, the consented bank data, the GST and bureau pulls and the confirmed
                spread. No figure in the memo is keyed by hand except where you record an override.
              </p>
              <p className="flex items-center gap-1.5 text-foreground">
                <FileText className="h-3.5 w-3.5 text-primary" /> CCB CAM template v4.2 ·{" "}
                <Link to="/admin/templates" className="text-primary hover:underline">
                  template designer
                </Link>
              </p>
              <button
                type="button"
                onClick={() => {
                  const text = SECTIONS.map((s) => `${s.number}. ${s.title}\n\n${bodyFor(m, s).map(stripCitations).join("\n\n")}`).join("\n\n");
                  navigator.clipboard?.writeText(text);
                  toast.success("Plain-text memo copied", { description: "Citations stripped, wording as it stands now." });
                }}
                className="flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] text-foreground hover:bg-muted"
              >
                <RotateCcw className="h-3.5 w-3.5" /> Copy plain text
              </button>
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

export type { MemoSection };
