import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { CitationInspector } from "@/components/memo/cited";
import { CURRENT_USER, getAppraisal } from "@/data/seed";
import {
  DEFAULT_RECOMMENDATION,
  FIRST_CUT,
  GRADES,
  RATING_FACTORS,
  confirmRating,
  confirmRecommendation,
  setRating,
  setRecommendation,
  useMemoState,
  type Grade,
} from "@/data/memo";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/appraisals/$id/rating")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Rating and recommendation — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description =
      "Settle the internal risk rating on the CCB-1 to CCB-8 grid and the recommendation to the credit committee, with every change from the first cut recorded against the analyst.";
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
  component: RatingPanel,
});

const TONE: Record<string, string> = {
  positive: "border-positive/30 bg-positive-soft text-positive",
  neutral: "border-border bg-surface-muted text-muted-foreground",
  flag: "border-flag/35 bg-flag-soft text-flag-foreground",
  critical: "border-critical/30 bg-critical-soft text-critical",
};

function RatingPanel() {
  const { id } = Route.useParams();
  const a = getAppraisal(id);
  if (!a) throw notFound();

  const m = useMemoState();
  const [pending, setPending] = useState<Grade>(m.rating);
  const [reason, setReason] = useState("");
  const [draft, setDraft] = useState(m.recommendation);
  const [cite, setCite] = useState<string | null>(null);

  const changed = pending !== m.rating;

  const apply = () => {
    if (changed && reason.trim().length < 8) {
      toast.error("Changing the rating needs a recorded reason of at least eight characters.");
      return;
    }
    if (changed) {
      setRating(pending, reason.trim(), `${CURRENT_USER.name} · ${CURRENT_USER.role}`);
      toast.success(`Rating changed to ${pending}`, {
        description: `First cut ${FIRST_CUT} retained alongside your reason and timestamp.`,
      });
      setReason("");
    }
    confirmRating(CURRENT_USER.name);
    setRecommendation(draft);
    confirmRecommendation();
    toast.success("Rating and recommendation confirmed", {
      description: `Attributed to ${CURRENT_USER.name}, ${CURRENT_USER.role}. Sections 7 and 8 of the memo now carry it.`,
    });
  };

  return (
    <div>
      <PageHeader
        eyebrow={`Appraisal ${a.id} · Rating and recommendation`}
        title="Recommendation and risk rating"
        purpose="The model produced a first cut. The rating that leaves this screen is the analyst's, and any move from the first cut is recorded with a reason."
        actions={
          <>
            <Link
              to="/appraisals/$id/draft"
              params={{ id: a.id }}
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Draft
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

      <div className="grid gap-4 px-6 py-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <Panel
            title="Internal risk rating"
            subtitle={`CCB rating model v3.1 · first cut ${FIRST_CUT} (watch), financial score CCB-3 with a one-notch evidence-quality overlay`}
          >
            <div className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-4">
              {GRADES.map((g) => {
                const selected = pending === g.grade;
                const first = g.grade === FIRST_CUT;
                return (
                  <button
                    key={g.grade}
                    type="button"
                    onClick={() => setPending(g.grade)}
                    className={cn(
                      "rounded border px-2.5 py-2 text-left transition-colors",
                      selected ? "border-primary bg-primary/10" : "border-border bg-surface hover:bg-muted",
                    )}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-[13px] font-semibold text-foreground">{g.grade}</span>
                      <span className={cn("rounded border px-1 py-px text-[9.5px] font-medium", TONE[g.tone])}>
                        {g.band}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11.5px] text-muted-foreground">{g.label}</p>
                    {first && (
                      <p className="mt-1 text-[10.5px] font-medium text-primary">Model first cut</p>
                    )}
                    {m.rating === g.grade && m.rating !== FIRST_CUT && (
                      <p className="mt-1 text-[10.5px] font-medium text-positive">Current</p>
                    )}
                  </button>
                );
              })}
            </div>

            {changed && (
              <div className="border-t border-border bg-flag-soft/40 px-3 py-2.5">
                <label className="text-[11.5px] text-muted-foreground">
                  Moving from {m.rating} to {pending} — record why. The first cut and your reason are both retained.
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. Turnover reconciliation received and evidenced; overlay no longer applies"
                    className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                  />
                </label>
              </div>
            )}
          </Panel>

          <Panel title="Factors behind the first cut" subtitle="Each factor resolves to the evidence it was scored on.">
            <ul className="divide-y divide-border">
              {RATING_FACTORS.map((f) => (
                <li key={f.title} className="flex items-start gap-3 px-3 py-2.5">
                  {f.direction === "for" ? (
                    <TrendingUp className="mt-[2px] h-4 w-4 shrink-0 text-positive" />
                  ) : (
                    <TrendingDown className="mt-[2px] h-4 w-4 shrink-0 text-critical" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] font-medium text-foreground">{f.title}</p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">{f.detail}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-[11.5px] text-muted-foreground">{f.weight}</p>
                    {f.cite && (
                      <button
                        type="button"
                        onClick={() => setCite(f.cite!)}
                        className="text-[11px] text-info hover:underline"
                      >
                        evidence
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel
            title="Recommendation to the credit committee"
            subtitle="This text becomes section 8 of the memo, signed in the analyst's name."
          >
            <div className="p-3">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={7}
                className="w-full rounded border border-border bg-surface-muted p-3 text-[13px] leading-relaxed text-foreground"
              />
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={apply}
                  className="flex h-9 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:opacity-90"
                >
                  <Check className="h-3.5 w-3.5" /> Confirm rating and recommendation
                </button>
                <button
                  type="button"
                  onClick={() => setDraft(DEFAULT_RECOMMENDATION)}
                  className="h-9 rounded border border-border bg-surface px-3 text-[12.5px] text-foreground hover:bg-muted"
                >
                  Reset to the drafted wording
                </button>
                <p className="text-[11.5px] text-muted-foreground">
                  The model informs; the call is yours. Confirmation is attributed to {CURRENT_USER.name},{" "}
                  {CURRENT_USER.role}.
                </p>
              </div>

              {m.ratingConfirmed && (
                <div className="mt-3 flex items-start gap-2 rounded border border-positive/30 bg-positive-soft px-3 py-2">
                  <Check className="mt-[2px] h-4 w-4 shrink-0 text-positive" />
                  <p className="text-[12.5px] leading-relaxed text-foreground">
                    Rating {m.rating} and the recommendation confirmed by {CURRENT_USER.name} on 31 July 2026. Sections 7
                    and 8 of the memo carry it, and the pre-submission checklist is satisfied on this item.{" "}
                    <Link
                      to="/appraisals/$id/submission"
                      params={{ id: a.id }}
                      className="font-medium text-primary hover:underline"
                    >
                      Go to submission →
                    </Link>
                  </p>
                </div>
              )}

              {m.overrides.filter((o) => o.field === "Internal risk rating").length > 0 && (
                <div className="mt-3 rounded border border-flag/30 bg-flag-soft/40 p-3">
                  <p className="field-label">Rating changes recorded</p>
                  <ul className="mt-1.5 space-y-1.5">
                    {m.overrides
                      .filter((o) => o.field === "Internal risk rating")
                      .map((o) => (
                        <li key={o.id} className="text-[12.5px] text-foreground">
                          {o.original} → <span className="font-medium">{o.override}</span>
                          <span className="block text-[11.5px] text-muted-foreground">
                            {o.reason} · {o.by} · {o.at}
                          </span>
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </div>
          </Panel>
        </div>

        <aside className="space-y-3">
          <Panel title="Evidence">
            <div className="p-3">
              {cite ? (
                <CitationInspector cite={cite} appraisalId={a.id} onClose={() => setCite(null)} />
              ) : (
                <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                  Every factor on the left is scored from evidence already in this appraisal. Click "evidence" on any
                  factor to see the source and open it.
                </p>
              )}
            </div>
          </Panel>

          <Panel title="What moves the rating">
            <div className="space-y-2 p-3 text-[12px] leading-relaxed text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">To CCB-3:</span> the borrower reconciles FY2025 turnover to
                GST and bank credits, and the Crestline obligation is disclosed and registered. The overlay lifts and the
                financial score stands on its own.
              </p>
              <p>
                <span className="font-medium text-foreground">To CCB-5:</span> the reconciliation fails, or restated
                turnover of INR 121.44 cr is taken as the true base — margin and coverage fall, DSCR restates to 1.44x,
                and the disclosure failure becomes a management-quality mark.
              </p>
              <p className="flex items-center gap-1.5 pt-1 text-foreground">
                <Sparkles className="h-3.5 w-3.5 text-primary" /> Ask the copilot for the full derivation.
              </p>
            </div>
          </Panel>

          <Panel title="Facility on the table">
            <dl className="divide-y divide-border text-[12.5px]">
              {[
                ["Requested", a.proposal],
                ["Facilities", a.facilities],
                ["Recommended limit", "CC INR 15.80 cr + LC/BG INR 6.75 cr"],
                ["Rating now", `${m.rating}${m.ratingConfirmed ? " · confirmed" : " · first cut, unconfirmed"}`],
              ].map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-3 px-3 py-2">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd className="text-right font-medium text-foreground">{v}</dd>
                </div>
              ))}
            </dl>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
