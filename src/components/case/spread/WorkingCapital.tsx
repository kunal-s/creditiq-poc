import { Eye } from "lucide-react";
import type { Spread } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";

/** The working-capital assessment (F-22.2), as the engine worked it out: the method and why it
 * applies, each step with its basis and the page its figure was read from, and the eligible bank
 * finance against the amount requested. */
export function WorkingCapital({ caseId, spread }: { caseId: string; spread: Spread }) {
  const viewer = useDocViewer();
  const wc = spread.working_capital;
  if (wc.method === "not_applicable") return null;
  const missing = wc.missing ?? [];
  return (
    <section
      className="min-w-0 rounded border border-border bg-surface"
      data-testid="working-capital"
    >
      <header className="px-4 pb-3 pt-3.5">
        <h3 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t("outputs.spread.wcTitle")}
        </h3>
        <p className="mt-0.5 text-[12px] text-muted-foreground">{wc.reason}</p>
      </header>
      {missing.length > 0 ? (
        <p className="border-t border-border px-4 py-3 text-[12.5px] text-flag-foreground">
          {t("outputs.spread.wcMissing", { inputs: missing.join(", ") })}
        </p>
      ) : (
        <>
          <div className="relative overflow-x-auto border-t border-border">
            <table className="w-full min-w-[480px] text-[13px]">
              <tbody className="divide-y divide-border">
                {(wc.steps ?? []).map((step) => {
                  const e = step.evidence?.[0];
                  return (
                    <tr key={step.label} data-testid="wc-step">
                      <th scope="row" className="px-4 py-2 text-left font-medium text-foreground">
                        {step.label}
                      </th>
                      <td className="tabular whitespace-nowrap px-4 py-2 text-right font-semibold">
                        {step.value === null || step.value === undefined
                          ? "—"
                          : step.unit === "%"
                            ? `${step.value}%`
                            : formatInr(step.value)}
                      </td>
                      <td className="px-4 py-2 text-[12px] text-muted-foreground">{step.basis}</td>
                      <td className="w-8 px-2 py-2 text-right">
                        {e && (
                          <button
                            type="button"
                            onClick={() =>
                              viewer.open({
                                caseId,
                                documentId: e.document_id,
                                page: e.page,
                                bbox: e.bbox ?? null,
                              })
                            }
                            title={t("crossVerification.evidence.openPage", { page: e.page })}
                            aria-label={t("crossVerification.evidence.openPage", { page: e.page })}
                            className="inline-flex items-center rounded border border-border p-1 text-primary hover:bg-muted"
                          >
                            <Eye className="h-3.5 w-3.5" aria-hidden />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p
            className="border-t border-border px-4 py-2.5 text-[13px] font-medium text-foreground"
            data-testid="wc-verdict"
          >
            {t("outputs.spread.wcVerdict", {
              eligible:
                wc.eligible === null || wc.eligible === undefined ? "—" : formatInr(wc.eligible),
              requested: formatInr(wc.requested),
            })}
          </p>
        </>
      )}
    </section>
  );
}
