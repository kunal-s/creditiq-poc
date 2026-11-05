import { Fragment } from "react";
import { cn } from "@/lib/utils";

export type Count = { key: string; label: string; n: number };

// Each count's separator is drawn before it, and the row is pulled left by the separator's
// width inside a clipping box: a separator that starts a line falls outside the box. The
// separator is drawn by CSS with empty alternative text; where the counts are not a list, a
// separator the screen reader hears sits between them instead.
const ITEM =
  "whitespace-nowrap before:inline-block before:w-[1.1em] before:text-center before:text-muted-foreground before:content-['·'_/_'']";

/** Counts in a line ("Documents needed 3 · Clarifications 1"). Each label stays with its count;
 * where the line wraps, it wraps between two counts, and no separator is left at either end. */
export function CountList({
  counts,
  list,
  strong,
  className,
  testId,
}: {
  counts: Count[];
  /** A list of its own (outside a button or a sentence). */
  list?: boolean;
  /** The counts in bold. */
  strong?: boolean;
  className?: string;
  testId?: string;
}) {
  const Box = list ? "div" : "span";
  const Row = list ? "ul" : "span";
  const Item = list ? "li" : "span";
  return (
    <Box className={cn("relative block overflow-clip", className)} data-testid={testId}>
      <Row className="-ml-[1.1em] flex flex-wrap">
        {counts.map(({ key, label, n }, i) => (
          <Fragment key={key}>
            {/* Out of the flow; in a sentence (not a list) it keeps the counts apart when read. */}
            {!list && i > 0 && <span className="sr-only"> · </span>}
            <Item className={ITEM}>
              {label} <span className={cn("tabular", strong && "font-semibold")}>{n}</span>
            </Item>
          </Fragment>
        ))}
      </Row>
    </Box>
  );
}
