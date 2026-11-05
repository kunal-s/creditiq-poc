import { useCallback, useEffect, useState } from "react";

const FLASH_MS = 1200;

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

/** Jump to a requirement's row from anywhere on the page (a blocker chip, a section cell, an
 * outcome): show it if the filter hides it, open the done band if it is there, bring it to the
 * middle of the screen, flash it, and move focus to its name. */
export function useJump({
  hidden,
  inDone,
  showAll,
  openDone,
}: {
  /** Whether the current filter hides the row. */
  hidden: (itemId: string) => boolean;
  /** Whether the row sits in the done band. */
  inDone: (itemId: string) => boolean;
  showAll: () => void;
  openDone: () => void;
}) {
  const [target, setTarget] = useState<{ id: string } | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const jump = useCallback(
    (itemId: string) => {
      if (hidden(itemId)) showAll();
      if (inDone(itemId)) openDone();
      // A fresh object each time, so a second jump to the same row runs again.
      setTarget({ id: itemId });
    },
    [hidden, inDone, showAll, openDone],
  );

  // After the filter and the done band have been applied, the row is in the page.
  useEffect(() => {
    if (!target) return;
    const frame = requestAnimationFrame(() => {
      const row = document.getElementById(`req-${target.id}`);
      if (!row) return;
      document.getElementById(`req-${target.id}-name`)?.focus({ preventScroll: true });
      row.scrollIntoView({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" });
      setFlash(target.id);
    });
    return () => cancelAnimationFrame(frame);
  }, [target]);

  useEffect(() => {
    if (!flash) return;
    const id = setTimeout(() => setFlash(null), FLASH_MS);
    return () => clearTimeout(id);
  }, [flash, target]);

  return { jump, flash };
}
