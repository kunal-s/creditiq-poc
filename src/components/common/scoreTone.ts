/** The colour of a readiness score against its gate: positive once the gate is met with nothing
 * blocking, else critical while anything blocks or the score is far off, flag when it is close.
 * The case header's bar and the Overview's meter share it, so they never disagree. */
export function scoreTone(score: number, gate: number, blocking?: number): string {
  return score >= gate && !blocking
    ? "bg-positive"
    : blocking
      ? "bg-destructive/40"
      : score >= gate * 0.75
        ? "bg-flag/60"
        : "bg-destructive/40";
}
