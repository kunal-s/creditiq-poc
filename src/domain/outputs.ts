import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/api/client";
import type { Evidence, OutputFormat, OutputKind, OutputSource } from "@/api/types";
import { t } from "@/config/terminology";
import { errorKind, refusal } from "@/domain/errors";

// The draft CAM and the PD note as files (F-23.5, F-24.3): Word, for credit to complete, and PDF,
// composed by the engine from the same content as the screen. A plain link cannot carry the
// session token, so the file is fetched with it and handed to the browser to save.

export const OUTPUT_FORMATS: OutputFormat[] = ["docx", "pdf"];

const FILE_STEM: Record<OutputKind, string> = { cam: "CAM-draft", pd_note: "PD-note" };

/** The name the engine gives the file, for when the browser does not let the page read it. */
export function outputFileName(output: OutputKind, caseId: string, format: OutputFormat): string {
  return `${FILE_STEM[output]}-${caseId}.${format}`;
}

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  // Released once the browser has had time to take the file.
  window.setTimeout(() => URL.revokeObjectURL(url), 40_000);
}

/** Download the memo or the note in one format: pending while the engine composes it, a toast if
 * it cannot be had. */
export function useOutputDownload(caseId: string, output: OutputKind) {
  return useMutation({
    mutationFn: async (format: OutputFormat) => {
      const file =
        output === "cam" ? await api.camFile(caseId, format) : await api.pdNoteFile(caseId, format);
      save(file.blob, file.filename ?? outputFileName(output, caseId, format));
    },
    onError: (error) =>
      toast.error(t("outputs.download.failed"), {
        description: refusal(error) ?? t(`state.${errorKind(error)}.description`),
      }),
  });
}

/** Each cited document's source by its id, so that a citation on screen carries the number the
 * downloads print. */
export function sourcesById(sources: OutputSource[]): ReadonlyMap<string, OutputSource> {
  return new Map(sources.map((s) => [s.document_id, s]));
}

/** Each page cited once, in the order cited. */
export function uniqueEvidence(evidence: Evidence[]): Evidence[] {
  return evidence.filter(
    (e, i) => evidence.findIndex((x) => x.document_id === e.document_id && x.page === e.page) === i,
  );
}

/** One source a statement cites: its pages, ascending, each with the first citation of it (and
 * so its region). */
export type SourcePages = { source: OutputSource; pages: number[]; evidence: Evidence[] };

/** The sources a statement cites, as the downloads mark them (engine/exports/layout.py): by
 * number, one entry per source with its pages; three or more sources in a row cited at the same
 * pages make one run, such as the monthly returns behind a year's GST figure ("13-23 p.1"). A
 * document the memo does not number is left in `unlisted`. */
export function citationRuns(
  evidence: Evidence[],
  sources: ReadonlyMap<string, OutputSource>,
): { runs: SourcePages[][]; unlisted: Evidence[] } {
  const bySource = new Map<number, SourcePages>();
  const unlisted: Evidence[] = [];
  for (const e of uniqueEvidence(evidence)) {
    const source = sources.get(e.document_id);
    if (!source) {
      unlisted.push(e);
      continue;
    }
    const cited = bySource.get(source.number) ?? { source, pages: [], evidence: [] };
    bySource.set(source.number, cited);
    cited.evidence.push(e);
  }
  const cited = [...bySource.values()]
    .sort((a, b) => a.source.number - b.source.number)
    .map((c) => {
      const evidence = [...c.evidence].sort((a, b) => a.page - b.page);
      return { ...c, evidence, pages: evidence.map((e) => e.page) };
    });
  const runs: SourcePages[][] = [];
  for (const c of cited) {
    const run = runs[runs.length - 1];
    const tail = run?.[run.length - 1];
    if (run && tail && c.source.number === tail.source.number + 1 && samePages(c, tail))
      run.push(c);
    else runs.push([c]);
  }
  // Two sources in a row stay apart, as the downloads print them.
  return { runs: runs.flatMap((run) => (run.length >= 3 ? [run] : run.map((c) => [c]))), unlisted };
}

function samePages(a: SourcePages, b: SourcePages): boolean {
  return a.pages.length === b.pages.length && a.pages.every((p, i) => p === b.pages[i]);
}

/** "4", "4-6", "1, 4-6": pages ascending, consecutive ones as a range. */
export function pageRuns(pages: number[]): string {
  const runs: [number, number][] = [];
  for (const p of [...new Set(pages)].sort((a, b) => a - b)) {
    const run = runs[runs.length - 1];
    if (run && p === run[1] + 1) run[1] = p;
    else runs.push([p, p]);
  }
  return runs.map(([a, b]) => (a === b ? String(a) : `${a}-${b}`)).join(", ");
}

const FIGURE = /^(?:INR -?[\d.,]+(?: (?:cr|lakh))?|-?[\d.,]+(?:x|%| days?)?|—)/;

/** A table figure split into its leading amount, kept on one line, and the words after it, which
 * may wrap: "INR 95.00 lakh" and "; outstanding INR 60.00 lakh". */
export function leadingFigure(text: string): [string, string] {
  const lead = FIGURE.exec(text)?.[0] ?? "";
  return [lead, text.slice(lead.length)];
}

const UNBROKEN =
  /\b(?:FY|AY) \d{4}-\d{2}\b|\bX[RV]-\d+-\d+\b|\b[A-Z]{2,3}-\d{2}\b|\bGSTR-\d[A-Z]?\b/g;

/** A statement's words in parts, those never to be broken at their hyphen or space marked: the
 * years (FY 2025-26, AY 2026-27), the board's and the run's references (XV-000021-03,
 * XR-000021-003), rule and norm ids (ID-06, DOC-01) and GSTR-3B. */
export function unbrokenParts(text: string): { text: string; unbroken: boolean }[] {
  const parts: { text: string; unbroken: boolean }[] = [];
  let at = 0;
  for (const m of text.matchAll(UNBROKEN)) {
    const index = m.index ?? 0;
    if (index > at) parts.push({ text: text.slice(at, index), unbroken: false });
    parts.push({ text: m[0], unbroken: true });
    at = index + m[0].length;
  }
  if (at < text.length) parts.push({ text: text.slice(at), unbroken: false });
  return parts;
}

/** The configuration version as people know it, "Version 15 (published 13 Oct 2026)"; from an
 * engine that sends no label, the version's first characters. */
export function configLabel(output: { config_label?: string; config_version: string }): string {
  return output.config_label || output.config_version.slice(0, 8);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** The date the case's data is read as of, as the memo and its files print it: "9 Oct 2026" (a
 * calendar day, never shifted by the time zone; engine/util.py display_date). */
export function formatDay(day: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(day);
  const month = m ? MONTHS[Number(m[2]) - 1] : undefined;
  if (!m || !month) return day;
  return `${Number(m[3])} ${month} ${m[1]}`;
}

/** The anchor of a memo section on the CAM view, which the note's observations open. */
export const camSectionAnchor = (sectionId: string) => `cam-section-${sectionId}`;

/** The memo section that states an observation the note asks about (F-24): the id before the ":"
 * of the observation's key ("financials:fall"); null for a key that names none. */
export function observationSection(ref: string): string | null {
  const at = ref.indexOf(":");
  return at > 0 ? ref.slice(0, at) : null;
}
