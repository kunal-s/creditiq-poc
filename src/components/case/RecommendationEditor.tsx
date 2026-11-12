import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Cam } from "@/api/types";
import { api } from "@/api/client";
import { Recommendation } from "@/components/case/Outputs";
import { t } from "@/config/terminology";
import { readRecommendation, writeRecommendation } from "@/domain/camRecommendation";
import { useCamChange } from "@/domain/findings";
import { formatDay } from "@/domain/outputs";
import { useCan } from "@/domain/session";

// The recommendation, written where credit is asked for it (F-23.4): one box under each heading the
// memo carries. Saving goes through the engine into the memo's recommendation section, the same
// record Outputs edits, with who saved it and when; nothing is kept only in the browser. A role that
// cannot decide reads the recommendation as the memo prints it.
//
// Test ids: recommendation-editor, recommendation-answer (data-prompt), recommendation-save,
// recommendation-saved, recommendation-error, recommendation-sign-off.

export function RecommendationEditor({ caseId, m }: { caseId: string; m: Cam }) {
  const mayWrite = useCan("review.decide");
  const prompts = m.recommendation_prompts ?? [];
  const stored = readRecommendation(m.recommendation ?? "", prompts);
  const [drafts, setDrafts] = useState<string[]>(() => stored.answers.map((a) => a.text));
  const first = useRef<HTMLTextAreaElement>(null);
  const save = useCamChange(caseId, (paragraphs: string[]) =>
    api.camWords(caseId, "recommendation", { paragraphs, source: "person" }),
  );
  const storedKey = stored.answers.map((a) => a.text).join("\u0000");
  const dirty = drafts.join("\u0000") !== storedKey;
  const empty = drafts.every((d) => !d.trim()) && stored.other.length === 0;

  // A link to this box ("Open the recommendation") puts the cursor in it.
  useEffect(() => {
    if (window.location.hash === "#recommendation") first.current?.focus();
  }, []);
  // Leaving the page with words not saved asks first.
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (!mayWrite || prompts.length === 0) return <Recommendation m={m} headed={false} />;

  const review = m.recommendation_review;
  const saved = review && review.state !== "machine" && review.at ? review : null;
  return (
    <form
      className="space-y-3"
      data-testid="recommendation-editor"
      onSubmit={(e) => {
        e.preventDefault();
        if (!dirty || empty || save.isPending) return;
        save.mutate(
          writeRecommendation(
            prompts.map((prompt, i) => ({ prompt, text: drafts[i] ?? "" })),
            stored.other,
          ),
        );
      }}
    >
      {stored.other.map((p, i) => (
        <p key={i} className="text-[13px] leading-relaxed">
          {p}
        </p>
      ))}
      {prompts.map((prompt, i) => (
        <label
          key={prompt}
          className="block"
          data-testid="recommendation-answer"
          data-prompt={prompt}
        >
          <span className="text-[12.5px] font-medium text-foreground">{prompt}</span>
          <textarea
            ref={i === 0 ? first : undefined}
            value={drafts[i] ?? ""}
            onChange={(e) => setDrafts((d) => d.map((v, k) => (k === i ? e.target.value : v)))}
            rows={i === 0 ? 4 : 3}
            placeholder={t("page.rating.answerPlaceholder")}
            className="mt-1 block w-full resize-y rounded border border-border bg-surface px-3 py-2 text-[13px] leading-relaxed placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring"
          />
        </label>
      ))}
      <div className="flex flex-wrap items-center gap-3 pt-1">
        <button
          type="submit"
          disabled={!dirty || empty || save.isPending}
          className="inline-flex h-8 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="recommendation-save"
        >
          {save.isPending && (
            <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
          )}
          {t(save.isPending ? "page.rating.saving" : "page.rating.save")}
        </button>
        {dirty && !save.isPending && (
          <button
            type="button"
            onClick={() => setDrafts(stored.answers.map((a) => a.text))}
            className="inline-flex h-8 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-surface-muted"
          >
            {t("page.rating.discard")}
          </button>
        )}
        <span
          className="text-[12px] text-muted-foreground"
          aria-live="polite"
          data-testid="recommendation-saved"
        >
          {dirty
            ? t("page.rating.unsaved")
            : saved
              ? t("page.rating.savedBy", {
                  name: saved.by_name ?? saved.by ?? "",
                  at: formatDay(saved.at ?? ""),
                })
              : t("page.rating.notWritten")}
        </span>
        {save.isError && (
          <span className="text-[12px] text-critical-text" data-testid="recommendation-error">
            {t("page.rating.saveFailed")}
          </span>
        )}
      </div>
      {(m.sign_off ?? []).length > 0 && (
        <dl
          className="mt-2 grid gap-x-6 gap-y-1 border-t border-border pt-3 text-[12px] sm:grid-cols-3"
          data-testid="recommendation-sign-off"
        >
          {(m.sign_off ?? []).map((r, i) => (
            <div key={r.role} className="min-w-0">
              <dt className="text-muted-foreground">{r.role}</dt>
              <dd className="text-foreground">
                {i === 0 && saved
                  ? t("page.rating.signedBy", {
                      name: saved.by_name ?? saved.by ?? "",
                      at: formatDay(saved.at ?? ""),
                    })
                  : t("page.rating.notYet")}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </form>
  );
}
