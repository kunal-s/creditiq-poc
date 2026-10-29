import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";

// A column beside the page for the case assistant. It is not a dialog: the page stays visible and usable next to it.
// A screen that has an assistant registers it (`available`) and renders its panel into the dock's node; the dock is
// shown while the screen has registered one and the user has it open. Below `md` there is no room beside the page,
// so the dock covers it instead. Whether it is open and how wide it is are remembered for the tab.

const OPEN_KEY = "creditiq.assistant.open";
const WIDTH_KEY = "creditiq.assistant.width";
const DEFAULT_WIDTH = 400;
const MIN_WIDTH = 320;
const MAX_WIDTH = 720;
const STEP = 24;

const clamp = (n: number) => Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(n)));

function remembered(key: string, store: "session" | "local"): string | null {
  try {
    return (store === "session" ? sessionStorage : localStorage).getItem(key);
  } catch {
    return null; // private windows and blocked storage: carry on without it
  }
}

function remember(key: string, value: string, store: "session" | "local"): void {
  try {
    (store === "session" ? sessionStorage : localStorage).setItem(key, value);
  } catch {
    /* nothing to do */
  }
}

interface Dock {
  /** Where the panel is rendered; null until the dock has mounted. */
  node: HTMLElement | null;
  open: boolean;
  setOpen: (open: boolean) => void;
  /** A screen with an assistant calls this on mount and with false on unmount. */
  setAvailable: (available: boolean) => void;
  // for the slot
  hostRef: (el: HTMLElement | null) => void;
  visible: boolean;
  width: number;
  resize: (w: number) => void;
}

const DockContext = createContext<Dock | null>(null);

export function useAssistantDock(): Dock | null {
  return useContext(DockContext);
}

export function AssistantDockProvider({ children }: { children: ReactNode }) {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const [open, setOpenState] = useState(() => remembered(OPEN_KEY, "session") === "1");
  const [available, setAvailable] = useState(false);
  const [width, setWidth] = useState(() =>
    clamp(Number(remembered(WIDTH_KEY, "local")) || DEFAULT_WIDTH),
  );

  const setOpen = useCallback((next: boolean) => {
    setOpenState(next);
    remember(OPEN_KEY, next ? "1" : "0", "session");
  }, []);
  const resize = useCallback((next: number) => {
    const w = clamp(next);
    setWidth(w);
    remember(WIDTH_KEY, String(w), "local");
  }, []);

  const visible = available && open;
  const value = useMemo<Dock>(
    () => ({ node, open, setOpen, setAvailable, hostRef: setNode, visible, width, resize }),
    [node, open, setOpen, visible, width, resize],
  );
  return <DockContext.Provider value={value}>{children}</DockContext.Provider>;
}

/** The column itself: place it beside the page, inside the row that holds the page. */
export function AssistantDockSlot() {
  const dock = useAssistantDock();
  if (!dock) return null;
  return <Column {...dock} />;
}

function Column({ hostRef, visible, width, resize: onResize }: Dock) {
  const drag = useRef<{ x: number; w: number } | null>(null);
  useEffect(() => {
    if (!visible) drag.current = null;
  }, [visible]);

  const down = (e: PointerEvent<HTMLDivElement>) => {
    drag.current = { x: e.clientX, w: width };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const move = (e: PointerEvent<HTMLDivElement>) => {
    if (drag.current) onResize(drag.current.w + (drag.current.x - e.clientX));
  };
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft") onResize(width + STEP);
    else if (e.key === "ArrowRight") onResize(width - STEP);
    else return;
    e.preventDefault();
  };

  return (
    <aside
      data-testid="assistant-dock"
      data-open={visible}
      style={{ "--dock-w": `${width}px` } as React.CSSProperties}
      className={cn(
        "relative min-h-0 shrink-0 flex-col border-l border-border bg-surface",
        visible ? "flex max-md:fixed max-md:inset-0 max-md:z-50 md:w-(--dock-w)" : "hidden",
      )}
    >
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize"
        aria-valuemin={MIN_WIDTH}
        aria-valuemax={MAX_WIDTH}
        aria-valuenow={width}
        tabIndex={0}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={() => (drag.current = null)}
        onKeyDown={key}
        className="absolute inset-y-0 -left-1 z-10 hidden w-2 cursor-col-resize touch-none transition-colors hover:bg-primary/20 focus-visible:bg-primary/30 focus-visible:outline-none md:block"
      />
      <div ref={hostRef} className="flex min-h-0 flex-1 flex-col" />
    </aside>
  );
}
