import { t } from "@/config/terminology";
import { EmptyState } from "./EmptyState";

/** Body of a screen whose feature lands in a later wave (spread,
 * cross-verification, policy, draft, comparison and scorecard). The feature
 * reference is kept for tracing only, never shown. */
export function ScreenPending({ feature }: { feature: string }) {
  return (
    <div className="px-4 py-5 sm:px-6" data-feature={feature}>
      <EmptyState title={t("state.pending.title")} description={t("state.pending.description")} />
    </div>
  );
}
