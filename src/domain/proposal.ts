import type { Meta, Span } from "@/api/types";

/** The branch id whose label matches the RM's own branch. */
export function branchFor(label: string | null | undefined, meta: Meta | undefined): string | null {
  if (!label || !meta) return null;
  const needle = label.trim().toLowerCase();
  return meta.branches.find((b) => b.label.toLowerCase() === needle)?.id ?? null;
}

/** A value's source when it was read from the message: "message:<start>-<end>". */
export function spanSource(span: Span | null | undefined): string | null {
  return span ? `message:${span.start}-${span.end}` : null;
}

/** The message span a source names, if it is one ("message:<start>-<end>"). */
export function spanOf(source: string | null | undefined): Span | null {
  const m = /^message:(\d+)-(\d+)$/.exec(source ?? "");
  return m ? { start: Number(m[1]), end: Number(m[2]) } : null;
}

export type Mark = {
  start: number;
  end: number;
  level: "stripped" | "found" | "candidate" | "selected";
};

/** Split the message into runs, each with the strongest mark covering it. */
export function markRuns(
  text: string,
  marks: Mark[],
): { text: string; start: number; level: Mark["level"] | null }[] {
  const rank = { stripped: 0, found: 1, candidate: 2, selected: 3 } as const;
  const bounds = new Set<number>([0, text.length]);
  for (const m of marks) {
    bounds.add(Math.max(0, Math.min(text.length, m.start)));
    bounds.add(Math.max(0, Math.min(text.length, m.end)));
  }
  const points = Array.from(bounds).sort((a, b) => a - b);
  const runs: { text: string; start: number; level: Mark["level"] | null }[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i]!;
    const end = points[i + 1]!;
    if (end <= start) continue;
    let level: Mark["level"] | null = null;
    for (const m of marks) {
      if (m.start <= start && m.end >= end && (!level || rank[m.level] > rank[level])) {
        level = m.level;
      }
    }
    runs.push({ text: text.slice(start, end), start, level });
  }
  return runs;
}
