import { Chip } from "@/components/common/Panel";
import { useMeta } from "@/domain/cases";

/** The product a case was opened under, as a small chip with its case-number prefix (LAP, BBG);
 * its name in the hover text. Nothing for a case with no product recorded. */
export function ProductChip({ product }: { product?: string | null | undefined }) {
  const { data: meta } = useMeta();
  if (!product) return null;
  const p = meta?.products.find((x) => x.id === product);
  return (
    <Chip tone="muted" upper title={p?.label ?? product}>
      <span data-testid="product-chip" data-product={product}>
        {p?.prefix ?? product.toUpperCase()}
      </span>
    </Chip>
  );
}
