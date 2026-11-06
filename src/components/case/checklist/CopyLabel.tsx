import type { LucideIcon } from "lucide-react";
import { CopyCheck } from "lucide-react";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

const FACE = "col-start-1 row-start-1 inline-flex items-center justify-center gap-1.5";

/** A copy button's label, and "Copied" for a moment after. Both are laid out in one cell, so
 * the button keeps the width of the longer and nothing beside it moves; the one not shown is
 * hidden from sight and from the button's name. */
export function CopyLabel({
  icon: Icon,
  label,
  copied,
  iconClass = "size-3.5",
}: {
  icon: LucideIcon;
  label: string;
  copied: boolean;
  iconClass?: string;
}) {
  return (
    <span className="grid">
      <span className={cn(FACE, copied && "invisible")}>
        <Icon className={iconClass} aria-hidden />
        {label}
      </span>
      <span className={cn(FACE, !copied && "invisible")}>
        <CopyCheck className={cn(iconClass, "text-positive")} aria-hidden />
        {t("journey.copied")}
      </span>
    </span>
  );
}
