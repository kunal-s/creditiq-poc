import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2 px-6 text-center">
      <p className="text-[14px] font-medium text-foreground">{title}</p>
      <p className="max-w-md text-[13px] text-muted-foreground">{description}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
