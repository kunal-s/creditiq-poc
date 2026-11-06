import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { t } from "@/config/terminology";

const SHOWN_MS = 1500;

/** Copy text to the clipboard; the button that did it says so for a moment. Nothing is sent
 * from the system: the person pastes it where they choose. */
export function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => setCopied(null), SHOWN_MS);
    return () => clearTimeout(id);
  }, [copied]);
  const copy = useCallback(async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
    } catch {
      toast(t("queries.copyFailed"));
    }
  }, []);
  return { copied, copy };
}
