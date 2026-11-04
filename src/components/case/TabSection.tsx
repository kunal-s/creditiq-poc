import type { ReactNode } from "react";
import { useAnchor } from "@/domain/anchor";

/** A titled part of a case tab; `id` is the anchor other screens link to. The step's first part
 * opens with the header band every step has (`kicker` names the appraisal and the step), with the
 * step's actions under it; later parts carry a plain heading. */
export function TabSection({
  id,
  title,
  purpose,
  kicker,
  actions,
  children,
}: {
  id: string;
  title: string;
  purpose: string;
  kicker?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const ref = useAnchor<HTMLElement>(id);
  return (
    <section ref={ref} id={id} className="scroll-mt-4" data-testid={`section-${id}`}>
      {kicker ? (
        <StepHeader kicker={kicker} title={title} purpose={purpose} actions={actions} />
      ) : (
        <div className="px-4 pt-5 sm:px-6">
          <h2 className="text-[15px] font-semibold tracking-tight text-foreground">{title}</h2>
          <p className="mt-0.5 max-w-3xl text-[12.5px] text-muted-foreground">{purpose}</p>
        </div>
      )}
      {children}
    </section>
  );
}

/** The head of a case step: the appraisal and the step, the title, what the step is for, and its
 * actions, on a white band under the case header. */
export function StepHeader({
  kicker,
  title,
  purpose,
  actions,
}: {
  kicker: string;
  title: string;
  purpose?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="border-b border-border bg-surface px-4 py-4 sm:px-6" data-testid="step-header">
      <p className="field-label break-words">{kicker}</p>
      <h1 className="mt-0.5 text-[19px] font-semibold tracking-tight text-foreground">{title}</h1>
      {purpose && <p className="mt-1 max-w-3xl text-[13px] text-muted-foreground">{purpose}</p>}
      {actions && <div className="mt-3 flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
