import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Clock, Lock, SearchX, ServerCrash, Settings2, TriangleAlert, WifiOff } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";
import { errorKind, type ErrorKind } from "@/domain/errors";
import { cn } from "@/lib/utils";

/** Designed loading state: skeleton rows in the shape of a panel. */
export function LoadingBlock({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div
      className={cn("space-y-2.5 rounded border border-border bg-surface p-4", className)}
      role="status"
      aria-label={t("state.loading")}
      data-testid="loading"
    >
      <Skeleton className="h-3.5 w-40" />
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

const ICON: Record<ErrorKind, typeof Clock> = {
  notAvailable: Clock,
  forbidden: Lock,
  notFound: SearchX,
  noConfig: Settings2,
  invalid: TriangleAlert,
  unreachable: WifiOff,
  failed: ServerCrash,
};

/** Designed error state. A 501 reads as "not available yet", never as a failure. */
export function ErrorState({
  error,
  onRetry,
  compact,
}: {
  error: unknown;
  onRetry?: () => void;
  compact?: boolean | undefined;
}) {
  const kind = errorKind(error);
  const Icon = ICON[kind];
  const tone =
    kind === "notAvailable" || kind === "forbidden" || kind === "noConfig"
      ? "border-border bg-surface"
      : "border-destructive/30 bg-destructive/5";
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded border border-dashed text-center",
        compact ? "px-4 py-5" : "px-6 py-10",
        tone,
      )}
      role={kind === "notAvailable" ? "status" : "alert"}
      data-testid={`state-${kind}`}
    >
      <Icon className="h-5 w-5 text-muted-foreground" />
      <p className="text-[14px] font-medium text-foreground">{t(`state.${kind}.title`)}</p>
      <p className="max-w-md text-[12.5px] text-muted-foreground">
        {t(`state.${kind}.description`)}
      </p>
      {onRetry && kind !== "forbidden" && kind !== "notFound" && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded border border-border bg-surface px-3 py-1 text-[12px] font-medium hover:bg-muted"
        >
          {t("action.retry")}
        </button>
      )}
    </div>
  );
}

/** Loading, error and empty states around one query. */
export function QueryView<T>({
  query,
  isEmpty,
  empty,
  loading,
  compact,
  children,
}: {
  query: Pick<UseQueryResult<T>, "data" | "isLoading" | "isError" | "error" | "refetch">;
  isEmpty?: (data: T) => boolean;
  empty?: { title: string; description: string; action?: ReactNode };
  loading?: ReactNode;
  compact?: boolean;
  children: (data: T) => ReactNode;
}) {
  if (query.isError) {
    return (
      <ErrorState error={query.error} compact={compact} onRetry={() => void query.refetch()} />
    );
  }
  if (query.isLoading || query.data === undefined) return <>{loading ?? <LoadingBlock />}</>;
  if (empty && isEmpty?.(query.data)) {
    return <EmptyState title={empty.title} description={empty.description} action={empty.action} />;
  }
  return <>{children(query.data)}</>;
}
