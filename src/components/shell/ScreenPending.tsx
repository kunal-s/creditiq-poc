import { EmptyState } from "./EmptyState";

/** Body of a screen whose feature has not landed yet. Wave 1 replaces every
 * use with the prototype screen fed by real data (FRD AD-1); a check before
 * the live session fails while any use remains. */
export function ScreenPending({ feature }: { feature: string }) {
  return (
    <div className="px-6 py-5">
      <EmptyState
        title="Nothing to show yet"
        description={`This screen fills in once ${feature} is delivered.`}
      />
    </div>
  );
}
