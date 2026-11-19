/** An amount in the statement's own unit, as the statement prints it. */
export function printedAmount(value: number): string {
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

/** The amount in whole rupees, Indian grouping. */
export function inRupees(value: number): string {
  return Math.round(value).toLocaleString("en-IN");
}
