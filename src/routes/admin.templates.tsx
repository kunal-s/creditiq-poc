import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowDown, ArrowUp, Sparkles, Upload } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { EmptyState } from "@/components/shell/EmptyState";
import {
  TONE_PRESETS,
  moveSection,
  publishTemplate,
  setTemplateSettings,
  updateSection,
  useAdminState,
} from "@/data/admin";
import { useSession } from "@/domain/session";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/templates")({
  head: () => ({
    meta: [
      { title: `${t("page.adminTemplates.title")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content: `Define ${t("tenant.bank.name")}'s CAM structure, section order, house tone and citation style.`,
      },
    ],
  }),
  component: TemplateDesigner,
});

const CITATION_LABEL = {
  "every-figure": "Cite every figure",
  "material-only": "Cite material claims",
  none: "No citations",
} as const;

function TemplateDesigner() {
  const session = useSession();
  const actor = session?.user.name ?? "Unknown";
  const s = useAdminState();
  const [version, setVersion] = useState("v1.1");
  const [openSection, setOpenSection] = useState<string | null>(null);

  const tone = TONE_PRESETS.find((t) => t.id === s.templateSettings.tone)!;
  const enabled = s.template.filter((x) => x.enabled);
  const words = enabled.reduce((a, x) => a + x.words, 0);

  return (
    <div>
      <PageHeader
        eyebrow={t("page.adminTemplates.eyebrow")}
        title={t("page.adminTemplates.title")}
        purpose={`The bank's own memo: which sections appear, in what order, how long each runs, and the house tone the drafting engine writes in. Published templates shape every memo ${t("tenant.product.name")} generates.`}
        actions={
          <>
            {s.templatePublished && (
              <span className="hidden items-center gap-1.5 rounded border border-border bg-surface-muted px-2 py-1.5 text-[11.5px] text-muted-foreground lg:inline-flex">
                Published: {s.templatePublished.version} by {s.templatePublished.by}
              </span>
            )}
            <button
              onClick={() => {
                publishTemplate(version, actor);
                toast.success(`CAM template ${version} published`, {
                  description: `${enabled.length} sections, ${tone.label}. Applies to every memo drafted from now.`,
                });
              }}
              className="flex h-9 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Upload className="h-3.5 w-3.5" /> Publish {version}
            </button>
          </>
        }
      />

      <div className="grid gap-4 px-6 py-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <div className="space-y-4">
          <Panel
            title="Sections"
            subtitle={`${enabled.length} of ${s.template.length} enabled · about ${words.toLocaleString("en-IN")} words · ${tone.label}`}
            action={
              <label className="flex items-center gap-2 text-[12px] text-muted-foreground">
                Version
                <input
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  className="h-8 w-20 rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                />
              </label>
            }
          >
            <ol className="divide-y divide-border">
              {s.template.map((sec, i) => (
                <li key={sec.id}>
                  <div
                    className={cn(
                      "flex items-start gap-3 px-4 py-2.5",
                      !sec.enabled && "opacity-60",
                    )}
                  >
                    <span className="w-5 shrink-0 pt-0.5 text-[12px] tabular-nums text-muted-foreground">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <button
                        onClick={() => setOpenSection(openSection === sec.id ? null : sec.id)}
                        className="block text-left"
                      >
                        <p className="text-[13px] font-medium text-foreground">{sec.title}</p>
                        <p className="mt-0.5 text-[11.5px] text-muted-foreground">{sec.purpose}</p>
                      </button>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10.5px]">
                        <span className="rounded border border-border bg-surface-muted px-1.5 py-0.5 text-muted-foreground">
                          about {sec.words} words
                        </span>
                        <span className="rounded border border-border bg-surface-muted px-1.5 py-0.5 text-muted-foreground">
                          {CITATION_LABEL[sec.citations]}
                        </span>
                        {sec.required && (
                          <span className="rounded border border-info/25 bg-info-soft px-1.5 py-0.5 text-info">
                            Mandatory section
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        onClick={() => moveSection(sec.id, -1, actor)}
                        disabled={i === 0}
                        className="rounded border border-border p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30"
                        aria-label={`Move ${sec.title} up`}
                      >
                        <ArrowUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => moveSection(sec.id, 1, actor)}
                        disabled={i === s.template.length - 1}
                        className="rounded border border-border p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30"
                        aria-label={`Move ${sec.title} down`}
                      >
                        <ArrowDown className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => {
                          if (sec.required) {
                            toast.error(`${sec.title} is mandatory`, {
                              description: "Policy requires this section in every CAM.",
                            });
                            return;
                          }
                          updateSection(sec.id, { enabled: !sec.enabled }, actor);
                        }}
                        className={cn(
                          "rounded border px-2 py-1 text-[11.5px]",
                          sec.enabled
                            ? "border-positive/30 bg-positive-soft text-positive"
                            : "border-border bg-surface text-muted-foreground",
                        )}
                      >
                        {sec.enabled ? "On" : "Off"}
                      </button>
                    </div>
                  </div>
                  {openSection === sec.id && (
                    <div className="grid gap-3 border-t border-border bg-surface-muted/40 px-4 py-3 sm:grid-cols-2">
                      <label className="text-[12px]">
                        <span className="field-label">Section heading</span>
                        <input
                          value={sec.title}
                          onChange={(e) => updateSection(sec.id, { title: e.target.value }, actor)}
                          className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                        />
                      </label>
                      <label className="text-[12px]">
                        <span className="field-label">Target length (words)</span>
                        <input
                          type="number"
                          step={20}
                          value={sec.words}
                          onChange={(e) =>
                            updateSection(sec.id, { words: Number(e.target.value) || 0 }, actor)
                          }
                          className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground"
                        />
                      </label>
                      <label className="text-[12px] sm:col-span-2">
                        <span className="field-label">Purpose shown to the drafting engine</span>
                        <input
                          value={sec.purpose}
                          onChange={(e) =>
                            updateSection(sec.id, { purpose: e.target.value }, actor)
                          }
                          className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                        />
                      </label>
                      <div className="sm:col-span-2">
                        <span className="field-label">Citation rule</span>
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {(["every-figure", "material-only", "none"] as const).map((c) => (
                            <button
                              key={c}
                              onClick={() => updateSection(sec.id, { citations: c }, actor)}
                              className={cn(
                                "rounded border px-2 py-1 text-[11.5px]",
                                sec.citations === c
                                  ? "border-primary bg-primary/10 text-primary"
                                  : "border-border bg-surface text-muted-foreground hover:bg-muted",
                              )}
                            >
                              {CITATION_LABEL[c]}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ol>
          </Panel>

          <Panel
            title="House tone and presentation"
            subtitle="How the drafting engine writes, for every memo in this tenant."
          >
            <div className="space-y-3 px-4 py-3">
              <div>
                <p className="field-label">Tone</p>
                <div className="mt-1.5 grid gap-2 md:grid-cols-3">
                  {TONE_PRESETS.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setTemplateSettings({ tone: t.id }, actor)}
                      className={cn(
                        "rounded border p-2.5 text-left",
                        s.templateSettings.tone === t.id
                          ? "border-primary bg-primary/5"
                          : "border-border bg-surface hover:bg-muted",
                      )}
                    >
                      <p className="text-[12.5px] font-medium text-foreground">{t.label}</p>
                      <p className="mt-0.5 text-[11.5px] text-muted-foreground">{t.detail}</p>
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="field-label">Figures</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {(
                      [
                        ["crore-2dp", "INR crore, 2 dp"],
                        ["lakh-0dp", "INR lakh, 0 dp"],
                        ["absolute", "Absolute rupees"],
                      ] as const
                    ).map(([id, label]) => (
                      <button
                        key={id}
                        onClick={() => setTemplateSettings({ figures: id }, actor)}
                        className={cn(
                          "rounded border px-2 py-1 text-[11.5px]",
                          s.templateSettings.figures === id
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-border bg-surface text-muted-foreground hover:bg-muted",
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="field-label">Citations</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {(
                      [
                        ["inline", "In-line after each claim"],
                        ["endnote", "Endnotes per section"],
                      ] as const
                    ).map(([id, label]) => (
                      <button
                        key={id}
                        onClick={() => setTemplateSettings({ citations: id }, actor)}
                        className={cn(
                          "rounded border px-2 py-1 text-[11.5px]",
                          s.templateSettings.citations === id
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-border bg-surface text-muted-foreground hover:bg-muted",
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <label className="block text-[12px]">
                <span className="field-label">Document header</span>
                <input
                  value={s.templateSettings.header}
                  onChange={(e) => setTemplateSettings({ header: e.target.value }, actor)}
                  className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                />
              </label>
              <div>
                <p className="field-label">Annexures</p>
                <ul className="mt-1 space-y-1">
                  {s.templateSettings.annexures.map((a) => (
                    <li key={a} className="text-[12px] text-muted-foreground">
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Panel>
        </div>

        {/* preview */}
        <div className="space-y-4">
          <Panel
            title="Structure preview"
            subtitle="The draft template's order and tone. Section content is filled in once a memo is drafted."
          >
            <div className="max-h-[900px] overflow-y-auto px-5 py-4">
              <p className="border-b border-border pb-2 text-[11px] uppercase tracking-wide text-muted-foreground">
                {s.templateSettings.header}
              </p>
              {s.template.filter((sec) => sec.enabled).length === 0 ? (
                <EmptyState
                  title="No sections enabled"
                  description="Turn on at least one section to see the structure preview."
                />
              ) : (
                <div className="mt-4 space-y-4">
                  {s.template
                    .filter((sec) => sec.enabled)
                    .map((sec, i) => (
                      <section key={sec.id}>
                        <h4 className="text-[12.5px] font-semibold text-foreground">
                          {i + 1}. {sec.title}
                        </h4>
                        <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                          {sec.purpose}
                        </p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {CITATION_LABEL[sec.citations]} · target {sec.words} words ·{" "}
                          {s.templateSettings.citations === "inline"
                            ? "citations in line"
                            : "citations as endnotes"}
                        </p>
                      </section>
                    ))}
                </div>
              )}
              <p className="mt-4 border-t border-border pt-2 text-[11.5px] text-muted-foreground">
                {s.templateSettings.annexures.join(" · ")}
              </p>
            </div>
          </Panel>

          <div className="rounded border border-border bg-surface p-4">
            <p className="flex items-center gap-1.5 text-[12.5px] font-semibold">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> Ask the copilot
            </p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              "Draft a section outline for a new Trade Finance annexure" — the copilot proposes
              headings, the evidence each needs and where it should sit in the running order.
            </p>
            <p className="mt-2 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
              Published templates shape every memo in the {t("nav.memoLibrary")}.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
