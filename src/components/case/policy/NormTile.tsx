import { Link } from "@tanstack/react-router";
import { X } from "lucide-react";
import type { FocusEvent } from "react";
import type { NormInput, NormResult } from "@/api/types";
import { checkRow } from "@/components/case/xv/styles";
import { Chip } from "@/components/common/Panel";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { actualText, inputLabel, inputValue, normElementId } from "@/domain/policy";
import { cn } from "@/lib/utils";
import { NormWorking } from "./NormWorking";
import { OUTCOME_TEXT } from "./styles";

/** A ratio's band against its configured values (the engine's): green within the norm, amber past
 * it but within the marginal value, red past that. */
export const BAND_TEXT = {
  within: "text-positive",
  marginal: "text-flag-foreground",
  outside: "text-destructive",
} as const;

export const CHIP: Record<string, { tone: string; dot: string }> = {
  within: { tone: "border-positive/30 bg-positive-soft text-positive", dot: "bg-positive" },
  marginal: { tone: "border-flag/40 bg-flag-soft text-flag-foreground", dot: "bg-flag-foreground" },
  outside: {
    tone: "border-destructive/30 bg-critical-soft text-destructive",
    dot: "bg-destructive",
  },
  cannot_evaluate: { tone: "border-flag/40 bg-flag-soft text-flag-foreground", dot: "bg-flag" },
  not_applicable: {
    tone: "border-border bg-surface-muted text-muted-foreground",
    dot: "bg-muted-foreground/60",
  },
};

/** Where a norm stands, in the tile's chip: a ratio by the band the engine placed it in; any other
 * norm within policy when it passed and outside it when it deviated. */
export function statusOf(norm: NormResult): {
  key: string;
  label: string;
  tone: string;
  dot: string;
} {
  const key =
    norm.band ??
    (norm.outcome === "pass" ? "within" : norm.outcome === "deviation" ? "outside" : norm.outcome);
  const label =
    key === "within" || key === "marginal" || key === "outside"
      ? t(`policy.band.${key}`)
      : t(`policy.outcome.${key}`);
  return { key, label, ...CHIP[key]! };
}

/** The actual value as two parts, so the figure reads large and its unit small: "1.79" "x",
 * "129" " days", "INR 4.80" " cr". A value without a leading figure stays whole. */
export function split(text: string): [string, string] {
  const m = text.match(/^(INR\s)?(-?[\d.,]+)(.*)$/);
  return m ? [`${m[1] ?? ""}${m[2]}`, m[3] ?? ""] : [text, ""];
}

/** One norm as a tile (F-20): its name, the actual value large in the colour of where it stands,
 * the chip that says so, and the norm it is held to; why it could not be evaluated, in a line.
 * Selecting the tile opens its figures and working below the family's tiles. A key figure on the
 * overview, a norm in an authority step or a ?norm= link focuses it, which opens it too. */
export function NormTile({
  norm,
  selected,
  onSelect,
  detailId,
}: {
  norm: NormResult;
  selected: boolean;
  /** Toggle the tile's detail (a click), or open it (a link focusing the tile). */
  onSelect: (open?: boolean) => void;
  detailId: string;
}) {
  const status = statusOf(norm);
  // A norm with no result reads a dash; the chip says why.
  const evaluated = norm.outcome === "pass" || norm.outcome === "deviation";
  const [figure, unit] = evaluated ? split(actualText(norm)) : ["—", ""];
  const tone = !evaluated
    ? "text-muted-foreground"
    : norm.band
      ? BAND_TEXT[norm.band]
      : OUTCOME_TEXT[norm.outcome];
  const reason = norm.reason
    ? t(`policy.reason.${norm.reason}`, {
        inputs: (norm.reason_inputs ?? []).map((name) => inputLabel(norm, name)).join(", "),
      })
    : null;
  const missing =
    (norm.missing ?? []).length > 0
      ? t("policy.missing", {
          inputs: (norm.missing ?? []).map((name) => inputLabel(norm, name)).join(", "),
        })
      : null;
  return (
    <li
      id={normElementId(norm.id)}
      tabIndex={-1}
      // A link focuses the tile itself, which opens it; a click on its button toggles it.
      onFocus={(e: FocusEvent<HTMLLIElement>) => {
        if (e.target === e.currentTarget) onSelect(true);
      }}
      className={cn("relative min-w-0", checkRow, selected ? "bg-info-soft" : "bg-surface")}
      data-testid="norm"
      data-norm={norm.id}
      data-outcome={norm.outcome}
      data-selected={selected ? "true" : "false"}
    >
      <button
        type="button"
        onClick={() => onSelect()}
        aria-expanded={selected}
        aria-controls={detailId}
        className="flex h-full w-full flex-col items-start px-4 py-3 text-left transition-colors hover:bg-foreground/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        data-testid="norm-select"
      >
        <span className="flex w-full items-start justify-between gap-2">
          <span className="text-[12.5px] leading-snug text-muted-foreground">{norm.label}</span>
          {norm.provisional && (
            <span className="shrink-0 text-[10.5px] text-muted-foreground/80">
              {t("policy.provisional")}
            </span>
          )}
        </span>
        <span className="sr-only">{t(`policy.outcome.${norm.outcome}`)}</span>
        <span
          className={cn("mt-2 tabular font-semibold leading-none", tone)}
          data-testid="norm-actual"
        >
          <span className="text-[24px]">{figure}</span>
          <span className="text-[13px]">{unit}</span>
        </span>
        <span
          className={cn(
            "mt-2.5 inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11.5px] font-medium",
            status.tone,
          )}
          data-testid={norm.band ? "norm-band" : "norm-status"}
          data-band={norm.band ?? undefined}
          data-status={status.key}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", status.dot)} aria-hidden />
          {status.label}
        </span>
        <span className="mt-2 text-[11.5px] leading-snug text-muted-foreground">
          {t("policy.tile.required", { required: norm.required })}
          {norm.marginal_text && (
            <>
              {" · "}
              <span data-testid="norm-marginal">
                {t("policy.marginalAt", { value: norm.marginal_text })}
              </span>
            </>
          )}
        </span>
        {reason && (
          <span
            className={cn(
              "mt-1 text-[11.5px] leading-snug",
              norm.outcome === "deviation" ? "text-destructive" : "text-flag-foreground",
            )}
            data-testid="norm-reason"
            data-reason={norm.reason}
          >
            {reason}
          </span>
        )}
        {missing && (
          <span
            className="mt-1 text-[11.5px] leading-snug text-flag-foreground"
            data-testid="norm-missing"
          >
            {missing}
          </span>
        )}
      </button>
    </li>
  );
}

/** Where a figure with no document page comes from. */
function InputBasis({ caseId, input }: { caseId: string; input: NormInput }) {
  const basis = input.basis ?? "document";
  if (basis === "document") return null;
  if (basis === "checklist")
    return (
      <Link
        to="/appraisals/$caseId/completeness"
        params={{ caseId }}
        className="text-primary hover:underline"
        data-testid="norm-input-checklist"
        title={(input.refs ?? []).join(", ")}
      >
        {t("policy.basis.checklist")}
      </Link>
    );
  return (
    <span className="text-muted-foreground" data-testid="norm-input-basis" data-basis={basis}>
      ({t(`policy.basis.${basis}`)})
    </span>
  );
}

/** The selected tile's detail, under the family's tiles: the deviation's category, the figures the
 * norm used, each opening the page it was read from, and how it was decided. */
export function NormDetail({
  caseId,
  norm,
  id,
  onClose,
}: {
  caseId: string;
  norm: NormResult;
  id: string;
  onClose: () => void;
}) {
  const viewer = useDocViewer();
  const inputs = norm.outcome !== "not_applicable" ? (norm.inputs ?? []) : [];
  return (
    <div
      id={id}
      className="space-y-2.5 border-t border-border bg-surface px-4 py-3"
      data-testid="norm-detail"
      data-norm={norm.id}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] font-semibold text-foreground">
          {norm.label}
          {norm.outcome === "deviation" && <Chip tone="critical">{norm.category_label}</Chip>}
        </p>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex shrink-0 items-center gap-1 text-[11.5px] font-medium text-muted-foreground hover:text-foreground"
          data-testid="norm-detail-close"
        >
          <X className="h-3 w-3" aria-hidden /> {t("crossVerification.evidence.close")}
        </button>
      </div>
      {inputs.length > 0 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
          {inputs.map((input) => {
            const e = input.evidence?.[0];
            return (
              <li
                key={input.name}
                className="inline-flex min-w-0 flex-wrap items-center gap-1"
                data-testid="norm-input"
              >
                <span className="text-muted-foreground">{input.label}</span>
                {e ? (
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
                    className="tabular font-medium text-primary underline decoration-dotted underline-offset-2"
                  >
                    {inputValue(input.name, input.value)}
                  </button>
                ) : (
                  <span className="tabular font-medium">{inputValue(input.name, input.value)}</span>
                )}
                <InputBasis caseId={caseId} input={input} />
                {input.relies_on_manual && <Chip tone="flag">{t("crossCheck.manual")}</Chip>}
                {input.awaiting_review && (
                  <Chip tone="flag">
                    <span data-testid="norm-input-awaiting">{t("policy.awaitingReview")}</span>
                  </Chip>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <div data-testid="norm-details">
        <p className="field-label mb-1.5">{t("details.title")}</p>
        <NormWorking caseId={caseId} norm={norm} />
      </div>
    </div>
  );
}
