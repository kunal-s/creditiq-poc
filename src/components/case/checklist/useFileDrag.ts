import { useEffect, useState } from "react";

const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");

/** Whether files are being dragged over the window, so the rows that take a drop can say so.
 * A drop that lands outside a row is ignored: the browser never opens the file in place of the
 * page. Handlers on an element (a row, the upload zone) run first. */
export function useFileDrag(): boolean {
  const [depth, setDepth] = useState(0);
  useEffect(() => {
    const enter = (e: DragEvent) => {
      if (hasFiles(e)) setDepth((d) => d + 1);
    };
    const leave = (e: DragEvent) => {
      if (hasFiles(e)) setDepth((d) => Math.max(0, d - 1));
    };
    const reset = () => setDepth(0);
    const over = (e: DragEvent) => {
      if (!hasFiles(e) || e.defaultPrevented) return;
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = "none";
    };
    const drop = (e: DragEvent) => {
      reset();
      if (hasFiles(e) && !e.defaultPrevented) e.preventDefault();
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    window.addEventListener("dragend", reset);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
      window.removeEventListener("dragend", reset);
    };
  }, []);
  return depth > 0;
}
