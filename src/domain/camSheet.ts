import type {
  Cam,
  CamOverride,
  CamReview,
  CamSection,
  CamSummaryItem,
  Evidence,
} from "@/api/types";
import { t } from "@/config/terminology";

// The draft CAM as sheets (F-23): a sheet a section, in the memo's order, each a list of rows a grid
// draws as a spreadsheet. The rows are the memo's own blocks: its paragraphs (which a person may put
// in their words), its key facts as Field | Value | Source and its tables with their columns (whose
// figures a person may override, with a reason). Nothing here is kept apart from the memo: an edit is
// the engine's own record of words or of an override, so the sheet, the memo and the downloads agree.

/** The figure a table's cell is overridden by: its table (or section), its row and its column, as
 * the engine names it (engine/exports/xlsx.py figure_key). A fact's figure is its label. */
export function figureKey(owner: string, rowName: string, column: string): string {
  return [owner, rowName, column].map((p) => clean(p)).join(" · ");
}

/** The engine's record of a section's overrides, drawn as a table at its end (engine/cam_review.py). */
export const OVERRIDES_TITLE = "Figures overridden by the analyst";

function clean(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

/** The override in force for each figure: the last one made. */
export function latestOverrides(review: CamReview | undefined): Map<string, CamOverride> {
  const out = new Map<string, CamOverride>();
  for (const o of [...(review?.overrides ?? [])].sort((a, b) => a.at.localeCompare(b.at)))
    out.set(clean(o.figure), o);
  return out;
}

export type SheetCell = {
  text: string;
  citations: Evidence[];
  /** Set on a cell a person may change: the figure its override names. */
  figure?: string;
  /** The override in force for the cell. */
  override?: CamOverride;
  /** The value as the engine drafted it (before any override). */
  drafted: string;
  numeric?: boolean;
};

export type SheetRow =
  | { kind: "subheading"; text: string; part?: string }
  | { kind: "paragraph"; text: string; citations: Evidence[]; index: number }
  | { kind: "note"; text: string; role?: "rating" | "empty" }
  | { kind: "head"; cells: string[] }
  | { kind: "cells"; cells: SheetCell[]; zebra: boolean; label: boolean; facts?: boolean }
  | { kind: "summary"; item: CamSummaryItem; n: number }
  | { kind: "group"; text: string; summaryKind: CamSummaryItem["kind"]; count: number }
  | { kind: "prompt"; text: string }
  | { kind: "box" }
  | { kind: "gap" };

export type SheetKind = "section" | "summary" | "recommendation";

export type Sheet = {
  id: string;
  kind: SheetKind;
  number: number;
  title: string;
  purpose: string | null | undefined;
  review: CamReview;
  rows: SheetRow[];
  /** The grid's columns: the widest of its tables, and at least the three of its key facts. */
  columns: number;
  /** The sheet's paragraphs as they read now: what a person's words replace, one for one. */
  paragraphs: string[];
};

const MACHINE: CamReview = { state: "machine", paragraphs: [], overrides: [], requests: [] };

function cell(text: string, citations: Evidence[] = [], extra: Partial<SheetCell> = {}): SheetCell {
  return { text, citations, drafted: text, ...extra };
}

/** A value a person may change, showing the override in force where there is one. */
function figureCell(
  text: string,
  citations: Evidence[],
  figure: string,
  overrides: Map<string, CamOverride>,
  numeric = false,
): SheetCell {
  const override = overrides.get(clean(figure));
  return {
    text: override ? override.value : text,
    citations,
    figure,
    drafted: text,
    numeric,
    ...(override ? { override } : {}),
  };
}

function sectionSheet(s: CamSection): Sheet {
  const review = s.review ?? MACHINE;
  const overrides = latestOverrides(review);
  const parts = s.parts ?? [];
  const rows: SheetRow[] = [];
  const paragraphs: string[] = [];
  let part = 0;
  let columns = 3;
  for (const b of s.blocks ?? []) {
    if (b.kind === "paragraph" && b.paragraph) {
      rows.push({
        kind: "paragraph",
        text: b.paragraph.text,
        citations: b.paragraph.citations ?? [],
        index: paragraphs.length,
      });
      paragraphs.push(b.paragraph.text);
    } else if (b.kind === "subheading" && b.text) {
      // The subheadings are the parts' titles, in order: each is where a link to its part lands.
      const p = parts.length > 1 ? parts[part++] : undefined;
      rows.push({ kind: "subheading", text: b.text, ...(p ? { part: p.id } : {}) });
    } else if (b.kind === "note" && b.text) {
      rows.push({ kind: "note", text: b.text });
    } else if (b.kind === "facts" && (b.facts ?? []).length > 0) {
      rows.push({
        kind: "head",
        cells: [t("outputs.sheet.field"), t("outputs.sheet.value"), t("outputs.sheet.source")],
      });
      (b.facts ?? []).forEach((f, i) =>
        rows.push({
          kind: "cells",
          label: true,
          facts: true,
          zebra: i % 2 === 1,
          cells: [
            cell(f.label),
            figureCell(f.value.text, f.value.citations ?? [], f.label, overrides),
          ],
        }),
      );
      rows.push({ kind: "gap" });
    } else if (b.kind === "table" && b.table) {
      const tb = b.table;
      // The record of overrides is the engine's: shown, never itself overridden.
      const record = tb.title === OVERRIDES_TITLE;
      const owner = tb.title || s.title;
      if (tb.title) rows.push({ kind: "subheading", text: tb.title });
      columns = Math.max(columns, tb.columns.length);
      if (tb.rows.length > 0) {
        rows.push({ kind: "head", cells: tb.columns });
        tb.rows.forEach((row, n) => {
          const name = row[0]?.text ?? "";
          rows.push({
            kind: "cells",
            label: false,
            zebra: n % 2 === 1,
            cells: row.map((c, i) =>
              record
                ? cell(c.text, c.citations ?? [])
                : figureCell(
                    c.text,
                    c.citations ?? [],
                    figureKey(owner, name, tb.columns[i] ?? ""),
                    overrides,
                    (tb.numeric ?? []).includes(i),
                  ),
            ),
          });
        });
      }
      if (tb.note) rows.push({ kind: "note", text: tb.note });
      rows.push({ kind: "gap" });
    }
  }
  if (rows.length === 0 && s.empty) rows.push({ kind: "note", text: s.empty, role: "empty" });
  if (rows[rows.length - 1]?.kind === "gap") rows.pop();
  return {
    id: s.id,
    kind: "section",
    number: s.number,
    title: s.title,
    purpose: s.purpose,
    review,
    rows,
    columns,
    paragraphs,
  };
}

const SUMMARY_KINDS: CamSummaryItem["kind"][] = [
  "finding",
  "incomplete",
  "deviation",
  "unassessed",
  "query",
];

function paragraphRows(paragraphs: string[]): SheetRow[] {
  return paragraphs.map((text, index) => ({ kind: "paragraph", text, citations: [], index }));
}

/** The risk assessment: a person's words on the risks, the rating's note, then the register of
 * findings, checks not completed, deviations, norms not assessed and open queries. */
function summarySheet(m: Cam): Sheet {
  const review = m.summary_review ?? MACHINE;
  const paragraphs = review.paragraphs ?? [];
  const rows: SheetRow[] = paragraphRows(paragraphs);
  if (m.rating_note) rows.push({ kind: "note", text: m.rating_note, role: "rating" });
  for (const kind of SUMMARY_KINDS) {
    const items = m.summary.filter((i) => i.kind === kind);
    if (items.length === 0 && kind !== "finding") continue;
    rows.push({ kind: "group", text: "", summaryKind: kind, count: items.length });
    // The open queries under the query list's own groups.
    let group: string | null = null;
    items.forEach((item, i) => {
      const title = kind === "query" && item.group ? t(`queryGroup.${item.group}`) : null;
      if (title && title !== group) rows.push({ kind: "subheading", text: title });
      group = title;
      rows.push({ kind: "summary", item, n: i + 1 });
    });
  }
  return {
    id: "summary",
    kind: "summary",
    number: m.summary_number,
    title: m.summary_title,
    purpose: m.summary_purpose,
    review,
    rows,
    columns: 3,
    paragraphs,
  };
}

/** The recommendation, left to credit: its words once written, each heading credit completes with
 * room under it, and the sign-off. */
function recommendationSheet(m: Cam): Sheet {
  const review = m.recommendation_review ?? MACHINE;
  const paragraphs = (m.recommendation ?? "").split("\n\n").filter((p) => p.trim());
  const rows: SheetRow[] = paragraphRows(paragraphs);
  if (paragraphs.length === 0) rows.push({ kind: "paragraph", text: "", citations: [], index: 0 });
  for (const prompt of m.recommendation_prompts ?? []) {
    rows.push({ kind: "prompt", text: prompt }, { kind: "box" });
  }
  const signOff = m.sign_off ?? [];
  if (signOff.length > 0) {
    rows.push(
      { kind: "gap" },
      {
        kind: "head",
        cells: (["role", "name", "designation", "signature", "date"] as const).map((k) =>
          t(`outputs.cam.signOff.${k}`),
        ),
      },
    );
    signOff.forEach((s, n) =>
      rows.push({
        kind: "cells",
        label: true,
        zebra: n % 2 === 1,
        cells: [cell(s.role), cell(""), cell(""), cell(""), cell("")],
      }),
    );
  }
  return {
    id: "recommendation",
    kind: "recommendation",
    number: m.recommendation_number,
    title: m.recommendation_title,
    purpose: m.recommendation_purpose,
    review,
    rows,
    columns: signOff.length > 0 ? 5 : 3,
    paragraphs,
  };
}

/** The memo's sheets, in its order. */
export function camSheets(m: Cam): Sheet[] {
  return [...m.sections.map(sectionSheet), summarySheet(m), recommendationSheet(m)];
}

/** "A", "B", … "Z", "AA": a column's letter, as a spreadsheet heads it. */
export function columnLetter(index: number): string {
  let n = index + 1;
  let out = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    out = String.fromCharCode(65 + r) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

/** The paragraphs with one replaced (or, when emptied, taken out): what a person's words send. */
export function withParagraph(paragraphs: string[], index: number, text: string): string[] {
  const next = [...paragraphs];
  while (next.length <= index) next.push("");
  next[index] = text.trim();
  return next.filter((p) => p.trim());
}
