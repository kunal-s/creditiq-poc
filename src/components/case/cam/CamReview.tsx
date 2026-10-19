import { Link, useRouterState } from "@tanstack/react-router";
import { History, Pencil, RotateCcw, ShieldAlert, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { Cam, CamBlock, CamReview as Review, CamSection, CamSummaryItem } from "@/api/types";
import {
  Block,
  CamMemo,
  Downloads,
  Recommendation,
  Sources,
  SourcesContext,
  Summary,
} from "@/components/case/Outputs";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { api } from "@/api/client";
import { useCam, useCamChange, useCamRegenerate } from "@/domain/findings";
import { camSectionAnchor, configLabel, formatDay, sourcesById } from "@/domain/outputs";
import { cn } from "@/lib/utils";

// The CAM draft and review (F-23): the memo's eight sections, one at a time, chosen from the list
// on the left, with the draft's state under it. Each section says whether its words are the
// engine's, a person's or a copilot redraft a person kept, and offers: Edit in my words,
// Regenerate with copilot (a redraft to read, then keep or discard), Override a figure (kept with
// the value drafted and the reason) and Request more data (it goes on the query list). The
// engine drafts and keeps every change with who and when; the screen sends what a person did.
//
// Test ids:
//   cam-review               the view: cam-review-meta (as of, configuration, run) with the
//                            downloads; cam-review-banner while a blocking discrepancy is open
//   cam-review-nav           the sections: cam-review-nav-item each (data-section, data-state,
//                            aria-current on the one shown)
//   cam-review-state         the draft's state: cam-state-citations, cam-state-edited,
//                            cam-state-overrides, cam-state-requests, cam-state-rating
//   cam-review-section       the section shown (data-section, data-state): cam-section-kicker,
//                            cam-section-title, cam-section-purpose, cam-section-badge, its
//                            actions cam-action-edit, cam-action-regenerate, cam-action-override,
//                            cam-action-request, cam-action-restore; their panels cam-edit-panel,
//                            cam-regenerate-panel (cam-regenerate-preview, cam-regenerate-keep),
//                            cam-override-panel (cam-override-figure, -original, -value, -reason,
//                            cam-override-save), cam-request-panel (cam-request-text,
//                            cam-request-save), cam-action-error; then its body (the memo's
//                            blocks, the summary or the recommendation), cam-section-overrides
//                            and cam-section-requests

type Shown = {
  id: string;
  number: number;
  title: string;
  purpose: string | null | undefined;
  review: Review;
  body: ReactNode;
};

const SUMMARY = "summary";
const MODE_KEY = "creditiq.cam.mode";
const RECOMMENDATION = "recommendation";

/** The pages the memo cites, each counted once (a document's page cited twice is one). */
function countCitations(m: Cam): number {
  const seen = new Set<string>();
  const add = (list: { document_id: string; page: number }[] | undefined) =>
    (list ?? []).forEach((e) => seen.add(`${e.document_id}:${e.page}`));
  for (const b of m.sections.flatMap((s) => s.blocks ?? []) as CamBlock[]) {
    add(b.paragraph?.citations);
    (b.facts ?? []).forEach((f) => add(f.value.citations));
    (b.table?.rows ?? []).forEach((row) => row.forEach((c) => add(c.citations)));
  }
  m.summary.forEach((i) => add(i.citations));
  return seen.size;
}

/** The discrepancy still open that blocks submission, for the banner. */
function blockingOpen(m: Cam): CamSummaryItem | undefined {
  return m.summary.find(
    (i) => i.kind === "finding" && i.blocking && i.status !== "Accepted as valid",
  );
}

function stateLabel(review: Review): string {
  if (review.state === "edited")
    return t("outputs.review.state.edited", { name: review.by_name ?? review.by ?? "" });
  if (review.state === "regenerated")
    return t("outputs.review.state.regenerated", { name: review.by_name ?? review.by ?? "" });
  return t("outputs.review.state.machine");
}

export function CamReviewView({ caseId }: { caseId: string }) {
  const cam = useCam(caseId);
  // A section at a time to review it, or the whole memo top to bottom to read it through. A link
  // to a part (#cam-section-<id>, from the PD note) opens the section that holds it.
  const [mode, setModeState] = useState<"sections" | "memo">(() => {
    try {
      return window.sessionStorage.getItem(MODE_KEY) === "memo" ? "memo" : "sections";
    } catch {
      return "sections";
    }
  });
  // Kept for the browser session, so the way back from the board finds the memo as it was left.
  const setMode = (next: "sections" | "memo") => {
    setModeState(next);
    try {
      window.sessionStorage.setItem(MODE_KEY, next);
    } catch {
      // A private window: the choice lasts this page only.
    }
  };
  return (
    <QueryView query={cam}>
      {(m) => (
        <div className="space-y-3">
          <div
            className="inline-flex rounded border border-border bg-surface p-0.5"
            role="group"
            aria-label={t("outputs.review.mode")}
          >
            {(["sections", "memo"] as const).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setMode(key)}
                aria-pressed={mode === key}
                className={cn(
                  "rounded px-3 py-1 text-[12.5px] font-medium transition-colors",
                  mode === key
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
                data-testid={`cam-mode-${key}`}
              >
                {t(`outputs.review.modes.${key}`)}
              </button>
            ))}
          </div>
          {mode === "memo" ? (
            <CamMemo caseId={caseId} m={m} />
          ) : (
            <SourcesContext.Provider value={sourcesById(m.sources ?? [])}>
              <ReviewBody caseId={caseId} m={m} />
            </SourcesContext.Provider>
          )}
        </div>
      )}
    </QueryView>
  );
}

function ReviewBody({ caseId, m }: { caseId: string; m: Cam }) {
  const shown: Shown[] = useMemo(
    () => [
      ...m.sections.map((s) => ({
        id: s.id,
        number: s.number,
        title: s.title,
        purpose: s.purpose,
        review: s.review ?? { state: "machine" as const },
        body: <SectionBody caseId={caseId} section={s} />,
      })),
      {
        id: SUMMARY,
        number: m.summary_number,
        title: m.summary_title,
        purpose: m.summary_purpose,
        review: m.summary_review ?? { state: "machine" as const },
        body: (
          <div className="space-y-3">
            <Words paragraphs={m.summary_review?.paragraphs ?? []} />
            {m.rating_note && (
              <p
                className="rounded border border-border bg-surface-muted/50 px-3 py-2 text-[12.5px] text-muted-foreground"
                data-testid="cam-rating-note"
              >
                {m.rating_note}
              </p>
            )}
            <Summary caseId={caseId} m={m} headed={false} />
          </div>
        ),
      },
      {
        id: RECOMMENDATION,
        number: m.recommendation_number,
        title: m.recommendation_title,
        purpose: m.recommendation_purpose,
        review: m.recommendation_review ?? { state: "machine" as const },
        body: <Recommendation m={m} headed={false} />,
      },
    ],
    [caseId, m],
  );

  // A link to a section or one of its parts (#cam-section-<id>, from the PD note) shows it.
  const hash = useRouterState({ select: (s) => s.location.hash });
  const fromHash = (h: string): string | null => {
    const id = h.replace(/^#?cam-section-/, "");
    if (!id || id === h.replace(/^#/, "")) return null;
    const owner = m.sections.find((s) => s.id === id || (s.parts ?? []).some((p) => p.id === id));
    return owner?.id ?? (shown.some((s) => s.id === id) ? id : null);
  };
  const [selected, setSelected] = useState<string>(() => shown[0]!.id);
  useEffect(() => {
    const raw = hash || (typeof window !== "undefined" ? window.location.hash : "");
    const id = fromHash(raw);
    if (!id) return;
    setSelected(id);
    // Then to the part the link names, once its section is drawn.
    const target = raw.replace(/^#/, "");
    const timers = [0, 150, 400].map((ms) =>
      window.setTimeout(
        () => document.getElementById(target)?.scrollIntoView({ block: "start" }),
        ms,
      ),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hash]);
  const current = shown.find((s) => s.id === selected) ?? shown[0]!;
  const blocking = blockingOpen(m);
  const total = shown.length;
  const edited = shown.filter((s) => s.review.state !== "machine").length;
  const overrides = shown.reduce((n, s) => n + (s.review.overrides?.length ?? 0), 0);
  const requests = shown.reduce((n, s) => n + (s.review.requests?.length ?? 0), 0);

  return (
    <div className="space-y-4" data-testid="cam-review">
      <div
        className="flex flex-wrap items-center justify-between gap-3"
        data-testid="cam-review-meta"
      >
        <p className="tabular text-[12px] text-muted-foreground">
          {m.title} · {m.borrower} · {t("outputs.header.asOf", { date: formatDay(m.as_of) })} ·{" "}
          <span title={m.config_version}>
            {t("outputs.header.config", { version: configLabel(m) })}
          </span>
          {m.run_id && ` · ${t("outputs.header.run", { id: m.run_id })}`}
        </p>
        <Downloads caseId={caseId} output="cam" />
      </div>
      {m.template_note && (
        <p className="rounded border border-info/40 bg-info-soft px-3 py-2 text-[12px] italic text-info">
          {m.template_note}
        </p>
      )}
      {blocking && (
        <p
          className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded border border-destructive/40 bg-critical-soft px-4 py-2.5 text-[12.5px] text-foreground"
          data-testid="cam-review-banner"
        >
          <ShieldAlert className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
          {t("outputs.review.banner")}
          <Link
            to="/appraisals/$caseId/cross-verification"
            params={{ caseId }}
            search={{ finding: blocking.ref }}
            className="font-medium text-destructive hover:underline"
          >
            {t("outputs.review.bannerOpen", { ref: blocking.ref })} →
          </Link>
        </p>
      )}

      <div className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-4 lg:sticky lg:top-4 lg:self-start">
          <nav
            className="rounded border border-border bg-surface"
            aria-label={t("outputs.review.sections")}
            data-testid="cam-review-nav"
          >
            <header className="border-b border-border px-4 py-3">
              <h2 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t("outputs.review.sections")}
              </h2>
              <p className="mt-0.5 text-[12px] text-muted-foreground">
                {t("outputs.review.sectionCount", { n: total })}
              </p>
            </header>
            <ol className="space-y-0.5 p-2">
              {shown.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(s.id)}
                    aria-current={s.id === current.id ? "true" : undefined}
                    className={cn(
                      "flex w-full items-start gap-2.5 rounded px-2.5 py-2 text-left text-[13px] transition-colors",
                      s.id === current.id
                        ? "bg-surface-muted font-semibold text-foreground"
                        : "text-muted-foreground hover:bg-surface-muted/60 hover:text-foreground",
                    )}
                    data-testid="cam-review-nav-item"
                    data-section={s.id}
                    data-state={s.review.state}
                  >
                    <span className="tabular w-4 shrink-0 text-[12px]">{s.number}</span>
                    <span className="min-w-0 flex-1 break-words">{s.title}</span>
                    {s.review.state !== "machine" && (
                      <Pencil className="mt-0.5 h-3 w-3 shrink-0 text-primary" aria-hidden />
                    )}
                  </button>
                </li>
              ))}
            </ol>
          </nav>
          <section
            className="rounded border border-border bg-surface"
            data-testid="cam-review-state"
          >
            <h2 className="border-b border-border px-4 py-3 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("outputs.review.draftState")}
            </h2>
            <dl className="divide-y divide-border text-[12.5px]">
              {[
                ["citations", t("outputs.review.citations"), String(countCitations(m))],
                ["edited", t("outputs.review.edited"), `${edited} of ${total}`],
                ["overrides", t("outputs.review.overrides"), String(overrides)],
                ["requests", t("outputs.review.requests"), String(requests)],
                ["rating", t("outputs.review.rating"), t("outputs.review.notRated")],
              ].map(([key, label, value]) => (
                <div key={key} className="flex items-baseline justify-between gap-3 px-4 py-2">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd
                    className="tabular text-right text-foreground"
                    data-testid={`cam-state-${key}`}
                  >
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </aside>

        <ReviewSection key={current.id} caseId={caseId} m={m} s={current} total={total} />
      </div>
      <Sources caseId={caseId} sources={m.sources ?? []} />
    </div>
  );
}

/** A drafted section's blocks: its parts each under its subheading, each with its anchor. */
function SectionBody({ caseId, section }: { caseId: string; section: CamSection }) {
  const blocks = section.blocks ?? [];
  const parts = section.parts ?? [];
  if (blocks.length === 0)
    return (
      <p className="text-[12.5px] text-muted-foreground" data-testid="cam-section-empty">
        {section.empty}
      </p>
    );
  // The subheadings are the parts' titles, in order: each carries its part's anchor.
  let part = 0;
  return (
    <div className="space-y-2.5">
      {blocks.map((block, i) => {
        if (block.kind === "subheading" && parts.length > 1) {
          const p = parts[part++];
          return (
            <h4
              key={i}
              id={p ? camSectionAnchor(p.id) : undefined}
              className="scroll-mt-4 pt-1 text-[13px] font-semibold"
              data-testid="cam-subheading"
              data-part={p?.id}
            >
              {block.text}
            </h4>
          );
        }
        return <Block key={i} caseId={caseId} block={block} />;
      })}
    </div>
  );
}

function Words({ paragraphs }: { paragraphs: string[] }) {
  if (paragraphs.length === 0) return null;
  return (
    <div className="space-y-2.5">
      {paragraphs.map((p, i) => (
        <p key={i} className="text-[13px] leading-relaxed" data-testid="cam-paragraph">
          {p}
        </p>
      ))}
    </div>
  );
}

type Panel = "edit" | "regenerate" | "override" | "request" | null;

function ReviewSection({
  caseId,
  m,
  s,
  total,
}: {
  caseId: string;
  m: Cam;
  s: Shown;
  total: number;
}) {
  const [panel, setPanel] = useState<Panel>(null);
  const toggle = (p: Panel) => setPanel((now) => (now === p ? null : p));
  const restore = useCamChange(caseId, () => api.camRestore(caseId, s.id));
  const review = s.review;
  const drafted = review.state === "machine";
  const anchor = m.sections.some((x) => x.id === s.id) ? camSectionAnchor(s.id) : undefined;
  return (
    <section
      id={anchor}
      className="min-w-0 scroll-mt-4 rounded border border-border bg-surface"
      data-testid="cam-review-section"
      data-section={s.id}
      data-state={review.state}
    >
      <header className="flex flex-wrap items-start justify-between gap-3 px-5 pb-3 pt-4">
        <div className="min-w-0">
          <p className="field-label" data-testid="cam-section-kicker">
            {t("outputs.review.kicker", { n: s.number, total, title: m.title })}
          </p>
          <h3
            className="mt-1 text-[17px] font-semibold text-foreground"
            data-testid="cam-section-title"
          >
            {s.title}
          </h3>
          {s.purpose && (
            <p
              className="mt-0.5 text-[12.5px] text-muted-foreground"
              data-testid="cam-section-purpose"
            >
              {s.purpose}
            </p>
          )}
        </div>
        <span className="flex flex-wrap items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11.5px]",
              drafted
                ? "border-border bg-surface-muted text-muted-foreground"
                : "border-primary/30 bg-info-soft text-primary",
            )}
            data-testid="cam-section-badge"
          >
            {review.state === "regenerated" ? (
              <Sparkles className="h-3 w-3" aria-hidden />
            ) : review.state === "edited" ? (
              <Pencil className="h-3 w-3" aria-hidden />
            ) : (
              <Sparkles className="h-3 w-3" aria-hidden />
            )}
            {stateLabel(review)}
          </span>
          <span className="rounded border border-border px-2 py-0.5 text-[11.5px] text-muted-foreground">
            {review.at
              ? t("outputs.review.changedAt", { date: formatDay(review.at.slice(0, 10)) })
              : t("outputs.review.draftedAsOf", { date: formatDay(m.as_of) })}
          </span>
        </span>
      </header>

      <div className="flex flex-wrap gap-2 border-y border-border px-5 py-3">
        <ActionButton
          primary
          active={panel === "edit"}
          onClick={() => toggle("edit")}
          testId="cam-action-edit"
          icon={<Pencil className="h-4 w-4" aria-hidden />}
        >
          {t("outputs.review.edit")}
        </ActionButton>
        <ActionButton
          active={panel === "regenerate"}
          onClick={() => toggle("regenerate")}
          testId="cam-action-regenerate"
          disabled={!m.copilot}
          title={m.copilot ? undefined : t("outputs.review.copilotOff")}
          icon={<Sparkles className="h-4 w-4" aria-hidden />}
        >
          {t("outputs.review.regenerate")}
        </ActionButton>
        <ActionButton
          active={panel === "override"}
          onClick={() => toggle("override")}
          testId="cam-action-override"
          icon={<History className="h-4 w-4" aria-hidden />}
        >
          {t("outputs.review.override")}
        </ActionButton>
        <ActionButton
          active={panel === "request"}
          onClick={() => toggle("request")}
          testId="cam-action-request"
        >
          {t("outputs.review.request")}
        </ActionButton>
        {!drafted && (
          <ActionButton
            onClick={() => restore.mutate(undefined)}
            testId="cam-action-restore"
            icon={<RotateCcw className="h-4 w-4" aria-hidden />}
          >
            {t("outputs.review.restore")}
          </ActionButton>
        )}
      </div>

      {panel === "edit" && <EditPanel caseId={caseId} m={m} s={s} onDone={() => setPanel(null)} />}
      {panel === "regenerate" && (
        <RegeneratePanel caseId={caseId} s={s} onDone={() => setPanel(null)} />
      )}
      {panel === "override" && (
        <OverridePanel caseId={caseId} s={s} onDone={() => setPanel(null)} />
      )}
      {panel === "request" && <RequestPanel caseId={caseId} s={s} onDone={() => setPanel(null)} />}

      <div className="space-y-4 px-5 py-4">
        {s.body}
        {(review.overrides?.length ?? 0) > 0 && !anchor && (
          <ul className="space-y-1 text-[12px]" data-testid="cam-section-overrides">
            {review.overrides!.map((o) => (
              <li key={o.id}>
                {t("outputs.review.overrideLine", {
                  figure: o.figure,
                  original: o.original,
                  value: o.value,
                  reason: o.reason,
                  name: o.by_name ?? o.by,
                })}
              </li>
            ))}
          </ul>
        )}
        {(review.requests?.length ?? 0) > 0 && (
          <ul
            className="space-y-1 rounded border border-border bg-surface-muted/40 px-3 py-2 text-[12px]"
            data-testid="cam-section-requests"
          >
            {review.requests!.map((r) => (
              <li key={r.id}>{t("outputs.review.requestLine", { text: r.text })}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function ActionButton({
  children,
  onClick,
  primary,
  active,
  disabled,
  title,
  icon,
  testId,
}: {
  children: ReactNode;
  onClick: () => void;
  primary?: boolean;
  active?: boolean;
  disabled?: boolean;
  title?: string | undefined;
  icon?: ReactNode;
  testId: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-expanded={active}
      className={cn(
        "inline-flex h-9 items-center gap-1.5 rounded px-3.5 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        primary
          ? "bg-primary text-primary-foreground hover:opacity-90"
          : "border border-border bg-surface text-foreground hover:bg-surface-muted",
        active && !primary && "bg-surface-muted",
      )}
      data-testid={testId}
    >
      {icon}
      {children}
    </button>
  );
}

function PanelFrame({
  children,
  testId,
  onClose,
  tone = "neutral",
}: {
  children: ReactNode;
  testId: string;
  onClose: () => void;
  tone?: "neutral" | "warm";
}) {
  return (
    <div className="px-5 pt-3">
      <div
        className={cn(
          "relative rounded border px-4 py-3",
          tone === "warm" ? "border-flag/40 bg-flag-soft/40" : "border-border bg-surface-muted/40",
        )}
        data-testid={testId}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-2 top-2 rounded p-1 text-muted-foreground hover:text-foreground"
          aria-label={t("outputs.review.close")}
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
        {children}
      </div>
    </div>
  );
}

function ErrorLine({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <p className="mt-2 text-[12px] text-destructive" data-testid="cam-action-error">
      {message}
    </p>
  );
}

const field =
  "w-full rounded border border-border bg-surface px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring";

/** The section's paragraphs as they read now, to put in a person's words. */
function currentWords(m: Cam, s: Shown): string[] {
  if (s.review.paragraphs && s.review.paragraphs.length > 0) return s.review.paragraphs;
  if (s.id === SUMMARY) return m.summary.map((i) => i.text);
  if (s.id === RECOMMENDATION) return m.recommendation ? m.recommendation.split("\n\n") : [];
  const section = m.sections.find((x) => x.id === s.id);
  return (section?.blocks ?? [])
    .filter((b) => b.kind === "paragraph" && b.paragraph)
    .map((b) => b.paragraph!.text);
}

function EditPanel({
  caseId,
  m,
  s,
  onDone,
}: {
  caseId: string;
  m: Cam;
  s: Shown;
  onDone: () => void;
}) {
  const [text, setText] = useState(() => currentWords(m, s).join("\n\n"));
  const save = useCamChange(caseId, (paragraphs: string[]) =>
    api.camWords(caseId, s.id, { paragraphs, source: "person" }),
  );
  const paragraphs = text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
  return (
    <PanelFrame testId="cam-edit-panel" onClose={onDone}>
      <label className="block text-[12px] font-medium text-muted-foreground" htmlFor="cam-edit">
        {t("outputs.review.editHint")}
      </label>
      <textarea
        id="cam-edit"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={Math.min(18, Math.max(6, paragraphs.length * 3))}
        className={cn(field, "mt-1.5 leading-relaxed")}
        data-testid="cam-edit-text"
      />
      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={() => save.mutate(paragraphs, { onSuccess: onDone })}
          disabled={paragraphs.length === 0 || save.isPending}
          className="h-9 rounded bg-primary px-4 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
          data-testid="cam-edit-save"
        >
          {t("outputs.review.editSave")}
        </button>
        <span className="text-[11.5px] text-muted-foreground">{t("outputs.review.editNote")}</span>
      </div>
      <ErrorLine error={save.error} />
    </PanelFrame>
  );
}

function RegeneratePanel({ caseId, s, onDone }: { caseId: string; s: Shown; onDone: () => void }) {
  const [instruction, setInstruction] = useState("");
  const draft = useCamRegenerate(caseId);
  const keep = useCamChange(
    caseId,
    ({ paragraphs, model }: { paragraphs: string[]; model: string }) =>
      api.camWords(caseId, s.id, { paragraphs, source: "copilot", model }),
  );
  const result = draft.data;
  return (
    <PanelFrame testId="cam-regenerate-panel" onClose={onDone}>
      <label
        className="block text-[12px] font-medium text-muted-foreground"
        htmlFor="cam-instruction"
      >
        {t("outputs.review.instruction")}
      </label>
      <div className="mt-1.5 flex flex-wrap gap-2">
        <input
          id="cam-instruction"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder={t("outputs.review.instructionPlaceholder")}
          className={cn(field, "min-w-0 flex-1 basis-64")}
          data-testid="cam-regenerate-instruction"
        />
        <button
          type="button"
          onClick={() => draft.mutate({ sectionId: s.id, instruction })}
          disabled={draft.isPending}
          className="inline-flex h-9 items-center gap-1.5 rounded bg-primary px-4 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
          data-testid="cam-regenerate-run"
        >
          <Sparkles className="h-4 w-4" aria-hidden />
          {draft.isPending ? t("outputs.review.redrafting") : t("outputs.review.redraft")}
        </button>
      </div>
      <ErrorLine error={draft.error} />
      {result && (
        <div className="mt-3 space-y-2" data-testid="cam-regenerate-preview">
          <p className="text-[11.5px] text-muted-foreground">
            {t(result.recorded ? "outputs.review.replayed" : "outputs.review.redrafted", {
              model: result.model,
            })}
          </p>
          {result.paragraphs.map((p, i) => (
            <p
              key={i}
              className="rounded border border-dashed border-primary/30 bg-surface px-3 py-2 text-[13px] leading-relaxed"
            >
              {p}
            </p>
          ))}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() =>
                keep.mutate(
                  { paragraphs: result.paragraphs, model: result.model },
                  { onSuccess: onDone },
                )
              }
              disabled={keep.isPending}
              className="h-9 rounded bg-primary px-4 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
              data-testid="cam-regenerate-keep"
            >
              {t("outputs.review.keep")}
            </button>
            <button
              type="button"
              onClick={() => draft.reset()}
              className="h-9 rounded border border-border px-4 text-[13px] font-medium"
              data-testid="cam-regenerate-discard"
            >
              {t("outputs.review.discard")}
            </button>
          </div>
          <ErrorLine error={keep.error} />
        </div>
      )}
    </PanelFrame>
  );
}

function OverridePanel({ caseId, s, onDone }: { caseId: string; s: Shown; onDone: () => void }) {
  const [form, setForm] = useState({ figure: "", original: "", value: "", reason: "" });
  const save = useCamChange(caseId, () => api.camOverride(caseId, s.id, form));
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  const ready = Object.values(form).every((v) => v.trim()) && form.reason.trim().length >= 3;
  const fields: [keyof typeof form, string][] = [
    ["figure", "figure"],
    ["original", "original"],
    ["value", "value"],
    ["reason", "reason"],
  ];
  return (
    <PanelFrame testId="cam-override-panel" onClose={onDone} tone="warm">
      <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
        {fields.map(([key, label]) => (
          <label key={key} className="block min-w-0">
            <span className="text-[12px] text-muted-foreground">
              {t(`outputs.review.overrideField.${label}`)}
            </span>
            <input
              value={form[key]}
              onChange={set(key)}
              placeholder={t(`outputs.review.overridePlaceholder.${label}`)}
              className={cn(field, "mt-1")}
              data-testid={`cam-override-${key}`}
            />
          </label>
        ))}
      </div>
      <button
        type="button"
        onClick={() => save.mutate(undefined, { onSuccess: onDone })}
        disabled={!ready || save.isPending}
        className="mt-3 h-9 rounded bg-primary px-4 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
        data-testid="cam-override-save"
      >
        {t("outputs.review.overrideSave")}
      </button>
      <ErrorLine error={save.error} />
    </PanelFrame>
  );
}

function RequestPanel({ caseId, s, onDone }: { caseId: string; s: Shown; onDone: () => void }) {
  const [text, setText] = useState("");
  const save = useCamChange(caseId, () => api.camRequest(caseId, s.id, { text }));
  return (
    <PanelFrame testId="cam-request-panel" onClose={onDone}>
      <label className="block text-[12px] font-medium text-muted-foreground" htmlFor="cam-request">
        {t("outputs.review.requestHint")}
      </label>
      <textarea
        id="cam-request"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        placeholder={t("outputs.review.requestPlaceholder")}
        className={cn(field, "mt-1.5")}
        data-testid="cam-request-text"
      />
      <button
        type="button"
        onClick={() => save.mutate(undefined, { onSuccess: onDone })}
        disabled={text.trim().length < 3 || save.isPending}
        className="mt-2 h-9 rounded bg-primary px-4 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
        data-testid="cam-request-save"
      >
        {t("outputs.review.requestSave")}
      </button>
      <ErrorLine error={save.error} />
    </PanelFrame>
  );
}
