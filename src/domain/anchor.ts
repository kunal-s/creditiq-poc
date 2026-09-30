import { useRouterState } from "@tanstack/react-router";
import { useEffect, useRef } from "react";

/**
 * Scroll to the element with this id when the URL's hash names it. The
 * content above it may still be loading, so the scroll repeats briefly
 * until the page settles, then leaves the reader alone.
 */
export function useAnchor<T extends HTMLElement>(id: string) {
  const ref = useRef<T>(null);
  const hash = useRouterState({ select: (s) => s.location.hash });
  useEffect(() => {
    if (hash !== id) return;
    const timers = [0, 150, 400, 800].map((ms) =>
      window.setTimeout(() => ref.current?.scrollIntoView({ block: "start" }), ms),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [hash, id]);
  return ref;
}
