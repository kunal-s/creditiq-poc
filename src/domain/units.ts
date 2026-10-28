import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { DisplayUnit } from "@/api/types";

// The unit financial figures are written in: one published setting (Administration screen), so the
// statement tables, the policy page, the memo and the exports write a figure the same way. The
// engine words its own sentences in the same unit (engine/units.py).

const DEFAULT: DisplayUnit = {
  unit: "crore",
  label: "Crore",
  divisor: 1e7,
  decimals: 2,
  suffix: " cr",
};

let current: DisplayUnit = DEFAULT;

/** The unit now in force. A component that shows a figure calls useDisplayUnit() so it is drawn
 * again when the unit is published anew; the formatters below read the unit it loaded. */
export function useDisplayUnit(): DisplayUnit {
  const { data } = useQuery({
    queryKey: ["config", "display-unit"],
    queryFn: api.displayUnit,
    staleTime: Infinity,
  });
  if (data) current = data;
  return data ?? current;
}

export function displayUnit(): DisplayUnit {
  return current;
}

/** What a table's heading names: "INR crore", "INR" for whole rupees. */
export function unitHeading(unit: DisplayUnit = current): string {
  return unit.divisor === 1 ? "INR" : `INR ${unit.label.toLowerCase()}`;
}

/** A financial figure in the unit, no more: "4.20" (crore), "42,00,000" (rupees). A table puts the
 * unit in its heading. Negative figures keep their sign. */
export function inUnit(value: number, unit: DisplayUnit = current): string {
  const scaled = value / unit.divisor;
  const text = scaled.toLocaleString("en-IN", {
    minimumFractionDigits: unit.decimals,
    maximumFractionDigits: unit.decimals,
  });
  // A figure that rounds to nothing is not "-0.00".
  return /^-[0.,]+$/.test(text) ? text.slice(1) : text;
}

/** A financial figure with its unit, as a sentence writes it: "INR 4.20 cr", "INR 42,00,000". */
export function money(value: number, unit: DisplayUnit = current): string {
  return `INR ${inUnit(value, unit)}${unit.suffix}`;
}
