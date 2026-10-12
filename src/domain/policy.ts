import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "@/api/client";
import type {
  ApprovingAuthority,
  AuthorityRef,
  AuthorityStep,
  NormFamily,
  NormResult,
  PolicyAssessment,
  PolicyCounts,
  PolicyGroup,
} from "@/api/types";
import { t, tOr } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { joinList, scrollBehavior } from "@/domain/crossVerification";

// The Policy checks tab (F-20, F-21): the engine's assessment of every norm, grouped by family
// with its counts, where each family stands and the norms to show first; and the approving
// authority the case needs. The page shows them as given and never recounts.

/** Every policy norm for the case, with its outcome, the counts and the families (F-20). */
export function usePolicy(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "policy"],
    queryFn: () => api.casePolicy(caseId),
  });
}

/** The authority the case needs under the published matrix (F-21). A 503 means the matrix is
 * not published; the norms still show beside it. */
export function useApprovingAuthority(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "approving-authority"],
    queryFn: () => api.caseApprovingAuthority(caseId),
  });
}

/** The approving authority answers 503 while no approval matrix is published. */
export function matrixNotPublished(error: unknown): boolean {
  return error instanceof ApiError && error.status === 503;
}

export const groupSectionId = (family: NormFamily) => `policy-group-${family}`;
export const groupHeadingId = (family: NormFamily) => `policy-group-${family}-title`;
export const AUTHORITY_SECTION_ID = "policy-authority";
export const AUTHORITY_HEADING_ID = "policy-authority-title";
/** A norm's row in its family's section: a key figure, or a norm id in an authority step,
 * scrolls to it and focuses it. */
export const normElementId = (normId: string) => `policy-norm-${normId}`;

/** Scroll to a section of the page and focus its heading (a card on the overview). */
export function openSection(sectionId: string, headingId: string) {
  document
    .getElementById(sectionId)
    ?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
  document.getElementById(headingId)?.focus({ preventScroll: true });
}

/** Scroll to a norm's row and focus it, marked as the row opened until the reader moves on (a key
 * figure on the overview, or a norm id in an authority step). */
export function openNorm(normId: string) {
  const row = document.getElementById(normElementId(normId));
  if (!row) return;
  row.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
  row.setAttribute("data-target", "true");
  row.addEventListener("blur", () => row.removeAttribute("data-target"), { once: true });
  row.focus({ preventScroll: true });
}

/** The families as the engine sent them, in its order. */
export function groupsOf(policy: PolicyAssessment): PolicyGroup[] {
  return policy.groups ?? [];
}

/** A family's norms, in the engine's order. */
export function familyNorms(policy: PolicyAssessment, family: NormFamily): NormResult[] {
  return policy.norms.filter((n) => n.family === family);
}

/** The norms the engine picked for a family's card, in its order. */
export function groupHighlights(policy: PolicyAssessment, group: PolicyGroup): NormResult[] {
  return (group.highlights ?? [])
    .map((id) => policy.norms.find((n) => n.id === id))
    .filter((n): n is NormResult => n !== undefined);
}

/** "2 deviations", "1 cannot be evaluated", "9 passed", "1 not applicable": the parts of a count
 * worth saying, in that order. `deviations: false` leaves the deviations out (a card shows them
 * apart); `passed: true` keeps the passed count even when it is nought. */
export function countParts(counts: PolicyCounts, { deviations = true, passed = false } = {}) {
  const parts: string[] = [];
  if (deviations && counts.deviations > 0)
    parts.push(
      counts.deviations === 1
        ? t("policy.count.deviationOne")
        : t("policy.count.deviationMany", { n: counts.deviations }),
    );
  if (counts.cannot_evaluate > 0)
    parts.push(t("policy.count.cannotEvaluate", { n: counts.cannot_evaluate }));
  if (passed || counts.passed > 0) parts.push(t("policy.count.passed", { n: counts.passed }));
  if (counts.not_applicable > 0)
    parts.push(t("policy.count.notApplicable", { n: counts.not_applicable }));
  return parts;
}

/** A value in the norm's unit: "1.59x", "60.5%", "90 days", "INR 4.20 cr", "rank 5". */
export function amount(value: number | null | undefined, unit: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  switch (unit) {
    case "x":
      return `${value.toFixed(2)}x`;
    case "%":
      return `${value.toFixed(1)}%`;
    case "days": {
      const n = Math.round(value);
      return n === 1 ? t("policy.unit.dayOne") : t("policy.unit.days", { n });
    }
    case "years": {
      // Truncated as the engine writes it, never rounded up to a threshold: 2.99 years is 2.9.
      const n = Math.floor(value * 10 + 1e-9) / 10;
      return n === 1 ? t("policy.unit.yearOne") : t("policy.unit.years", { n });
    }
    case "inr":
      return formatInr(value);
    case "rank":
      return t("policy.rank", { n: value });
    default:
      return String(value);
  }
}

/** An input as a reader expects it: rupees, years, a rank or a count. */
export function inputValue(name: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (name === "vintage_years" || name === "audited_years") return amount(value, "years");
  if (name === "bureau_rank") return amount(value, "rank");
  if (name === "blocking_items_open") return String(value);
  return formatInr(value);
}

export function inputLabel(norm: NormResult, name: string): string {
  return norm.inputs?.find((i) => i.name === name)?.label ?? tOr(`policy.input.${name}`, name);
}

/** The actual value as the engine words it. A deviation with no finite value reads
 * "Unbounded"; the reason line under the norm says why. */
export function actualText(norm: NormResult): string {
  if (norm.outcome === "cannot_evaluate" || norm.outcome === "not_applicable")
    return t(`policy.outcome.${norm.outcome}`);
  if (norm.actual === null || norm.actual === undefined)
    return norm.outcome === "deviation" ? t("policy.unbounded") : "—";
  return norm.actual_text ?? amount(norm.actual, norm.unit);
}

/** Why a norm could not be evaluated, briefly, for its key figure: the inputs not on file, or the
 * engine's reason. */
export function cannotEvaluateNote(norm: NormResult): string | null {
  const missing = norm.missing ?? [];
  if (missing.length > 0)
    return t("policy.card.missing", {
      inputs: joinList(missing.map((name) => inputLabel(norm, name))),
    });
  if (norm.reason)
    return t(`policy.card.reason.${norm.reason}`, {
      inputs: joinList((norm.reason_inputs ?? []).map((name) => inputLabel(norm, name))),
    });
  return null;
}

/** "Head Office Credit Committee (level 4)". */
export function authorityName(ref: AuthorityRef): string {
  return t("policy.authorityCard.named", { authority: ref.label, level: ref.level });
}

/** The authorities the amount bands call for, each once, in the matrix's order. */
export function amountAuthorities(authority: ApprovingAuthority): AuthorityRef[] {
  const seen = new Map<string, AuthorityRef>();
  for (const step of authority.steps)
    if (step.kind === "amount" && !seen.has(step.authority.key))
      seen.set(step.authority.key, step.authority);
  return [...seen.values()];
}

/** The deviation steps, in the matrix's order. */
export function deviationSteps(authority: ApprovingAuthority): AuthorityStep[] {
  return authority.steps.filter((step) => step.kind === "deviation");
}

/** A deviation step in a few words: "Financial norms +1 level", "Eligibility +1 level, at least
 * Regional Credit Head", with "capped" where the matrix ran out of authorities. */
export function deviationStepShort(step: AuthorityStep): string {
  const n = step.levels_above ?? 0;
  const parts: string[] = [];
  if (n > 0)
    parts.push(
      n === 1 ? t("policy.authorityCard.levelOne") : t("policy.authorityCard.levelMany", { n }),
    );
  if (step.at_least)
    parts.push(t("policy.authorityCard.atLeastStep", { authority: step.at_least.label }));
  if (step.capped) parts.push(t("policy.authorityCard.capped"));
  return t("policy.authorityCard.step", {
    category: step.category_label ?? step.category ?? "",
    effect: parts.join(", "),
  });
}

/** Whether the authority could rise once the norms not yet assessed are known. */
export function authorityRises(authority: ApprovingAuthority): boolean {
  return Boolean(
    authority.required &&
    authority.could_rise_to &&
    authority.could_rise_to.key !== authority.required.key,
  );
}
