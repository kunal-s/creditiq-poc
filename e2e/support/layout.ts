import type { Page } from "@playwright/test";

// How a screen sits on a phone: what sticks out past the screen edge, and a way to unroll the
// layout's scrolling areas so a screenshot shows the whole screen.

/** What sticks out past the screen edge. Content may scroll sideways only inside a box that is
 * narrower than the screen (a table inside a card); the full-width areas the layout scrolls in
 * count as the page. Content cut off by a box that hides its overflow counts too. */
export async function overflow(page: Page) {
  return page.evaluate(() => {
    const width = window.innerWidth;
    const box = (el: Element) => {
      for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        const s = getComputedStyle(p);
        const r = p.getBoundingClientRect();
        // A table in a card, or a strip of tabs: it scrolls sideways on purpose. The tall,
        // full-width area the layout scrolls in is the page.
        if (
          ["auto", "scroll"].includes(s.overflowX) &&
          (r.width < width - 2 || r.height < window.innerHeight / 2)
        )
          return "scrolls";
      }
      return null;
    };
    const out: { el: string; right: number; width: number }[] = [];
    const offends = (el: Element) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && (r.right > width + 1 || r.left < -1) && !box(el);
    };
    for (const el of Array.from(document.body.querySelectorAll("*"))) {
      if (!offends(el)) continue;
      if (el.parentElement && offends(el.parentElement)) continue;
      const r = el.getBoundingClientRect();
      const id = el.getAttribute("data-testid");
      const cls = (el.getAttribute("class") ?? "").split(" ").slice(0, 5).join(".");
      const text = (el.textContent ?? "").trim().slice(0, 30);
      out.push({
        el: `${el.tagName.toLowerCase()}${id ? `[${id}]` : ""}${cls ? `.${cls}` : ""} "${text}"`,
        right: Math.round(r.right),
        width: Math.round(r.width),
      });
    }
    return { page: document.documentElement.scrollWidth - width, offenders: out.slice(0, 10) };
  });
}

/** Unroll the full-width areas the layout scrolls in, so a screenshot shows the whole screen. */
export async function unroll(page: Page) {
  await page.evaluate(() => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("*"))) {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      const scroller = ["auto", "scroll"].includes(s.overflowY) && r.width >= width - 2;
      const frame = s.overflowY === "hidden" && r.height >= height - 2 && r.width >= width - 2;
      if (scroller || frame) {
        el.style.overflow = "visible";
        el.style.height = "auto";
        el.style.maxHeight = "none";
      }
    }
    document.documentElement.style.height = "auto";
    document.body.style.height = "auto";
  });
}

/** An open dialog either fits the screen's height or scrolls inside itself, so nothing in it is
 * out of reach on a short screen (a phone held sideways). The dialogs that do not. */
export async function dialogsCut(page: Page) {
  return page.evaluate(() => {
    const out: string[] = [];
    for (const d of Array.from(
      document.querySelectorAll('[role="dialog"], [role="alertdialog"]'),
    )) {
      const r = d.getBoundingClientRect();
      if (r.height === 0 || r.bottom <= window.innerHeight + 1) continue;
      const scrolls = [d, ...Array.from(d.querySelectorAll("*"))].some((el) => {
        const s = getComputedStyle(el);
        return ["auto", "scroll"].includes(s.overflowY) && el.scrollHeight > el.clientHeight;
      });
      if (!scrolls)
        out.push(
          `${d.getAttribute("aria-label") ?? d.textContent?.trim().slice(0, 30)} (${Math.round(r.height)}px)`,
        );
    }
    return out;
  });
}
