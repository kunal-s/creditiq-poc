import { Link } from "@tanstack/react-router";
import { ArrowRight, Check, ListPlus } from "lucide-react";
import type { XvItem } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { t } from "@/config/terminology";
import {
  awaitsReview,
  checkElementId,
  comparesText,
  useAddFindingQuery,
} from "@/domain/crossVerification";
import { refusal } from "@/domain/errors";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { ReviewValue } from "./ReviewValue";
import { checkRow, subsectionTitle } from "./styles";

/** An area's checks that could not run (`count`, as the engine counted them): why, and what would
 * complete each, which can go on the pre-login query list (F-14). A check waiting on a person's
 * review shows that instead. A refusal shows the engine's words where they are written for the
 * reader, else the designed error state. */
export function IncompleteList({
  caseId,
  items,
  count,
}: {
  caseId: string;
  items: XvItem[];
  count: number;
}) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-2" data-testid="xv-incomplete">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className={subsectionTitle}>{t("crossVerification.incomplete.title", { n: count })}</h3>
        <p className="text-[11.5px] text-muted-foreground">
          {t("crossVerification.incomplete.note")}
        </p>
      </div>
      <ul className="divide-y divide-border overflow-hidden rounded border border-border bg-surface">
        {items.map((item) => (
          <IncompleteRow key={item.finding.id} caseId={caseId} item={item} />
        ))}
      </ul>
    </div>
  );
}

function IncompleteRow({ caseId, item }: { caseId: string; item: XvItem }) {
  const f = item.finding;
  const canDecide = useCan("review.decide");
  const add = useAddFindingQuery(caseId);
  const waiting = awaitsReview(f);
  const awaiting =
    (f.columns ?? []).find((c) => c.awaiting_review) ?? f.sides.find((s) => s.awaiting_review);
  const missing = f.missing ?? [];
  const refused = add.isError ? refusal(add.error) : null;
  return (
    <li
      id={checkElementId(f.id)}
      tabIndex={-1}
      className={cn(
        "flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-l-4 border-l-flag/70 px-4 py-3",
        checkRow,
      )}
      data-testid="xv-incomplete-row"
      data-rule={f.rule_id}
    >
      <div className="min-w-0 flex-1 basis-72">
        <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="font-mono text-[11px] text-muted-foreground">{f.rule_id}</span>
          <span className="min-w-0 break-words text-[13px] font-medium text-foreground">
            {comparesText(f)}
            {f.scope && <span className="font-normal text-muted-foreground"> · {f.scope}</span>}
          </span>
        </p>
        {f.explanation && (
          <p className="mt-0.5 break-words text-[12.5px] text-muted-foreground">{f.explanation}</p>
        )}
        {f.request && (
          <p className="mt-0.5 break-words text-[12.5px] text-foreground" data-testid="xv-request">
            {t("crossVerification.incomplete.request", { request: f.request })}
          </p>
        )}
        {refused ? (
          <p
            role="alert"
            className="mt-1 text-[12px] text-destructive"
            data-testid="xv-query-error"
          >
            {refused}
          </p>
        ) : (
          add.isError && (
            <div className="mt-2" data-testid="xv-query-error">
              <ErrorState error={add.error} compact />
            </div>
          )
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {waiting ? (
          <ReviewValue
            caseId={caseId}
            fieldIds={awaiting?.field_ids ?? []}
            evidence={awaiting?.evidence?.[0]}
          />
        ) : item.in_query_list ? (
          <span data-testid="xv-on-query-list">
            <Chip tone="positive">
              <Check className="h-3 w-3" aria-hidden />{" "}
              {t("crossVerification.incomplete.onQueryList")}
            </Chip>
          </span>
        ) : (
          f.request &&
          canDecide && (
            <button
              type="button"
              disabled={add.isPending}
              onClick={() => add.mutate(f.id)}
              className="inline-flex h-7 items-center gap-1 rounded border border-border bg-surface px-2.5 text-[11.5px] font-medium text-foreground hover:bg-muted disabled:opacity-50"
              data-testid="xv-add-query"
            >
              <ListPlus className="h-3.5 w-3.5" aria-hidden />
              {t("crossVerification.incomplete.addToQueryList")}
            </button>
          )
        )}
        {missing.length > 0 && (
          <Link
            to="/appraisals/$caseId/documents"
            params={{ caseId }}
            className="inline-flex items-center gap-1 text-[11.5px] font-medium text-primary hover:underline"
            data-testid="xv-add-documents"
          >
            {t("crossVerification.incomplete.addDocuments")}
            <ArrowRight className="h-3 w-3" aria-hidden />
          </Link>
        )}
      </div>
    </li>
  );
}
