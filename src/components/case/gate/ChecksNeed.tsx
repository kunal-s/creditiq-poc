import { Link } from "@tanstack/react-router";
import { CircleDashed } from "lucide-react";
import { t } from "@/config/terminology";
import { useCrossVerification } from "@/domain/crossVerification";
import { caseCreated, useCaseProgress } from "@/domain/progress";
import { useCan } from "@/domain/session";

// On Document readiness, once the case is created: the cross-checks that could not run for want of a
// document, and what each needs, so the documents to ask for are named where the documents are
// managed rather than found later on Cross-verification. Each request is the engine's own words.
//
// Test ids: checks-need (data-count), checks-need-item.

export function ChecksNeed({ caseId }: { caseId: string }) {
  const canChecks = useCan("finding.read");
  const created = caseCreated(useCaseProgress(caseId).data);
  const board = useCrossVerification(caseId).data;
  if (!canChecks || !created || !board) return null;
  const needs = board.items
    .filter((i) => i.finding.outcome === "incomplete" && i.finding.request)
    .map((i) => ({ id: i.finding.id, title: i.finding.title, request: i.finding.request! }));
  if (needs.length === 0) return null;
  // The same documents often complete several checks: say each once.
  const requests = [...new Set(needs.map((n) => n.request))];
  return (
    <section
      className="rounded border border-border bg-surface px-4 py-3"
      data-testid="checks-need"
      data-count={needs.length}
    >
      <p className="flex items-start gap-2 text-[13px] font-medium text-foreground">
        <CircleDashed className="mt-0.5 size-4 shrink-0 text-flag-foreground" aria-hidden />
        {t("checksNeed.title", { n: needs.length })}
      </p>
      <ul className="mt-1.5 space-y-1 pl-6 text-[12.5px] text-muted-foreground">
        {requests.map((r) => (
          <li key={r} data-testid="checks-need-item">
            {r}
          </li>
        ))}
      </ul>
      <Link
        to="/appraisals/$caseId/cross-verification"
        params={{ caseId }}
        className="mt-2 inline-block pl-6 text-[12px] font-medium text-primary hover:underline"
      >
        {t("checksNeed.open")} →
      </Link>
    </section>
  );
}
