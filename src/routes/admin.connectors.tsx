import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Activity, ShieldCheck, Sparkles } from "lucide-react";
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
import { useSession } from "@/domain/session";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/connectors")({
  head: () => ({
    meta: [
      { title: `${t("page.adminConnectors.title")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content: `Health, credentials, retention and consent for every data source ${t("tenant.bank.name")} pulls from, with the downstream impact of switching one off.`,
      },
    ],
  }),
  component: ConnectorSettings,
});

function ConnectorSettings() {
  const session = useSession();
  const actor = session?.user.name ?? "Unknown";
  const s = useAdminState();
  const [open, setOpen] = useState<string | null>(null);

  const notHealthy = s.connectors.filter((c) => c.health !== "healthy");
  const off = s.connectors.filter((c) => !c.enabled);

  return (
    <div>
      <PageHeader
        eyebrow={t("page.adminConnectors.eyebrow")}
        title={t("page.adminConnectors.title")}
        purpose={`Every source ${t("tenant.product.name")} pulls from, its live health, who it needs consent from, and how long the evidence is kept. Switching a source off changes what the engine can prove — so the consequence is spelled out before you do it.`}
      />

      <div className="space-y-4 px-6 py-5">
        <div className="grid gap-3 sm:grid-cols-4">
          {[
            {
              n: s.connectors.filter((c) => c.enabled).length,
              l: "Sources enabled",
              t: "text-foreground",
            },
            {
              n: notHealthy.length,
              l: "Not fully healthy",
              t: notHealthy.length ? "text-flag-foreground" : "text-positive",
            },
            {
              n: s.connectors.filter((c) => c.consent === "required").length,
              l: "Require borrower consent",
              t: "text-foreground",
            },
            {
              n: off.length,
              l: "Switched off",
              t: off.length ? "text-critical" : "text-muted-foreground",
            },
          ].map((k) => (
            <div key={k.l} className="rounded border border-border bg-surface px-4 py-3">
              <p className={cn("text-[22px] font-semibold tabular-nums", k.t)}>{k.n}</p>
              <p className="text-[11.5px] text-muted-foreground">{k.l}</p>
            </div>
          ))}
        </div>

        {off.length > 0 && (
          <div className="flex items-start gap-2.5 rounded border border-flag/35 bg-flag-soft px-4 py-3">
            <Activity className="mt-0.5 h-4 w-4 shrink-0 text-flag-foreground" />
            <p className="text-[12.5px] text-flag-foreground">
              <span className="font-medium">
                {off.length} source{off.length === 1 ? "" : "s"} not connected.
              </span>{" "}
              External connectors are switched off for this environment; Manual upload is the active
              path until they are enabled.
            </p>
          </div>
        )}

        <div className="grid gap-4 [@media(min-width:1700px)]:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          <Panel
            title="Sources"
            subtitle="Provider, health over the last 30 days, consent basis and retention."
          >
            <ul className="divide-y divide-border">
              {s.connectors.map((c) => {
                const test = s.tests[c.id];
                return (
                  <li key={c.id}>
                    <div className={cn("px-4 py-3", !c.enabled && "opacity-70")}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <button
                          onClick={() => setOpen(open === c.id ? null : c.id)}
                          className="min-w-0 text-left"
                        >
                          <p className="flex flex-wrap items-center gap-2 text-[13px] font-medium text-foreground">
                            {c.name}
                            <span
                              className={cn(
                                "rounded border px-1.5 py-0.5 text-[10.5px] font-normal",
                                HEALTH_TONE[c.health],
                              )}
                            >
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
                              if (r.ok)
                                toast.success(`${c.name} test passed`, { description: r.result });
                              else
                                toast.warning(`${c.name} test returned a partial`, {
                                  description: r.result,
                                });
                            }}
                            className="h-8 rounded border border-border bg-surface px-2.5 text-[12px] hover:bg-muted"
                          >
                            Test connection
                          </button>
                          <button
                            onClick={() => {
                              if (c.required) {
                                toast.error(`${c.name} cannot be switched off`, {
                                  description:
                                    CONNECTOR_IMPACT[c.id]?.[0] ??
                                    "A core rule depends on this source.",
                                });
                                return;
                              }
                              toggleConnector(c.id, actor);
                              setOpen(c.id);
                              toast(
                                c.enabled ? `${c.name} switched off` : `${c.name} switched on`,
                                {
                                  description: c.enabled
                                    ? CONNECTOR_IMPACT[c.id]?.[0]
                                    : "Available to the next acquisition run.",
                                },
                              );
                            }}
                            className={cn(
                              "h-8 rounded border px-2.5 text-[12px]",
                              c.enabled
                                ? "border-positive/30 bg-positive-soft text-positive"
                                : "border-border bg-surface text-muted-foreground hover:bg-muted",
                            )}
                          >
                            {c.enabled ? "Enabled" : "Disabled"}
                          </button>
                        </div>
                      </div>
                      {test && (
                        <p
                          className={cn(
                            "mt-2 rounded border px-2.5 py-1.5 text-[11.5px]",
                            test.ok
                              ? "border-positive/25 bg-positive-soft text-positive"
                              : "border-flag/30 bg-flag-soft text-flag-foreground",
                          )}
                        >
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
                              <li
                                key={x}
                                className="flex gap-1.5 text-[12px] text-muted-foreground"
                              >
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
            <Panel
              title="Consent and retention"
              subtitle={`What the borrower sees and agrees to, and how long ${t("tenant.bank.name")} keeps what it pulls.`}
            >
              <div className="space-y-3 px-4 py-3">
                <label className="block text-[12px]">
                  <span className="field-label">Purpose shown to the borrower</span>
                  <textarea
                    value={s.consent.purposeText}
                    onChange={(e) => setConsent({ purposeText: e.target.value }, actor)}
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
                      onChange={(e) =>
                        setConsent({ windowDays: Number(e.target.value) || 0 }, actor)
                      }
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground"
                    />
                  </label>
                  <label className="text-[12px]">
                    <span className="field-label">Reminder before expiry (days)</span>
                    <input
                      type="number"
                      value={s.consent.reminderDays}
                      onChange={(e) =>
                        setConsent({ reminderDays: Number(e.target.value) || 0 }, actor)
                      }
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground"
                    />
                  </label>
                  <label className="text-[12px]">
                    <span className="field-label">Record retention (years)</span>
                    <input
                      type="number"
                      value={s.consent.retentionYears}
                      onChange={(e) =>
                        setConsent({ retentionYears: Number(e.target.value) || 0 }, actor)
                      }
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground"
                    />
                  </label>
                  <div className="text-[12px]">
                    <span className="field-label">Controls</span>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      <button
                        onClick={() => setConsent({ autoRevoke: !s.consent.autoRevoke }, actor)}
                        className={cn(
                          "rounded border px-2 py-1 text-[11.5px]",
                          s.consent.autoRevoke
                            ? "border-positive/30 bg-positive-soft text-positive"
                            : "border-border bg-surface text-muted-foreground",
                        )}
                      >
                        Auto-revoke at expiry
                      </button>
                      <button
                        onClick={() => setConsent({ piiMasking: !s.consent.piiMasking }, actor)}
                        className={cn(
                          "rounded border px-2 py-1 text-[11.5px]",
                          s.consent.piiMasking
                            ? "border-positive/30 bg-positive-soft text-positive"
                            : "border-border bg-surface text-muted-foreground",
                        )}
                      >
                        Mask PAN and GSTIN on screen
                      </button>
                    </div>
                  </div>
                </div>
                <p className="flex items-start gap-1.5 rounded border border-border bg-surface-muted px-2.5 py-2 text-[11.5px] text-muted-foreground">
                  <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" />
                  No live consent is outstanding yet. Changing this window applies to the next
                  consent request.
                </p>
              </div>
            </Panel>

            <div className="rounded border border-border bg-surface p-4">
              <p className="flex items-center gap-1.5 text-[12.5px] font-semibold">
                <Sparkles className="h-3.5 w-3.5 text-primary" /> Ask the copilot
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                "What breaks if I switch off the bureau connector?" — the copilot names the rules,
                memo sections and rating inputs that lose their evidence, appraisal by appraisal.
              </p>
            </div>

            {s.log.length > 0 && (
              <Panel
                title="Recent configuration changes"
                subtitle="Everything set here is written to the audit ledger."
              >
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
