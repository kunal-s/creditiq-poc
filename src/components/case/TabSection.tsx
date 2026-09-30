import type { ReactNode } from "react";
import { useAnchor } from "@/domain/anchor";

/** A titled part of a case tab; `id` is the anchor other screens link to. */
export function TabSection({
  id,
  title,
  purpose,
  children,
}: {
  id: string;
  title: string;
  purpose: string;
  children: ReactNode;
}) {
  const ref = useAnchor<HTMLElement>(id);
  return (
    <section ref={ref} id={id} className="scroll-mt-4" data-testid={`section-${id}`}>
      <div className="px-4 pt-5 sm:px-6">
        <h2 className="text-[15px] font-semibold tracking-tight text-foreground">{title}</h2>
        <p className="mt-0.5 max-w-3xl text-[12.5px] text-muted-foreground">{purpose}</p>
      </div>
      {children}
    </section>
  );
}
