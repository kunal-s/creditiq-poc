import type {
  FileRecord,
  IntegrityFacts,
  IntegrityFigure,
  IntegrityFinding,
  LogicalDocument,
} from "@/api/types";
import type { Tone } from "@/components/common/Panel";
import { t, tOr } from "@/config/terminology";

/** F-07A: what a file's integrity checks come to, as the engine says it (never worked out
 * here, so every screen shows the same thing). */
export type IntegrityState = NonNullable<FileRecord["integrity_status"]>["state"];

export function stateOf(file: FileRecord): IntegrityState {
  return file.integrity_status?.state ?? "not_checked";
}

export const STATE_TONE: Record<IntegrityState, Tone> = {
  passed: "positive",
  review_recommended: "flag",
  suspicious: "critical",
  suspicious_high: "critical",
  incomplete: "flag",
  failed: "flag",
  not_checked: "muted",
  not_applicable: "muted",
};

/** True when the file has an integrity status worth showing. */
export function hasIntegrity(file: FileRecord) {
  return !["not_checked", "not_applicable"].includes(stateOf(file));
}

/** States that open the file's checks by default, so they are not missed. */
export function integrityStandsOut(file: FileRecord) {
  return ["suspicious", "suspicious_high", "review_recommended", "incomplete", "failed"].includes(
    stateOf(file),
  );
}

/** One check's result, as a reader is told it. */
export type CheckKind =
  "passed" | "suspicious" | "informational" | "not_applicable" | "not_run" | "failed";

export function checkKind(f: IntegrityFinding): CheckKind {
  if (f.method?.["execution_failed"] === "true") return "failed";
  if (f.method?.["not_configured"] === "true") return "not_run";
  if (f.status === "warning" || f.status === "review_required")
    return f.context ? "informational" : "suspicious";
  if (f.status === "pass") return "passed";
  return "not_applicable";
}

export const KIND_TONE: Record<CheckKind, string> = {
  passed: "text-positive",
  suspicious: "text-destructive",
  informational: "text-flag-foreground",
  not_applicable: "text-muted-foreground",
  not_run: "text-muted-foreground",
  failed: "text-flag-foreground",
};

/** Checks whose evidence has a place on a page: a recovered figure is printed where it
 * now stands, and what a later save painted is drawn where the page draws it. Every
 * other check's evidence is in the file's own records — revisions, identifiers,
 * metadata — and has no place on a page. */
export const PRINTED_ON_PAGE = new Set(["PDF_PRIOR_VALUE_RECOVERABLE", "REVISIONS_TOUCH_CONTENT"]);

/** One line of what the file says about itself, with the key a check names in `reads`. */
export type FactRow = {
  key: string;
  group: FactGroup;
  label: string;
  value: string;
  /** How the file itself writes it, shown beneath the value (a raw PDF date). */
  note?: string;
};
export type FactGroup = "file" | "info" | "xmp" | "id" | "revisions" | "fonts";

const INFO_ORDER = [
  "Producer",
  "Creator",
  "CreationDate",
  "ModDate",
  "Title",
  "Author",
  "Subject",
  "Keywords",
];
/** The information-dictionary entries the checks read: shown even when the file leaves them out. */
const INFO_ALWAYS = ["Producer", "Creator", "CreationDate", "ModDate"];
const XMP_ORDER = ["producer", "creator_tool", "create_date", "modify_date", "metadata_date"];

const n = (v: number) => v.toLocaleString("en-IN");
const when = (iso?: string) => (iso ? humanTime(iso) : undefined);

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ZONES: Record<string, string> = { "+05:30": "IST", Z: "UTC", "+00:00": "UTC" };
const ISO_TIME =
  /(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?/g;

/** One timestamp as a person reads it, in the time zone the file wrote it in:
 * "31 Jul 2026, 5:45:35 PM (+05:30 IST)". Not converted to the viewer's zone —
 * the file's own clock is the evidence. */
export function humanTime(iso: string): string {
  return iso.replace(ISO_TIME, (_m, y, mo, d, h, mi, s, z) => {
    const hour = Number(h);
    const clock = `${hour % 12 || 12}:${mi}${s ? `:${s}` : ""} ${hour < 12 ? "AM" : "PM"}`;
    const zone = z
      ? z === "Z"
        ? "UTC"
        : z.length === 5
          ? `${z.slice(0, 3)}:${z.slice(3)}`
          : z
      : "";
    const named =
      ZONES[zone] === "UTC" ? "UTC" : zone && ZONES[zone] ? `${zone} ${ZONES[zone]}` : zone;
    return `${Number(d)} ${MONTHS[Number(mo) - 1]} ${y}, ${clock}${named ? ` (${named})` : ""}`;
  });
}

/** A time this system recorded (not a file's own), in the reader's local time:
 * "30 Oct 2026, 12:34:31 pm". */
export function localTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "medium" });
}

/** Any text with every ISO timestamp in it made readable. */
export const humanTimes = (text: string) => humanTime(text);

function pageSize([w, h]: [number, number]) {
  const named =
    Math.abs(w - 595) < 2 && Math.abs(h - 842) < 2
      ? " (A4)"
      : Math.abs(w - 612) < 2 && Math.abs(h - 792) < 2
        ? " (Letter)"
        : "";
  return `${Math.round(w)} × ${Math.round(h)} pt${named}`;
}

/** Objects a save wrote, drawn ones first: "page (3), image (263), … and 4 more". */
function objectList(objs: { number: number; kind: string }[], total: number) {
  const drawn = new Set(["page", "image", "form", "font", "annotation"]);
  const shown = [...objs]
    .sort((a, b) => Number(drawn.has(b.kind)) - Number(drawn.has(a.kind)))
    .slice(0, 12)
    .map((o) =>
      t("fileIntegrity.facts.object", {
        kind: tOr(`fileIntegrity.facts.kind.${o.kind}`, o.kind),
        n: o.number,
      }),
    );
  const rest = total - shown.length;
  return rest > 0
    ? `${shown.join(", ")} ${t("fileIntegrity.facts.more", { n: rest })}`
    : shown.join(", ");
}

/** True when a box is the whole page: the evidence is the page itself, not a spot on it. */
export function isWholePage(rect: readonly number[] | null | undefined) {
  if (!rect || rect.length < 4) return false;
  const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = rect;
  return x0 <= 0 && y0 <= 0 && x1 >= 1 && y1 >= 1;
}

/** Every record the integrity checks read, as labelled lines in reading order. */
export function factRows(facts: IntegrityFacts): FactRow[] {
  const rows: FactRow[] = [];
  const add = (key: string, group: FactGroup, label: string, value: string) =>
    rows.push({ key, group, label, value });
  const none = t("fileIntegrity.facts.notStated");

  add("size", "file", t("fileIntegrity.facts.size"), `${n(facts.size_bytes)} bytes`);
  add("pdf_version", "file", t("fileIntegrity.facts.pdfVersion"), facts.pdf_version ?? none);
  add(
    "header_offset",
    "file",
    t("fileIntegrity.facts.headerOffset"),
    facts.header_offset
      ? t("fileIntegrity.facts.headerWrapped", { n: n(facts.header_offset ?? 0) })
      : t("fileIntegrity.facts.headerAt0"),
  );
  if (facts.pages != null) add("pages", "file", t("fileIntegrity.facts.pages"), n(facts.pages));
  if (facts.page_sizes?.length)
    add(
      "pages.size",
      "file",
      t("fileIntegrity.facts.pageSizes"),
      facts.page_sizes.map((s) => pageSize(s as [number, number])).join(" · "),
    );

  const info = facts.info ?? {};
  const keys = [...INFO_ORDER, ...Object.keys(info).filter((k) => !INFO_ORDER.includes(k))];
  for (const k of keys) {
    if (!(k in info) && !INFO_ALWAYS.includes(k)) continue;
    const raw = info[k];
    const parsed = when(facts.info_dates?.[k]);
    const value = raw === undefined ? none : (parsed ?? raw);
    add(`info.${k}`, "info", tOr(`fileIntegrity.facts.info.${k}`, k), value);
    if (parsed && raw) {
      const row = rows[rows.length - 1];
      if (row) row.note = raw;
    }
  }

  if (!facts.has_xmp)
    add("xmp", "xmp", t("fileIntegrity.facts.xmp"), t("fileIntegrity.facts.noXmp"));
  else
    for (const k of XMP_ORDER)
      add(`xmp.${k}`, "xmp", tOr(`fileIntegrity.facts.xmpKey.${k}`, k), facts.xmp?.[k] ?? none);

  if (facts.id_original == null && facts.id_current == null)
    add("id", "id", t("fileIntegrity.facts.id"), t("fileIntegrity.facts.noId"));
  else {
    add("id.original", "id", t("fileIntegrity.facts.idOriginal"), facts.id_original ?? none);
    add("id.current", "id", t("fileIntegrity.facts.idCurrent"), facts.id_current ?? none);
  }

  for (const r of facts.revisions ?? []) {
    add(
      "revisions",
      "revisions",
      t("fileIntegrity.facts.revision", { n: r.index + 1 }),
      t("fileIntegrity.facts.revisionValue", {
        start: n(r.start),
        end: n(r.end),
        length: n(r.length),
      }),
    );
    if (r.replaced?.length)
      add(
        "revisions",
        "revisions",
        t("fileIntegrity.facts.revisionReplaced", { n: r.index + 1 }),
        objectList(r.replaced, r.replaced_count ?? r.replaced.length),
      );
    if (r.added?.length)
      add(
        "revisions",
        "revisions",
        t("fileIntegrity.facts.revisionAdded", { n: r.index + 1 }),
        objectList(r.added, r.added_count ?? r.added.length),
      );
  }
  add("signatures", "revisions", t("fileIntegrity.facts.signatures"), n(facts.signatures ?? 0));
  add(
    "superseded",
    "revisions",
    t("fileIntegrity.facts.superseded"),
    n(facts.superseded_objects ?? 0),
  );
  for (const r of facts.recovered ?? [])
    add(
      "recovered",
      "revisions",
      t("fileIntegrity.facts.recovered"),
      t("fileIntegrity.facts.recoveredValue", { was: r.was, now: r.now }),
    );

  add(
    "fonts",
    "fonts",
    t("fileIntegrity.facts.fonts"),
    facts.fonts?.length ? facts.fonts.join(", ") : t("fileIntegrity.facts.noFonts"),
  );
  return rows;
}

/** Whether a line of the facts is one a check read: its key, a key under it, or the
 * single "no XMP" / "no identifier" line standing in for the entries it would hold. */
export function factRead(rowKey: string, reads: readonly string[]) {
  return reads.some(
    (k) =>
      rowKey === k ||
      rowKey.startsWith(`${k}.`) ||
      (rowKey === "xmp" && k.startsWith("xmp.")) ||
      (rowKey === "id" && k === "id"),
  );
}

export type IntegrityStatus = IntegrityFinding["status"];

export const STATUS_TONE: Record<IntegrityStatus, string> = {
  pass: "text-positive",
  warning: "text-flag",
  review_required: "text-critical",
  not_applicable: "text-muted-foreground",
  unable_to_determine: "text-muted-foreground",
};

/** A context-only observation (how the file was made) is a note for a reader:
 * it never counts as a signal, so it is never shown as one. */
export function isNote(f: IntegrityFinding) {
  return f.context && (f.status === "warning" || f.status === "review_required");
}

/** A finding counts as a signal when it stands out and is not context only. */
export function standsOut(f: IntegrityFinding) {
  return (f.status === "warning" || f.status === "review_required") && !f.context;
}

export type Origin = "digital" | "scanned" | "mixed";

/** Digital or scanned, from how each page was read: its own text layer, or a
 * picture read by OCR. A spreadsheet's cells count as its own text. */
export function originOf(documents: LogicalDocument[]) {
  const pages = new Map<number, string>();
  for (const d of documents) for (const p of d.pages ?? []) pages.set(p.n, p.route);
  const scanned = [...pages.values()].filter((r) => r === "ocr").length;
  const digital = pages.size - scanned;
  if (!pages.size) return null;
  const kind: Origin = scanned === 0 ? "digital" : digital === 0 ? "scanned" : "mixed";
  return { kind, digital, scanned };
}

export type MadeAs = "digital" | "scanned" | "mixed" | "image";

/** Digital or scanned, in one word: pages with their own text, pictures of pages
 * (however the pictures were made), or both; an image upload is a scanned image.
 * From the integrity stage's reading of the pages, or else how each was read. */
export function madeAsOf(file: FileRecord, documents: LogicalDocument[] = []) {
  const made = file.integrity_facts?.made_as;
  const read = made
    ? { kind: made.kind, text: made.text_pages, pictures: made.picture_pages }
    : (() => {
        const o = originOf(documents);
        return o && { kind: o.kind, text: o.digital, pictures: o.scanned };
      })();
  if (!read) return null;
  const image = (file.content_type ?? "").startsWith("image/");
  const kind: MadeAs =
    read.kind === "digital"
      ? "digital"
      : read.kind === "mixed"
        ? "mixed"
        : image
          ? "image"
          : "scanned";
  return { kind, text: read.text, pictures: read.pictures };
}

/** A place on a page an integrity check points at. */
export type Mark = {
  key: string;
  finding: IntegrityFinding;
  page: number;
  rect: [number, number, number, number];
  observed: string;
  threshold: string;
  tone: "critical" | "flag" | "muted";
};

/** Every place on a page a check points at, keyed `${code}-${index}`. A box the size of the
 * page is the page itself (a later save replaced it): it is said in words, not drawn. */
export function marksOf(found: IntegrityFinding[]): { marks: Mark[]; pagesReplaced: Set<number> } {
  const marks: Mark[] = [];
  const pagesReplaced = new Set<number>();
  for (const f of found)
    (f.evidence ?? []).forEach((e, i) => {
      if (!e.rect) return;
      if (isWholePage(e.rect)) {
        pagesReplaced.add(e.page);
        return;
      }
      marks.push({
        key: `${f.code}-${i}`,
        finding: f,
        page: e.page,
        rect: e.rect as [number, number, number, number],
        observed: e.observed,
        threshold: e.threshold,
        // Red only for what counts as evidence; amber for an observation; grey otherwise.
        tone: standsOut(f) ? "critical" : isNote(f) ? "flag" : "muted",
      });
    });
  return { marks, pagesReplaced };
}

/** How the rest of a figure's column is set: the typeface and size most of its figures
 * share, how many there are, and whether this one is set apart from them. */
export function columnOf(figure: IntegrityFigure, figures: readonly IntegrityFigure[]) {
  if (figure.column == null) return null;
  const members = figures.filter((f) => f.page === figure.page && f.column === figure.column);
  const styles = members.map((f) => `${f.font}|${f.size}`);
  const counts = new Map<string, number>();
  for (const s of styles) counts.set(s, (counts.get(s) ?? 0) + 1);
  const [common = ""] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? [];
  const [font = "", size = "0"] = common.split("|");
  return {
    count: members.length,
    font,
    size: Number(size),
    apart: `${figure.font}|${figure.size}` !== common && members.length > 1,
  };
}
