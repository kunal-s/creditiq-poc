import { createFileRoute, Link, notFound, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CircleAlert,
  Copy,
  Plus,
  Search,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { ConfidenceChip, Panel, SourceChip } from "@/components/identity/chips";
import {
  DIRECTORS,
  ENTITIES,
  NEAR_DUPLICATE,
  RESOLVED_FIELDS,
  SUGGESTED_LINKS,
  getEntity,
} from "@/data/identity";
import { getAppraisal } from "@/data/seed";

export const Route = createFileRoute("/appraisals/$id/identity")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Entity resolution — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description =
      "Confirm the legal entity, its group perimeter and its directors before any data is pulled: CIN, PAN, GSTIN, LEI and registry-sourced confidence on every field.";
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
  component: IdentityStep,
});

function IdentityStep() {
  const { id } = Route.useParams();
  const appraisal = getAppraisal(id);
  if (!appraisal) throw notFound();
  const entity = getEntity("northwind-manufacturing")!;

  const navigate = useNavigate();
  const [linkConfirmed, setLinkConfirmed] = useState<Record<string, "pending" | "confirmed" | "removed">>({
    "northwind-logistics": "pending",
  });
  const [showDuplicate, setShowDuplicate] = useState(false);
  const [duplicateResolved, setDuplicateResolved] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const directors = entity.directorSlugs.map((s) => DIRECTORS.find((d) => d.slug === s)!);
  const pendingLinks = Object.values(linkConfirmed).filter((v) => v === "pending").length;

  function confirmAll() {
    setConfirmed(true);
    toast.success("Borrower and group confirmed", {
      description:
        "Northwind Manufacturing Ltd locked as the appraisal entity with Northwind Logistics Ltd inside the group perimeter.",
    });
    navigate({ to: "/appraisals/$id/data", params: { id } });
  }

  return (
    <div className="pb-10">
      <PageHeader
        eyebrow={`Appraisal ${appraisal.id} · Identity`}
        title="Entity resolution and confirmation"
        purpose="Confirm exactly which legal entity this is, its group perimeter and its directors, before any data is pulled."
        actions={
          <>
            <button
              type="button"
              onClick={() => setShowDuplicate(true)}
              className="h-8 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              Correct match
            </button>
            <button
              type="button"
              onClick={confirmAll}
              className="flex h-8 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              {confirmed ? <Check className="h-3.5 w-3.5" /> : null}
              Confirm borrower and group <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </>
        }
      />

      <div className="grid gap-4 px-6 py-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-4">
          {/* Resolution header */}
          <Panel
            title="Confirmed match"
            subtitle="Resolved from the name, PAN and GSTIN supplied at intake. Sources refreshed 30 July 2026."
            action={
              <span className="inline-flex items-center gap-1.5 rounded border border-positive/30 bg-positive-soft px-2 py-0.5 text-[11px] font-medium text-positive">
                <Check className="h-3 w-3" /> Single high-confidence match
              </span>
            }
          >
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
              <div>
                <h3 className="text-[16px] font-semibold tracking-tight">{entity.name}</h3>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  {entity.sector} · {entity.status}
                </p>
              </div>
              <div className="text-[11.5px] text-muted-foreground">
                <span className="field-label block">Existing exposure</span>
                <span className="text-[12.5px] text-foreground">{entity.exposure}</span>
              </div>
            </div>
            <dl className="divide-y divide-border">
              {RESOLVED_FIELDS.map((f) => (
                <div key={f.label} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5">
                  <dt className="w-44 shrink-0 text-[12px] text-muted-foreground">{f.label}</dt>
                  <dd className="min-w-0 flex-1 text-[13px] text-foreground tabular">{f.value}</dd>
                  <ConfidenceChip level={f.confidence} />
                  <SourceChip source={f.source} />
                  {f.note && (
                    <p className="w-full pl-44 text-[11.5px] text-muted-foreground">{f.note}</p>
                  )}
                </div>
              ))}
            </dl>
            <div className="flex flex-wrap items-center gap-2 border-t border-border bg-surface-muted px-4 py-2.5 text-[11.5px] text-muted-foreground">
              <CircleAlert className="h-3.5 w-3.5 text-flag" />
              One near-duplicate registry record shares this name stem.
              <button
                type="button"
                onClick={() => setShowDuplicate(true)}
                className="font-medium text-primary hover:underline"
              >
                Review the candidate
              </button>
              {duplicateResolved && (
                <span className="rounded border border-positive/30 bg-positive-soft px-1.5 py-0.5 text-[10.5px] font-medium text-positive">
                  Disambiguated by you · 31 July 2026
                </span>
              )}
            </div>
          </Panel>

          {/* Near duplicate */}
          {showDuplicate && (
            <Panel
              title="Disambiguation required"
              subtitle="CreditIQ will not guess between these. Pick the entity this appraisal is for."
              className="border-flag/40"
              action={
                <button
                  type="button"
                  onClick={() => setShowDuplicate(false)}
                  aria-label="Dismiss disambiguation"
                  className="grid h-6 w-6 place-items-center rounded text-muted-foreground hover:bg-muted"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              }
            >
              <div className="grid gap-px bg-border md:grid-cols-2">
                <div className="bg-surface p-4">
                  <p className="text-[13px] font-semibold">{entity.name}</p>
                  <dl className="mt-2 space-y-1 text-[12px] text-muted-foreground tabular">
                    <div>CIN {entity.cin}</div>
                    <div>PAN {entity.panMasked} · GSTIN {entity.gstin}</div>
                    <div>Incorporated {entity.incorporated}</div>
                    <div>{entity.registeredOffice}</div>
                  </dl>
                  <button
                    type="button"
                    onClick={() => {
                      setDuplicateResolved(true);
                      setShowDuplicate(false);
                      toast.success("Match retained", {
                        description: "Northwind Manufacturing Ltd (CIN U27310MH2009PLC198435) kept as the appraisal entity.",
                      });
                    }}
                    className="mt-3 h-8 w-full rounded bg-primary text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    This is the borrower
                  </button>
                </div>
                <div className="bg-surface p-4">
                  <p className="text-[13px] font-semibold">{NEAR_DUPLICATE.name}</p>
                  <dl className="mt-2 space-y-1 text-[12px] text-muted-foreground tabular">
                    <div>CIN {NEAR_DUPLICATE.cin}</div>
                    <div>PAN {NEAR_DUPLICATE.pan} · GSTIN {NEAR_DUPLICATE.gstin}</div>
                    <div>Incorporated {NEAR_DUPLICATE.incorporated}</div>
                    <div>{NEAR_DUPLICATE.registeredOffice}</div>
                  </dl>
                  <button
                    type="button"
                    onClick={() =>
                      toast("Match switch requires a reason", {
                        description:
                          "Switching to CIN U28999MH2014PTC258771 contradicts the PAN supplied by Marcus Chen; record a reason in the audit trail before proceeding.",
                      })
                    }
                    className="mt-3 h-8 w-full rounded border border-border bg-surface text-[12.5px] font-medium text-foreground hover:bg-muted"
                  >
                    Switch to this entity
                  </button>
                </div>
              </div>
              <ul className="space-y-1 border-t border-border bg-surface-muted px-4 py-3 text-[12px] text-muted-foreground">
                {NEAR_DUPLICATE.distinguishers.map((d) => (
                  <li key={d} className="flex gap-2">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-muted-foreground/60" />
                    {d}
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {/* Directors */}
          <Panel
            title="Directors on record"
            subtitle="MCA DIN master, refreshed 29 July 2026. None disqualified."
            action={
              <span className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                <Users className="h-3.5 w-3.5" /> {directors.length} directors
              </span>
            }
          >
            <ul className="divide-y divide-border">
              {directors.map((d) => (
                <li key={d.slug} className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)] items-center gap-x-4 gap-y-1 px-4 py-2.5">
                  <Link
                    to="/people/$slug"
                    params={{ slug: d.slug }}
                    className="truncate text-[13px] font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {d.name}
                  </Link>
                  <span className="text-[12px] text-muted-foreground">{d.role}</span>
                  <span className="text-[12px] text-muted-foreground tabular">DIN {d.din}</span>
                  <span className="col-start-1 text-[11.5px] text-muted-foreground">Appointed {d.appointed}</span>
                  <span className="text-right text-[12px] text-foreground tabular">{d.shareholding}</span>
                </li>
              ))}
            </ul>
          </Panel>

          {/* Group and related parties */}
          <Panel
            title="Group and related parties"
            subtitle="Suggested from shared directorships and registered-address overlap. Nothing enters the perimeter until you confirm."
            action={
              <button
                type="button"
                onClick={() =>
                  toast("Add a related entity", {
                    description: "Search by name, PAN, GSTIN or CIN to attach another entity to this group perimeter.",
                  })
                }
                className="flex h-7 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] font-medium text-foreground hover:bg-muted"
              >
                <Plus className="h-3.5 w-3.5" /> Add related entity
              </button>
            }
          >
            <ul className="divide-y divide-border">
              {SUGGESTED_LINKS.map((l) => {
                const state = linkConfirmed[l.entitySlug];
                return (
                  <li key={l.entitySlug} className="px-4 py-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to="/entities/$slug"
                            params={{ slug: l.entitySlug }}
                            className="text-[13px] font-medium text-foreground hover:text-primary hover:underline"
                          >
                            {l.name}
                          </Link>
                          <ConfidenceChip level={l.confidence} />
                          <SourceChip source={l.source} />
                          {state === "confirmed" && (
                            <span className="rounded border border-positive/30 bg-positive-soft px-1.5 py-0.5 text-[10.5px] font-medium text-positive">
                              In group perimeter
                            </span>
                          )}
                          {state === "removed" && (
                            <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10.5px] font-medium text-muted-foreground">
                              Excluded by you
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-[11.5px] text-muted-foreground tabular">
                          PAN {l.pan} · GSTIN {l.gstin}
                        </p>
                        <p className="mt-1 text-[12.5px] text-muted-foreground">{l.basis}</p>
                        {l.leiNote && (
                          <p className="mt-1.5 inline-flex items-center gap-1.5 rounded border border-flag/35 bg-flag-soft px-2 py-1 text-[11.5px] text-flag-foreground">
                            <AlertTriangle className="h-3.5 w-3.5" /> {l.leiNote} Carried forward as an open
                            item to cross-verification.
                          </p>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setLinkConfirmed((s) => ({ ...s, [l.entitySlug]: "confirmed" }));
                            toast.success(`${l.name} added to the group perimeter`);
                          }}
                          className="h-7 rounded bg-primary px-2.5 text-[12px] font-medium text-primary-foreground hover:bg-primary/90"
                        >
                          Confirm link
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setLinkConfirmed((s) => ({ ...s, [l.entitySlug]: "removed" }));
                            toast("Link removed", { description: `${l.name} excluded from the group perimeter with a reason recorded.` });
                          }}
                          className="h-7 rounded border border-border bg-surface px-2.5 text-[12px] font-medium text-foreground hover:bg-muted"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
            <p className="border-t border-border bg-surface-muted px-4 py-2.5 text-[11.5px] text-muted-foreground">
              {pendingLinks > 0
                ? `${pendingLinks} suggested link awaiting your decision. Group exposure is not aggregated until it is settled.`
                : "Group perimeter settled. Aggregate exposure will be computed at the spread step."}
            </p>
          </Panel>

          {/* Exposure context */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-info/25 bg-info-soft px-4 py-3 text-[12.5px]">
            <span className="field-label">Exposure context</span>
            <span className="text-foreground">
              Existing Cash Credit of INR 12.20 cr already on the books for {entity.name}, sanctioned 30
              August 2025, outstanding INR 10.86 cr.
            </span>
            <Link
              to="/appraisals/$id/spread"
              params={{ id }}
              className="font-medium text-primary hover:underline"
            >
              See how it feeds the proposal
            </Link>
          </div>
        </div>

        {/* Side column */}
        <div className="space-y-4">
          <Panel title="Registry snapshot">
            <dl className="divide-y divide-border text-[12.5px]">
              {[
                ["Status", entity.status],
                ["Authorised capital", entity.authorisedCapital],
                ["Paid-up capital", entity.paidUpCapital],
                ["Last statutory filing", entity.lastFilingAgm],
                ["Registered office", entity.registeredOffice],
              ].map(([k, v]) => (
                <div key={k} className="px-4 py-2.5">
                  <span className="field-label block">{k}</span>
                  <span className="mt-0.5 block text-foreground">{v}</span>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel title="Group perimeter">
            <ul className="divide-y divide-border">
              {ENTITIES.map((e) => (
                <li key={e.slug} className="px-4 py-2.5">
                  <Link
                    to="/entities/$slug"
                    params={{ slug: e.slug }}
                    className="text-[12.5px] font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {e.name}
                  </Link>
                  <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
                    {e.relationship} · {e.lei ? `LEI ${e.lei}` : "LEI not obtained"}
                  </span>
                </li>
              ))}
            </ul>
          </Panel>

          <div className="rounded border border-border bg-surface p-4">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> Inline AI action
            </p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
              Sweep the MCA DIN master for any other active company sharing Rajesh Malhotra, Anita
              Malhotra or Sameer Deshpande, then report anything outside the current perimeter.
            </p>
            <button
              type="button"
              onClick={() =>
                toast("Director sweep complete", {
                  description:
                    "Malhotra Family Holdings Pvt Ltd (investment holding, no bank facilities) and Deccan Toolings Ltd (independent directorship only) sit outside the perimeter.",
                })
              }
              className="mt-3 flex h-8 w-full items-center justify-center gap-1.5 rounded bg-primary text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Search className="h-3.5 w-3.5" /> Run director sweep
            </button>
            <button
              type="button"
              onClick={() =>
                toast("Identity block copied", {
                  description: "Legal name, CIN, PAN, GSTIN, LEI and registered office copied for the memo.",
                })
              }
              className="mt-2 flex h-8 w-full items-center justify-center gap-1.5 rounded border border-border bg-surface text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <Copy className="h-3.5 w-3.5" /> Copy identity block to memo
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
