import { createFileRoute } from "@tanstack/react-router";
import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";
import type { Meta } from "@/api/types";
import { IntakeDocuments } from "@/components/cases/IntakeDocuments";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { CreateBar } from "@/components/intake/CreateBar";
import { IntakeForm } from "@/components/intake/IntakeForm";
import { MessagePanel } from "@/components/intake/MessagePanel";
import { ProductChoice, type IntakeStep } from "@/components/intake/ProductChoice";
import { ReviewPanel } from "@/components/intake/ReviewPanel";
import { StartButton, StartPanel } from "@/components/intake/StartPanel";
import { duplicatesIn, useNewApplication } from "@/components/intake/useNewApplication";
import { PageHeader } from "@/components/shell/PageHeader";
import { t } from "@/config/terminology";
import { useMeta } from "@/domain/cases";
import { previewRequest } from "@/domain/intakeCreate";
import { withIntakeDefaults } from "@/domain/intakeMeta";

export const Route = createFileRoute("/appraisals/new")({
  head: () => ({
    meta: [{ title: `${t("page.newApplication.title")} — ${t("tenant.product.name")}` }],
  }),
  component: NewApplication,
});

/** The product-first New appraisal (F-04; plan 2026-11-27): the product, the start boxes (a
 * message and identifiers optional, documents required), the product's form, the review and
 * Create — sections of one page. Nothing is stored until Create sends the case with its files. */
function NewApplication() {
  const query = useMeta();
  const meta = useMemo(
    () => (query.data ? withIntakeDefaults(query.data) : undefined),
    [query.data],
  );
  const app = useNewApplication(meta);
  const blocked = Object.values(app.checks).some((c) => (Array.isArray(c) ? c.length > 0 : c));
  const step: IntakeStep = !app.draft ? "start" : blocked ? "details" : "review";

  return (
    <div>
      <PageHeader
        eyebrow={t("page.newApplication.eyebrow")}
        title={t("page.newApplication.title")}
        purpose={t("page.newApplication.purpose")}
        actions={
          meta && app.form && !app.draft ? (
            <StartButton
              meta={meta}
              form={app.form}
              start={app.start}
              reading={app.propose.isPending}
              onContinue={app.continueFromStart}
            />
          ) : undefined
        }
      />
      <div className="space-y-4 px-4 pt-5 pb-5 sm:px-6">
        {query.isError ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        ) : !meta || !app.form ? (
          <LoadingBlock rows={6} />
        ) : (
          <>
            <ProductChoice
              products={meta.products}
              value={app.draft?.product ?? app.start.product}
              pending={app.pending}
              step={step}
              onChoose={app.chooseProduct}
              onConfirm={app.confirmSwitch}
              onCancel={app.cancelSwitch}
              disabled={app.propose.isPending}
            />
            {app.draft ? (
              <ApplicationView app={app} meta={meta} />
            ) : (
              <StartPanel
                meta={meta}
                form={app.form}
                start={app.start}
                onStart={app.patchStart}
                error={app.propose.isError ? app.propose.error : null}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Steps 3 to 5 once the start is done: the message beside the form (when there is one), then
 * the review with the documents, then Create. */
function ApplicationView({ app, meta }: { app: ReturnType<typeof useNewApplication>; meta: Meta }) {
  const { draft, form, proposal, body } = app;
  if (!draft || !form || !body) return null;
  const files = app.start.files;
  const reading = app.propose.isPending;
  const next = meta.products.find((p) => p.id === (app.switching ?? app.start.product));
  return (
    <>
      {reading && (
        <p
          role="status"
          data-testid="form-reading"
          className="rounded border border-info/30 bg-info-soft px-4 py-2 text-[12px] text-info"
        >
          {t("intake.form.reading", { product: next?.label ?? "" })}
        </p>
      )}
      {app.propose.isError && <ErrorState error={app.propose.error} compact />}
      <fieldset
        disabled={reading}
        aria-busy={reading || undefined}
        className={cn(
          "m-0 min-w-0 border-0 p-0",
          proposal && "grid items-start gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]",
          reading && "opacity-60",
        )}
      >
        {proposal ? (
          <div className="min-w-0 lg:sticky lg:top-4">
            <MessagePanel
              text={app.start.text}
              proposal={proposal}
              draft={draft}
              selected={app.selected}
              onEdit={app.backToStart}
            />
          </div>
        ) : (
          <button
            type="button"
            onClick={app.backToStart}
            data-testid="back-to-start"
            className="mb-3 inline-flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] font-medium text-foreground hover:bg-muted"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> {t("intake.form.backToStart")}
          </button>
        )}
        <IntakeForm
          form={form}
          draft={draft}
          proposal={proposal}
          meta={meta}
          selected={app.selected}
          onSelect={app.setSelected}
          onChange={app.setDraft}
        />
      </fieldset>
      <h2 className="pt-1 text-[13px] font-semibold text-foreground">
        {t("intake.reviewHeading")}
      </h2>
      <div className="grid items-start gap-4 @min-[56rem]/main:grid-cols-2">
        <ReviewPanel
          product={draft.product}
          form={form}
          body={body}
          missing={app.checks.missing}
          gaps={app.checks.gaps}
          files={files}
          onAttach={(added) => app.patchStart({ files: [...files, ...added] })}
          onRemove={(i) => app.patchStart({ files: files.filter((_, j) => j !== i) })}
          review={app.review}
          fresh={app.fresh}
          duplicates={app.duplicates}
          override={app.override}
          reason={app.reason}
          onOverride={() => app.setOverride(true)}
          onReason={app.setReason}
        />
        <IntakeDocuments request={previewRequest(meta, draft)} />
      </div>
      <CreateBar
        {...app.checks}
        creating={app.create.isPending}
        error={duplicatesIn(app.create.error) ? null : app.create.error}
        onDiscard={app.discard}
        onCreate={app.submit}
      />
    </>
  );
}
