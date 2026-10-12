import { CheckCircle2, ChevronRight, MinusCircle } from "lucide-react";
import type { Finding, XvItem } from "@/api/types";
import { t } from "@/config/terminology";
import { checkElementId, comparesText } from "@/domain/crossVerification";
import { checkRow, subsectionTitle } from "./styles";

/** "<rule> · <what it compares> · <scope>" — the line every passed or inapplicable check
 * starts with. */
function Lead({ finding }: { finding: Finding }) {
  return (
    <>
      <span className="font-mono text-[11.5px] text-muted-foreground">{finding.rule_id}</span>
      {" · "}
      <span className="text-foreground">{comparesText(finding)}</span>
      {finding.scope && (
        <>
          {" · "}
          {finding.scope}
        </>
      )}
    </>
  );
}

/** An area's checks that passed, closed until asked for, each with what the engine found (the
 * variance and the tolerance it was within, where it measured one). The checks that did not apply
 * follow, each with why. The counts are the engine's. A key figure on the overview opens the list
 * at its row (the row's element id). */
export function PassedList({
  passed,
  notApplicable,
  counts,
}: {
  passed: XvItem[];
  notApplicable: XvItem[];
  counts: { passed: number; notApplicable: number };
}) {
  if (passed.length + notApplicable.length === 0) return null;
  return (
    <details className="group rounded border border-border bg-surface" data-testid="xv-passed">
      <summary className="flex cursor-pointer select-none list-none flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2.5 [&::-webkit-details-marker]:hidden">
        <span className={`flex items-center gap-1.5 ${subsectionTitle}`}>
          <ChevronRight
            className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90"
            aria-hidden
          />
          {/* An area where nothing passed and something did not apply leads with the latter. */}
          {passed.length > 0
            ? t("crossVerification.passed.title", { n: counts.passed })
            : t("crossVerification.passed.notApplicableCount", { n: counts.notApplicable })}
        </span>
        {passed.length > 0 && counts.notApplicable > 0 && (
          <span className="text-[11.5px] text-muted-foreground">
            {t("crossVerification.passed.notApplicableCount", { n: counts.notApplicable })}
          </span>
        )}
      </summary>
      {passed.length > 0 && (
        <ul className="divide-y divide-border border-t border-border">
          {passed.map(({ finding }) => (
            <li
              key={finding.id}
              id={checkElementId(finding.id)}
              tabIndex={-1}
              className={`flex items-start gap-2 px-4 py-1.5 text-[12.5px] ${checkRow}`}
              data-testid="xv-passed-row"
              data-rule={finding.rule_id}
            >
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" aria-hidden />
              <span className="min-w-0 break-words">
                <Lead finding={finding} />
                {finding.explanation && (
                  <span className="text-muted-foreground">
                    {" · "}
                    {finding.explanation}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {notApplicable.length > 0 && (
        <div className="border-t border-border">
          {passed.length > 0 && (
            <p className="field-label px-4 pb-1 pt-2.5">
              {t("crossVerification.passed.notApplicable")}
            </p>
          )}
          <ul className="divide-y divide-border">
            {notApplicable.map(({ finding }) => (
              <li
                key={finding.id}
                id={checkElementId(finding.id)}
                tabIndex={-1}
                className={`flex items-start gap-2 px-4 py-1.5 text-[12.5px] ${checkRow}`}
                data-testid="xv-not-applicable-row"
                data-rule={finding.rule_id}
              >
                <MinusCircle
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <span className="min-w-0 break-words">
                  <Lead finding={finding} />
                  {finding.explanation && (
                    <span className="text-muted-foreground">
                      {" · "}
                      {finding.explanation}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </details>
  );
}
