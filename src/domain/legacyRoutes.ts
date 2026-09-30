// Earlier routes (the prototype's two case workspaces) and where they now
// live (docs/functional-requirements.md §6). Kept until the PoC ends so
// saved links keep working.

export type Target = { to: string; hash?: string; search?: Record<string, string> };

const APPRAISAL: Record<string, Target> = {
  upload: { to: "documents" },
  identity: { to: "extraction", hash: "identity" },
  data: { to: "extraction", hash: "fields" },
  spread: { to: "outputs", search: { view: "spread" } },
  draft: { to: "outputs", search: { view: "cam" } },
  "cross-verification": { to: "cross-verification" },
  policy: { to: "policy" },
  comparison: { to: "comparison" },
};

const DOCREADY: Record<string, Target> = {
  checklist: { to: "completeness", hash: "checklist" },
  readiness: { to: "completeness", hash: "readiness" },
  collection: { to: "completeness", hash: "queries" },
  validation: { to: "documents" },
};

/** Where an earlier `/appraisals/<id>/<step>` or `/docready/<splat>` now lives. */
export function legacyTarget(workspace: "appraisals" | "docready", splat: string): Target {
  const [id, step] = splat.split("/").filter(Boolean);
  if (!id) return { to: "/" };
  if (workspace === "appraisals" && id === "new" && !step) return { to: "/appraisals/new" };
  const base = `/appraisals/${encodeURIComponent(decodeURIComponent(id))}`;
  const known = step ? (workspace === "appraisals" ? APPRAISAL : DOCREADY)[step] : undefined;
  if (!known) return { to: base };
  return { ...known, to: `${base}/${known.to}` };
}
