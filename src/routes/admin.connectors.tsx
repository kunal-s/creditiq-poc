import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowUpRight, Activity, ShieldCheck, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import {
  CONNECTOR_IMPACT,
  HEALTH_LABEL,
  HEALTH_TONE,
  setConsent,
  setRetention,
  testConnector,
  toggleConnector,
  useAdminState,
} from "@/data/admin";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/connectors")({
  head: () => {
    const title = "Connector and consent settings — CreditIQ";
    const description =
      "Health, credentials, retention and consent for every data source Continental Commercial Bank pulls from — GST, bureau, registry, Account Aggregator, adverse media and core banking — with the downstream impact of switching one off.";
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
  component: ConnectorSettings,
});

function ConnectorSettings() {
  const s = useAdminState();
  const [open, setOpen] = useState<string | null>("media");

  const degraded = s.connectors.filter((c) => c.health !== "healthy");
  const off = s.connectors.filter((c) => !c.enabled);

  return (
    <div>
      <PageHeader
        eyebrow="Admin · Data sources"
        title="Connector and consent settings"
        purpose="Every source CreditIQ pulls from, its live health, who it needs consent from, and how long the evidence is kept. Switching a source off changes what the engine can prove — so the consequence is spelled out before you do it."
        actions={
          <Link
            to="/appraisals/$id/data"
            params={{ id: "CAM-2026-0418" }}
            className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
          >
            Acquisition console <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        }
      />

      <div className="space-y-4 px-6 py-5">
        <div className="grid gap-3 sm:grid-cols-4">
          {[
            { n: s.connectors.filter((c) => c.enabled).length, l: "Sources enabled", t: "text-foreground" },
            { n: degraded.length, l: "Not fully healthy", t: degraded.length ? "text-flag-foreground" : "text-positive" },
            { n: s.connectors.filter((c) => c.consent === "required").length, l: "Require borrower consent", t: "text-foreground" },
            { n: off.length, l: "Switched off", t: off.length ? "text-critical" : "text-muted-foreground" },
          ].map((k) => (
            <div key={k.l} className="rounded border border-border bg-surface px-4 py-3">
              <p className={cn("text-[22px] font-semibold tabular-nums", k.t)}>{k.n}</p>
              <p className="text-[11.5px] text-muted-foreground">{k.l}</p>
            </div>
          ))}
        </div>

        {degraded.length > 0 && (
          <div className="flex items-start gap-2.5 rounded border border-flag/35 bg-flag-soft px-4 py-3">
            <Activity className="mt-0.5 h-4 w-4 shrink-0 text-flag-foreground" />
            <p className="text-[12.5px] text-flag-foreground">
              <span className="font-medium">{degraded[0]!.name} is {HEALTH_LABEL[degraded[0]!.health].toLowerCase()}.</span>{" "}
              {degraded[0]!.note} The gap is recorded in Northwind's Risk Assessment and in the audit ledger.
            </p>
          </div>
        )}

        <div className="grid gap-4 [@media(min-width:1700px)]:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          <Panel title="Sources" subtitle="Provider, health over the last 30 days, consent basis and retention.">
            <ul className="divide-y divide-border">
              {s.connectors.map((c) => {
                const test = s.tests[c.id];
                return (
                  <li key={c.id}>
                    <div className={cn("px-4 py-3", !c.enabled && "opacity-70")}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <button onClick={() => setOpen(open === c.id ? null : c.id)} className="min-w-0 text-left">
                          <p className="flex flex-wrap items-center gap-2 text-[13px] font-medium text-foreground">
                            {c.name}
                            <span className={cn("rounded border px-1.5 py-0.5 text-[10.5px] font-normal", HEALTH_TONE[c.health])}>
                              {HEALTH_LABEL[c.health]}
                            </span>
                            {c.consent === "required" && (
                              <span className="rounded border border-info/25 bg-info-soft px-1.5 py-0.5 text-[10.5px] font-normal text-info">
                                Consent required
                              </span>
                            )}
                            {c.required && (
                              <span className="rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[10.5px] font-normal text-muted-foreground">
                                Cannot be disabled
                              </span>
                            )}
                          </p>
                          <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                            {c.provider} · {c.detail}
                          </p>
                          <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                            {c.latency} · {c.successRate} · last call {c.lastCall}
                          </p>
                        </button>
                        <div className="flex shrink-0 items-center gap-1.5">
                          <button
                            onClick={() => {
                              const r = testConnector(c.id);
                              if (r.ok) toast.success(`${c.name} test passed`, { description: r.result });
                              else toast.warning(`${c.name} test returned a partial`, { description: r.result });
                            }}
                            className="h-8 rounded border border-border bg-surface px-2.5 text-[12px] hover:bg-muted"
                          >
                            Test connection
                          </button>
                          <button
                            onClick={() => {
                              if (c.required) {
                                toast.error(`${c.name} cannot be switched off`, {
                                  description: CONNECTOR_IMPACT[c.id]?.[0] ?? "A core rule depends on this source.",
                                });
                                return;
                              }
                              toggleConnector(c.id);
                              setOpen(c.id);
                              toast(c.enabled ? `${c.name} switched off` : `${c.name} switched on`, {
                                description: c.enabled ? CONNECTOR_IMPACT[c.id]?.[0] : "Available to the next acquisition run.",
                              });
                            }}
                            className={cn(
                              "h-8 rounded border px-2.5 text-[12px]",
                              c.enabled ? "border-positive/30 bg-positive-soft text-positive" : "border-border bg-surface text-muted-foreground hover:bg-muted",
                            )}
                          >
                            {c.enabled ? "Enabled" : "Disabled"}
                          </button>
                        </div>
                      </div>
                      {test && (
                        <p className={cn("mt-2 rounded border px-2.5 py-1.5 text-[11.5px]", test.ok ? "border-positive/25 bg-positive-soft text-positive" : "border-flag/30 bg-flag-soft text-flag-foreground")}>
                          Tested {test.at} — {test.result}
                        </p>
                      )}
                    </div>
                    {open === c.id && (
                      <div className="grid gap-3 border-t border-border bg-surface-muted/40 px-4 py-3 md:grid-cols-2">
                        <div>
                          <p className="field-label">If this source is unavailable</p>
                          <ul className="mt-1 space-y-1">
                            {(CONNECTOR_IMPACT[c.id] ?? []).map((x) => (
                              <li key={x} className="flex gap-1.5 text-[12px] text-muted-foreground">
                                <span className="text-muted-foreground">—</span>
                                <span>{x}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div className="space-y-2">
                          <div>
                            <p className="field-label">Operating note</p>
                            <p className="mt-0.5 text-[12px] text-muted-foreground">{c.note}</p>
                          </div>
                          <label className="block text-[12px]">
                            <span className="field-label">Evidence retention (days)</span>
                            <input
                              type="number"
                              step={365}
                              value={c.retentionDays}
                              onChange={(e) => setRetention(c.id, Number(e.target.value) || 0)}
                              className="mt-1 h-8 w-32 rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground"
                            />
                            <span className="ml-2 text-[11.5px] text-muted-foreground">
                              about {(c.retentionDays / 365).toFixed(1)} years
                            </span>
                          </label>
                        </div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </Panel>

          <div className="space-y-4">
            <Panel title="Consent and retention" subtitle="What the borrower sees and agrees to, and how long CCB keeps what it pulls.">
              <div className="space-y-3 px-4 py-3">
                <label className="block text-[12px]">
                  <span className="field-label">Purpose shown to the borrower</span>
                  <textarea
                    value={s.consent.purposeText}
                    onChange={(e) => setConsent({ purposeText: e.target.value })}
                    rows={3}
                    className="mt-1 w-full rounded border border-border bg-surface px-2 py-1.5 text-[12.5px] leading-relaxed text-foreground"
                  />
                  <span className="mt-1 block text-[11.5px] text-muted-foreground">
                    Rendered verbatim on the consent journey before signature.
                  </span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-[12px]">
                    <span className="field-label">Consent window (days)</span>
                    <input
                      type="number"
                      value={s.consent.windowDays}
                      onChange={(e) => setConsent({ windowDays: Number(e.target.value) || 0 })}
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground"
                    />
                  </label>
                  <label className="text-[12px]">
                    <span className="field-label">Reminder before expiry (days)</span>
                    <input
                      type="number"
                      value={s.consent.reminderDays}
                      onChange={(e) => setConsent({ reminderDays: Number(e.target.value) || 0 })}
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground"
                    />
                  </label>
                  <label className="text-[12px]">
                    <span className="field-label">Record retention (years)</span>
                    <input
                      type="number"
                      value={s.consent.retentionYears}
                      onChange={(e) => setConsent({ retentionYears: Number(e.target.value) || 0 })}
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground"
                    />
                  </label>
                  <div className="text-[12px]">
                    <span className="field-label">Controls</span>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      <button
                        onClick={() => setConsent({ autoRevoke: !s.consent.autoRevoke })}
                        className={cn(
                          "rounded border px-2 py-1 text-[11.5px]",
                          s.consent.autoRevoke ? "border-positive/30 bg-positive-soft text-positive" : "border-border bg-surface text-muted-foreground",
                        )}
                      >
                        Auto-revoke at expiry
                      </button>
                      <button
                        onClick={() => setConsent({ piiMasking: !s.consent.piiMasking })}
                        className={cn(
                          "rounded border px-2 py-1 text-[11.5px]",
                          s.consent.piiMasking ? "border-positive/30 bg-positive-soft text-positive" : "border-border bg-surface text-muted-foreground",
                        )}
                      >
                        Mask PAN and GSTIN on screen
                      </button>
                    </div>
                  </div>
                </div>
                <p className="flex items-start gap-1.5 rounded border border-border bg-surface-muted px-2.5 py-2 text-[11.5px] text-muted-foreground">
                  <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" />
                  Northwind's bank-statement consent, taken on 14 July 2026, expires on{" "}
                  {13 + s.consent.windowDays > 31 ? "13 August 2026" : `${13 + s.consent.windowDays} July 2026`} under this window.
                  Changing it re-dates every live consent at the next refresh.
                </p>
                <Link
                  to="/appraisals/$id/consent"
                  params={{ id: "CAM-2026-0418" }}
                  className="inline-flex items-center gap-1 text-[12px] text-primary hover:underline"
                >
                  Preview the borrower's consent journey <ArrowUpRight className="h-3 w-3" />
                </Link>
              </div>
            </Panel>

            <div className="rounded border border-border bg-surface p-4">
              <p className="flex items-center gap-1.5 text-[12.5px] font-semibold">
                <Sparkles className="h-3.5 w-3.5 text-primary" /> Ask the copilot
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                "What breaks if I switch off the bureau connector?" — the copilot names the rules, memo sections and rating inputs that
                lose their evidence, appraisal by appraisal.
              </p>
            </div>

            {s.log.length > 0 && (
              <Panel title="Recent configuration changes" subtitle="Everything set here is written to the audit ledger.">
                <ul className="divide-y divide-border">
                  {s.log.slice(0, 6).map((l, i) => (
                    <li key={i} className="px-4 py-2 text-[12px]">
                      <p className="text-foreground">{l.text}</p>
                      <p className="text-[11.5px] text-muted-foreground">
                        {l.by} · {l.at}
                      </p>
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
