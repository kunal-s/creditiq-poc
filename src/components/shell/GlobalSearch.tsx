import { useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Search } from "lucide-react";
import { t } from "@/config/terminology";
import { stageLabel, useCases } from "@/domain/cases";
import { cn } from "@/lib/utils";

const MAX_RESULTS = 8;
const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

/** The top bar's search over the appraisals the user can see: by borrower, appraisal number or
 * relationship manager. Ctrl K (Cmd K on a Mac) focuses it; a result opens the appraisal. */
export function GlobalSearch() {
  const cases = useCases();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const q = query.trim().toLowerCase();
  const results = useMemo(
    () =>
      q
        ? (cases.data ?? [])
            .filter((c) => [c.borrower, c.id, c.rm].some((v) => v.toLowerCase().includes(q)))
            .slice(0, MAX_RESULTS)
        : [],
    [cases.data, q],
  );

  const go = (id: string) => {
    setOpen(false);
    setQuery("");
    input.current?.blur();
    void navigate({ to: "/appraisals/$caseId", params: { caseId: id } });
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      go(results[active].id);
    } else if (e.key === "Escape") {
      setOpen(false);
      input.current?.blur();
    }
  };

  return (
    <div className="relative w-full max-w-[28rem]" data-testid="global-search">
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-sidebar-foreground/60"
        aria-hidden
      />
      <input
        ref={input}
        type="search"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
        placeholder={t("search.placeholder")}
        aria-label={t("search.label")}
        role="combobox"
        aria-expanded={open && q !== ""}
        aria-controls="global-search-results"
        className="h-8 w-full rounded border border-sidebar-border bg-sidebar-accent/60 pl-8 pr-12 text-[12.5px] text-sidebar-accent-foreground outline-none placeholder:text-sidebar-foreground/60 focus:border-sidebar-ring"
      />
      <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-sidebar-border px-1.5 text-[10px] text-sidebar-foreground/60">
        {MAC ? "⌘K" : "Ctrl K"}
      </kbd>
      {open && q !== "" && (
        <ul
          id="global-search-results"
          role="listbox"
          className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded border border-border bg-surface py-1 text-foreground shadow-lg"
        >
          {results.length === 0 ? (
            <li className="px-3 py-2 text-[12px] text-muted-foreground">{t("search.none")}</li>
          ) : (
            results.map((c, i) => (
              <li key={c.id} role="option" aria-selected={i === active}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => go(c.id)}
                  onMouseEnter={() => setActive(i)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 px-3 py-2 text-left",
                    i === active && "bg-muted",
                  )}
                  data-testid="search-result"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[12.5px] font-medium">{c.borrower}</span>
                    <span className="block truncate text-[11px] text-muted-foreground">
                      {c.id} · {c.rm}
                    </span>
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {stageLabel(c.stage)}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
