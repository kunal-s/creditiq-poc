import { useId, useState } from "react";
import { Lock } from "lucide-react";
import { toast } from "sonner";
import type { XvDecision, XvDecisionKind, XvItem } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { t } from "@/config/terminology";
import { formatStamp, useDecideFinding } from "@/domain/crossVerification";
import { refusal } from "@/domain/errors";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { DECISION_TONE } from "./styles";

const CHOICES: XvDecisionKind[] = ["accept", "dismiss", "escalate"];
const MIN_COMMENT = 3;

/** The reviewer's decision on a discrepancy (F-19, F-17.4): accept, dismiss or escalate, each
 * with a comment. Accepted or dismissed, it is recorded and shown; escalated, it stays open and
 * blocking until the Credit Manager accepts or dismisses it. A refused decision says why and the
 * board reads the engine again, so a decision or an escalation made meanwhile shows in its
 * place. */
export function Adjudication({ caseId, item }: { caseId: string; item: XvItem }) {
  const canDecide = useCan("review.decide");
  const canDecideEscalated = useCan("finding.escalation");
  const decide = useDecideFinding(caseId);
  const [choice, setChoice] = useState<XvDecisionKind | null>(null);
  const [comment, setComment] = useState("");
  const id = useId();
  const { decision, escalation } = item;
  const failure = decide.isError ? <DecisionError error={decide.error} /> : null;

  if (decision) {
    return (
      <div className="space-y-2 px-4 py-3">
        {failure}
        <RecordedDecision decision={decision} />
        {escalation && <EscalationNote escalation={escalation} />}
      </div>
    );
  }

  const waiting = Boolean(escalation) && !canDecideEscalated;
  // An escalated discrepancy is already with the Credit Manager, who accepts or dismisses it.
  const choices = escalation ? CHOICES.filter((c) => c !== "escalate") : CHOICES;
  const locked = waiting || decide.isPending;
  const ready = choice !== null && comment.trim().length >= MIN_COMMENT && !locked;
  const clearError = () => {
    if (decide.isError) decide.reset();
  };
  const save = () => {
    if (!choice || !ready) return;
    decide.mutate(
      { findingId: item.finding.id, body: { decision: choice, comment: comment.trim() } },
      {
        onSuccess: () => {
          setChoice(null);
          setComment("");
          toast.success(t("review.recorded"));
        },
      },
    );
  };

  return (
    <div className="space-y-2.5 px-4 py-3" data-testid="xv-adjudication">
      {escalation && <EscalationNote escalation={escalation} />}
      {!canDecide ? (
        <p className="text-[12px] text-muted-foreground" data-testid="xv-read-only">
          {t("crossVerification.decision.readOnly")}
        </p>
      ) : (
        <>
          <p id={`${id}-title`} className="field-label">
            {t("crossVerification.decision.title")}
          </p>
          <div
            role="radiogroup"
            aria-labelledby={`${id}-title`}
            className={cn("grid gap-2", choices.length === 3 ? "lg:grid-cols-3" : "sm:grid-cols-2")}
          >
            {choices.map((c) => (
              <label
                key={c}
                className={cn(
                  "flex min-w-0 items-start gap-2 rounded border px-3 py-2 transition-colors",
                  choice === c ? "border-primary bg-primary/5" : "border-border bg-surface",
                  locked ? "cursor-not-allowed opacity-60" : "cursor-pointer",
                  !locked && choice !== c && "hover:border-primary/40 hover:bg-surface-muted",
                )}
              >
                <input
                  type="radio"
                  name={`${id}-decision`}
                  value={c}
                  checked={choice === c}
                  disabled={locked}
                  onChange={() => {
                    setChoice(c);
                    clearError();
                  }}
                  aria-describedby={`${id}-${c}`}
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-[var(--primary)]"
                  data-testid={`xv-decision-${c}`}
                />
                <span className="min-w-0">
                  <span className="block text-[12.5px] font-medium text-foreground">
                    {t(`crossVerification.decision.${c}`)}
                  </span>
                  <span
                    id={`${id}-${c}`}
                    className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground"
                  >
                    {t(`crossVerification.decision.${c}Help`)}
                  </span>
                </span>
              </label>
            ))}
          </div>
          {waiting && (
            <p
              className="flex items-center gap-1.5 text-[12px] font-medium text-flag-foreground"
              data-testid="xv-waiting-manager"
            >
              <Lock className="h-3.5 w-3.5" aria-hidden />
              {t("crossVerification.decision.waitingForManager")}
            </p>
          )}
          <label className="block">
            <span className="field-label">{t("crossVerification.decision.comment")}</span>
            <textarea
              rows={3}
              value={comment}
              disabled={locked}
              required
              minLength={MIN_COMMENT}
              onChange={(e) => {
                setComment(e.target.value);
                clearError();
              }}
              placeholder={t("crossVerification.decision.commentPlaceholder")}
              aria-describedby={`${id}-hint`}
              className="mt-1 w-full resize-y rounded border border-border bg-surface px-3 py-2 text-[12.5px] outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
              data-testid="xv-comment"
            />
          </label>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <button
              type="button"
              disabled={!ready}
              onClick={save}
              className="h-8 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
              data-testid="xv-save-decision"
            >
              {t("crossVerification.decision.save")}
            </button>
            <span id={`${id}-hint`} className="text-[11.5px] text-muted-foreground">
              {t("crossVerification.decision.commentHint")}
            </span>
          </div>
          {failure}
        </>
      )}
    </div>
  );
}

/** Why a decision was not recorded: the engine's refusal word for word where it is written for
 * the reader (a comment too short, decided or escalated meanwhile), else the designed state. */
function DecisionError({ error }: { error: unknown }) {
  const refused = refusal(error);
  return refused ? (
    <p role="alert" className="text-[12px] text-destructive" data-testid="xv-decision-error">
      {refused}
    </p>
  ) : (
    <div data-testid="xv-decision-error">
      <ErrorState error={error} compact />
    </div>
  );
}

/** An accepted or dismissed discrepancy: the decision, who made it and when, and why. A decision
 * recorded without a comment (in the review queue, before every decision needed one) says so. */
function RecordedDecision({ decision }: { decision: XvDecision }) {
  return (
    <div
      className="rounded border border-border bg-surface-muted p-3"
      data-testid="xv-recorded-decision"
      data-decision={decision.decision}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Chip tone={DECISION_TONE[decision.decision]}>
          {t(`crossVerification.decided.${decision.decision}`)}
        </Chip>
        <p className="text-[11.5px] text-muted-foreground">
          {t("crossVerification.decision.by", {
            name: decision.by_name || decision.by,
            at: formatStamp(decision.at),
          })}
        </p>
      </div>
      {decision.comment ? (
        <p className="mt-2 whitespace-pre-line break-words text-[12.5px] leading-relaxed text-foreground/85">
          {decision.comment}
        </p>
      ) : (
        <p className="mt-2 text-[12px] italic text-muted-foreground" data-testid="xv-no-comment">
          {t("crossVerification.decision.noComment")}
        </p>
      )}
      <p className="mt-1 text-[11.5px] text-muted-foreground">
        {t(`crossVerification.decision.${decision.decision}Help`)}
      </p>
    </div>
  );
}

/** Who escalated the discrepancy to the Credit Manager, when, and why. */
function EscalationNote({ escalation }: { escalation: XvDecision }) {
  return (
    <div
      className="rounded border border-info/30 bg-info-soft px-3 py-2 text-[12px]"
      data-testid="xv-escalation-note"
    >
      <p className="font-medium text-info">
        {t("crossVerification.decision.escalatedBy", {
          name: escalation.by_name || escalation.by,
          at: formatStamp(escalation.at),
        })}
      </p>
      {escalation.comment && (
        <p className="mt-0.5 whitespace-pre-line break-words text-foreground/85">
          {escalation.comment}
        </p>
      )}
    </div>
  );
}
