import { useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Eye,
  MapPin,
  Minus,
  MoveHorizontal,
  Plus,
  Type,
} from "lucide-react";
import type { FileRecord, IntegrityFigure, IntegrityFinding, LogicalDocument } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { Skeleton } from "@/components/ui/skeleton";
import { t, tOr } from "@/config/terminology";
import {
  useCaseDocuments,
  useCaseFiles,
  useFileFigures,
  useFilePageImage,
} from "@/domain/documents";
import {
  STATUS_TONE,
  checkKind,
  factRead,
  factRows,
  humanTimes,
  isNote,
  isWholePage,
  marksOf,
  standsOut,
  type Mark,
} from "@/domain/integrity";
import { IntegrityOverlay } from "./IntegrityOverlay";
import { cn } from "@/lib/utils";
import { FileFacts, StatusIcon, TraceButton, WhereInFile } from "./IntegrityPanel";
import {
  HumanReview,
  IntegritySummary,
  KindLabel,
  MadeAsChip,
  StateChip,
} from "./IntegritySummary";

/** F-07A: one file's integrity, whole. Its pages on the left with every place a
 * check points at drawn on them; on the right, what stands out, the fonts, and
 * every check run on the file — applied, with nothing to look at, or not run for
 * its kind — with the records each one read. Indicators for a person, never a
 * verdict. */

const ZOOMS = [0.75, 1, 1.25, 1.5, 2];

function PageCanvas({
  caseId,
  fileId,
  page,
  marks,
  figures,
  focus,
  zoom,
  onPick,
}: {
  caseId: string;
  fileId: string;
  page: number;
  marks: Mark[];
  figures: IntegrityFigure[] | undefined;
  focus: string | null;
  zoom: number;
  onPick: (m: Mark) => void;
}) {
  const image = useFilePageImage(caseId, fileId, page);
  if (image.isError) return <ErrorState error={image.error} compact />;
  return (
    <div
      className="relative mx-auto"
      style={{ width: `${Math.round(zoom * 100)}%`, maxWidth: zoom * 860 }}
    >
      {image.url ? (
        <img
          src={image.url}
          alt={t("viewer.pageAlt", { page })}
          className="block w-full rounded border border-border bg-white shadow-sm"
          data-testid="integrity-view-image"
        />
      ) : (
        <Skeleton className="aspect-[1/1.41] w-full" />
      )}
      {image.url && (
        <IntegrityOverlay marks={marks} figures={figures} focus={focus} onPick={onPick} />
      )}
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-md border border-border bg-card px-3.5 py-3", className)}>
      {children}
    </section>
  );
}

function Fold({
  title,
  children,
  open: initially = false,
  testId,
}: {
  title: string;
  children: React.ReactNode;
  open?: boolean;
  testId?: string;
}) {
  const [open, setOpen] = useState(initially);
  return (
    <div className="border-t border-border/70 pt-2" data-testid={testId}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-1 text-left text-[12px] font-medium text-foreground hover:text-primary"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        {title}
      </button>
      {open && <div className="mt-1.5">{children}</div>}
    </div>
  );
}

/** One check: its result, what it measured, each place it points at, and its records. */
function CheckRow({
  f,
  selected,
  onSelect,
  onShow,
  where,
}: {
  f: IntegrityFinding;
  selected: boolean;
  onSelect: () => void;
  onShow: (page: number, key: string) => void;
  where: ReturnType<typeof factRows>;
}) {
  const note = isNote(f);
  return (
    <li
      className={cn("-mx-1.5 flex gap-2 rounded px-1.5 py-1.5", selected && "bg-primary/5")}
      data-testid="integrity-view-check"
      data-code={f.code}
      data-status={f.status}
      id={`check-${f.code}`}
    >
      <StatusIcon status={f.status} note={note} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className={cn("text-[12px] text-foreground", standsOut(f) && "font-semibold")}>
            {tOr(`fileIntegrity.check.${f.code}`, f.code)}
          </span>
          <KindLabel kind={checkKind(f)} />
          <TraceButton selected={selected} onClick={onSelect} />
        </div>
        <p className="text-[11px] leading-snug text-muted-foreground">{humanTimes(f.finding)}</p>
        {f.method?.["limitations"] && checkKind(f) !== "passed" && (
          <p className="text-[10.5px] text-muted-foreground">
            <span className="font-medium">{t("fileIntegrity.summary.whyMatters")}:</span>{" "}
            {f.method["limitations"]}
          </p>
        )}
        {(f.evidence ?? []).slice(0, 8).map((e, i) => (
          <div
            key={i}
            className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-[10.5px] text-muted-foreground"
          >
            <span>
              <span className="font-medium">{t("fileIntegrity.observed")}:</span>{" "}
              {humanTimes(e.observed)}
              {" · "}
              <span className="font-medium">{t("fileIntegrity.threshold")}:</span>{" "}
              {humanTimes(e.threshold)}
            </span>
            {e.rect && (
              <button
                type="button"
                onClick={() => onShow(e.page, `${f.code}-${i}`)}
                className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
              >
                <MapPin className="h-3 w-3" />
                {t(isWholePage(e.rect) ? "fileIntegrity.showPage" : "fileIntegrity.showOnPage", {
                  page: e.page,
                })}
              </button>
            )}
          </div>
        ))}
        {selected && <WhereInFile rows={where} />}
      </div>
    </li>
  );
}

export function IntegrityView({ caseId, fileId }: { caseId: string; fileId: string }) {
  const files = useCaseFiles(caseId);
  const docs = useCaseDocuments(caseId);
  if (files.isError) return <ErrorState error={files.error} />;
  const file = files.data?.find((f) => f.id === fileId);
  if (!file) return <Skeleton className="h-96 w-full" />;
  const documents = (docs.data ?? []).filter((d) => d.file_id === fileId);
  return <View caseId={caseId} file={file} documents={documents} />;
}

function View({
  caseId,
  file,
  documents,
}: {
  caseId: string;
  file: FileRecord;
  documents: LogicalDocument[];
}) {
  const found = useMemo(() => file.integrity ?? [], [file.integrity]);
  const facts = file.integrity_facts ?? null;
  const rows = useMemo(() => (facts ? factRows(facts) : []), [facts]);
  const { marks, pagesReplaced } = useMemo(() => marksOf(found), [found]);
  const pageCount = Math.max(
    facts?.pages ?? 0,
    ...documents.map((d) => d.page_to),
    ...marks.map((m) => m.page),
    1,
  );
  const signals = found.filter(standsOut);
  const firstMarked = marks.find((m) => m.tone !== "muted")?.page ?? 1;
  const [showFigures, setShowFigures] = useState(false);
  const figures = useFileFigures(caseId, file.id, showFigures);
  const [page, setPage] = useState(firstMarked);
  const [zoom, setZoom] = useState(1);
  const [showAll, setShowAll] = useState(false);
  const [focus, setFocus] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [factsOpen, setFactsOpen] = useState(false);

  const onPage = marks.filter((m) => m.page === page && (showAll || m.tone !== "muted"));
  const show = (p: number, key: string) => {
    setPage(p);
    setFocus(key);
  };
  const pick = (m: Mark) => {
    setFocus(m.key);
    setSelected(m.finding.code);
    document
      .getElementById(`check-${m.finding.code}`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  };
  const select = (c: string) => {
    setSelected((cur) => (cur === c ? null : c));
    setFactsOpen(true);
  };
  const whereOf = (f: IntegrityFinding) => rows.filter((r) => factRead(r.key, f.reads ?? []));

  const skipped = found.filter((f) => f.skipped_for_type);
  const nothing = found.filter((f) => f.status === "not_applicable" && !f.skipped_for_type);
  const unknown = found.filter((f) => f.status === "unable_to_determine");
  const applied = found.filter((f) => ["pass", "warning", "review_required"].includes(f.status));
  const rank = (f: IntegrityFinding) =>
    standsOut(f) ? (f.status === "review_required" ? 0 : 1) : isNote(f) ? 2 : 3;
  const limits = [
    ...new Map(
      found.flatMap((f) =>
        (f.evidence ?? []).slice(0, 1).map((e) => [f.code, e.threshold] as const),
      ),
    ),
  ];
  const fonts = found.find((f) => f.code === "FONT_WITHIN_VALUE");
  const version = String(found[0]?.method?.["policy_version"] ?? "");

  const checkList = (list: IntegrityFinding[]) => (
    <ul className="divide-y divide-border/70">
      {[...list]
        .sort((a, b) => rank(a) - rank(b))
        .map((f) => (
          <CheckRow
            key={f.code}
            f={f}
            selected={selected === f.code}
            onSelect={() => select(f.code)}
            onShow={show}
            where={whereOf(f)}
          />
        ))}
    </ul>
  );

  return (
    <div className="flex flex-col gap-3 pb-10" data-testid="integrity-view">
      {/* The file, and what the checks came to. */}
      <Card className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Link
          to="/appraisals/$caseId/documents"
          params={{ caseId }}
          className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          {t("fileIntegrity.view.back")}
        </Link>
        <div className="min-w-0 flex-1">
          <p className="break-all text-[14px] font-semibold text-foreground">
            {file.original_name}
          </p>
          <p className="flex flex-wrap items-center gap-x-2 text-[11px] text-muted-foreground">
            <MadeAsChip file={file} documents={documents} />
            <span>{t("fileIntegrity.view.pages", { n: pageCount })}</span>
            <span className="font-mono">sha256 {file.sha256.slice(0, 12)}…</span>
          </p>
        </div>
        <StateChip file={file} />
      </Card>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        {/* The pages, with every place a check points at. */}
        <Card className="flex min-h-[520px] flex-col gap-2 p-0">
          <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2 text-[11.5px]">
            <button
              type="button"
              aria-label={t("fileIntegrity.view.zoomOut")}
              onClick={() => setZoom((z) => ZOOMS[Math.max(ZOOMS.indexOf(z) - 1, 0)] ?? z)}
              className="rounded border border-border p-1 hover:bg-muted"
            >
              <Minus className="h-3.5 w-3.5" />
            </button>
            <span className="w-10 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              aria-label={t("fileIntegrity.view.zoomIn")}
              onClick={() =>
                setZoom((z) => ZOOMS[Math.min(ZOOMS.indexOf(z) + 1, ZOOMS.length - 1)] ?? z)
              }
              className="rounded border border-border p-1 hover:bg-muted"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setZoom(1)}
              className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-1 hover:bg-muted"
            >
              <MoveHorizontal className="h-3.5 w-3.5" />
              {t("fileIntegrity.view.fit")}
            </button>
            <span className="mx-1 h-4 w-px bg-border" />
            <button
              type="button"
              aria-label={t("fileIntegrity.view.prev")}
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded border border-border p-1 hover:bg-muted disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span className="tabular-nums" data-testid="integrity-view-page">
              {t("fileIntegrity.view.page", { page, pages: pageCount })}
            </span>
            <button
              type="button"
              aria-label={t("fileIntegrity.view.next")}
              disabled={page >= pageCount}
              onClick={() => setPage((p) => p + 1)}
              className="rounded border border-border p-1 hover:bg-muted disabled:opacity-40"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
            <label className="ml-auto inline-flex cursor-pointer items-center gap-1.5 text-muted-foreground">
              <input
                type="checkbox"
                checked={showAll}
                onChange={(e) => setShowAll(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              <Eye className="h-3.5 w-3.5" />
              {t("fileIntegrity.view.showAll")}
            </label>
            <label className="inline-flex cursor-pointer items-center gap-1.5 text-muted-foreground">
              <input
                type="checkbox"
                checked={showFigures}
                onChange={(e) => setShowFigures(e.target.checked)}
                className="h-3.5 w-3.5"
                data-testid="integrity-view-show-figures"
              />
              {t("fileIntegrity.overlay.figures")}
            </label>
          </div>
          {pagesReplaced.has(page) && (
            <p className="mx-3 rounded border border-flag/40 bg-flag/10 px-2 py-1 text-[11px] text-flag-foreground">
              {t("fileIntegrity.view.pageReplaced")}
            </p>
          )}
          <div className="max-h-[78vh] flex-1 overflow-auto bg-muted/40 px-3 pb-3 pt-6">
            <PageCanvas
              caseId={caseId}
              fileId={file.id}
              page={page}
              marks={onPage}
              figures={
                showFigures ? (figures.data ?? []).filter((f) => f.page === page) : undefined
              }
              focus={focus}
              zoom={zoom}
              onPick={pick}
            />
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border px-3 py-2 text-[11px]">
            <span className="font-medium text-foreground" data-testid="integrity-view-mark-count">
              {onPage.length
                ? t("fileIntegrity.view.marksOnPage", { n: onPage.length })
                : t("fileIntegrity.view.noMarksOnPage")}
            </span>
            {onPage.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => pick(m)}
                className={cn(
                  "rounded px-1.5 py-0.5 text-[10.5px] font-medium",
                  focus === m.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/70",
                )}
              >
                {tOr(`fileIntegrity.mark.${m.finding.code}`, m.finding.code)}
              </button>
            ))}
          </div>
        </Card>

        {/* What stands out, the fonts, and every check. */}
        <div className="flex flex-col gap-3">
          <IntegritySummary
            caseId={caseId}
            file={file}
            showEvidenceLink={false}
            onShow={(f) => {
              const i = (f.evidence ?? []).findIndex((e) => e.rect);
              const e = f.evidence?.[i];
              if (e) show(e.page, `${f.code}-${i}`);
            }}
          />
          <HumanReview caseId={caseId} file={file} />

          <Card>
            <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Type className="h-3.5 w-3.5" />
              {t("fileIntegrity.view.fonts")}
            </p>
            {fonts && (
              <p
                className={cn(
                  "rounded px-2 py-1.5 text-[11.5px]",
                  standsOut(fonts)
                    ? "bg-flag/10 text-foreground"
                    : "bg-positive-soft text-foreground",
                )}
              >
                <span className="font-semibold">{t(`fileIntegrity.status.${fonts.status}`)}.</span>{" "}
                {fonts.finding}
              </p>
            )}
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              <span className="font-medium">{t("fileIntegrity.view.fontsNamed")}:</span>{" "}
              {facts?.fonts?.length ? facts.fonts.join(", ") : t("fileIntegrity.view.noFonts")}
            </p>
          </Card>

          <Card>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("fileIntegrity.view.checksTitle")}
            </p>
            <div
              className="mb-2 flex flex-wrap gap-1.5 text-[11px]"
              data-testid="integrity-view-counts"
            >
              {(
                [
                  [applied.length, "applied"],
                  [nothing.length, "nothingToLook"],
                  [skipped.length, "notRun"],
                  [unknown.length, "unknown"],
                  [limits.length, "limits"],
                ] as const
              ).map(([n, key]) => (
                <span key={key} className="rounded border border-border bg-muted/40 px-2 py-1">
                  <span className="mr-1 text-[13px] font-semibold tabular-nums text-foreground">
                    {n}
                  </span>
                  {t(`fileIntegrity.view.${key}`)}
                </span>
              ))}
            </div>
            <div className="flex flex-col gap-2">
              <Fold
                title={t("fileIntegrity.view.appliedList")}
                open
                testId="integrity-view-applied"
              >
                {checkList(applied)}
              </Fold>
              {nothing.length > 0 && (
                <Fold title={t("fileIntegrity.view.nothingList")}>{checkList(nothing)}</Fold>
              )}
              {skipped.length > 0 && (
                <Fold title={t("fileIntegrity.view.notRunList")}>{checkList(skipped)}</Fold>
              )}
              {unknown.length > 0 && (
                <Fold title={t("fileIntegrity.view.unknownList")}>{checkList(unknown)}</Fold>
              )}
              <Fold title={t("fileIntegrity.view.limitsList")}>
                <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-3 gap-y-1 text-[11px]">
                  {limits.map(([c, limit]) => (
                    <div key={c} className="contents">
                      <dt className="text-muted-foreground">
                        {tOr(`fileIntegrity.check.${c}`, c)}
                      </dt>
                      <dd className="text-foreground">{limit}</dd>
                    </div>
                  ))}
                </dl>
                <p className="mt-1.5 text-[10.5px] text-muted-foreground">
                  {t("fileIntegrity.view.limitsSource", { version })}
                </p>
              </Fold>
            </div>
          </Card>
        </div>
      </div>
      {facts && (
        <Card>
          <FileFacts
            rows={rows}
            highlight={found.find((f) => f.code === selected)?.reads ?? []}
            open={factsOpen}
            onToggle={() => setFactsOpen((v) => !v)}
          />
        </Card>
      )}
    </div>
  );
}
