import { Check, X } from "lucide-react";
import type { GateCondition } from "./conditions";

/** The three conditions of the F-13 gate, each with a tick or a cross. Used by the panel on
 * the completeness step and by the locked stages, so both read identically. */
export function ConditionList({ conditions }: { conditions: GateCondition[] }) {
  return (
    <ul className="space-y-1.5" data-testid="gate-conditions">
      {conditions.map((condition) => (
        <li
          key={condition.key}
          className="flex items-start gap-2 text-[12.5px]"
          data-testid="gate-condition"
          data-condition={condition.key}
          data-met={condition.met}
        >
          {condition.met ? (
            <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" aria-hidden />
          ) : (
            <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-flag-foreground" aria-hidden />
          )}
          <span className={condition.met ? "text-muted-foreground" : "text-foreground"}>
            {condition.label}
          </span>
        </li>
      ))}
    </ul>
  );
}
