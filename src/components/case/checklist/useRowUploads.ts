import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { ChecklistItemState, ChecklistStatus, LogicalDocument } from "@/api/types";
import { t } from "@/config/terminology";
import { useChecklist, type Band } from "@/domain/checklist";
import { useCaseRegister, useDocumentTypes, useUpload } from "@/domain/documents";
import { errorKind } from "@/domain/errors";
import { useCan } from "@/domain/session";

// Files sent from a requirement's row (picked or dropped), for every row of the checklist at
// once. The content of a file decides where it counts: while it is read the row says so, then
// what it was read as and which requirement it now counts toward, or that it waits for a person,
// or why it was turned away. The state lives above the rows, so a row keeps its outcome lines
// when it is filtered out and back, or its status changes.

export type OutcomeState = "reading" | "counted" | "unasked" | "unidentified" | "turnedAway";

export type Outcome = {
  id: string;
  name: string;
  state: OutcomeState;
  text: string;
  /** The file's first document, for the reading track. */
  doc: LogicalDocument | undefined;
  /** The requirements the file now counts toward. */
  counts: string[];
};

/** Where a row stood when a file was sent from it: it stays there until the page is left, so
 * the outcome is read where the file was dropped. */
export type Pin = { band: Band; status: ChecklistStatus };

type Sent = { id: string; name: string };

export function useRowUploads(caseId: string) {
  const can = useCan("document.upload");
  const upload = useUpload(caseId);
  const { files, documents } = useCaseRegister(caseId);
  const checklist = useChecklist(caseId);
  const refetchChecklist = checklist.refetch;
  const types = useDocumentTypes();
  const [sent, setSent] = useState<Record<string, Sent[]>>({});
  const [pending, setPending] = useState<ReadonlySet<string>>(() => new Set());
  const [pinned, setPinned] = useState<Record<string, Pin>>({});
  // When each sent file's documents first appeared: its outcome waits for a checklist read after
  // that, so it never says "no requirement asks for it" from a checklist read before the file.
  const [seenAt, setSeenAt] = useState<Record<string, number>>({});

  useEffect(() => {
    const all = Object.values(sent).flat();
    const fresh = all.filter(
      (f) => seenAt[f.id] === undefined && (documents.data ?? []).some((d) => d.file_id === f.id),
    );
    if (fresh.length === 0) return;
    const at = documents.dataUpdatedAt;
    const id = setTimeout(() => {
      setSeenAt((prev) => ({ ...prev, ...Object.fromEntries(fresh.map((f) => [f.id, at])) }));
      // Read the checklist once more, so the outcome rests on a read made after the documents.
      void refetchChecklist();
    }, 0);
    return () => clearTimeout(id);
  }, [sent, seenAt, documents.data, documents.dataUpdatedAt, refetchChecklist]);

  const { mutateAsync } = upload;
  const send = useCallback(
    async (item: ChecklistItemState, band: Band, list: File[]) => {
      if (list.length === 0 || !can) return;
      const itemId = item.item_id;
      setPinned((prev) =>
        prev[itemId] ? prev : { ...prev, [itemId]: { band, status: item.status } },
      );
      setPending((prev) => new Set(prev).add(itemId));
      try {
        const result = await mutateAsync(list);
        // Added to what the row sent before (one file a director, say), so each keeps its line.
        setSent((prev) => {
          const before = prev[itemId] ?? [];
          const added = result.files
            .filter((f) => !before.some((s) => s.id === f.id))
            .map((f) => ({ id: f.id, name: f.original_name }));
          return { ...prev, [itemId]: [...before, ...added] };
        });
        toast.success(t("documents.uploaded", { n: result.files.length }));
      } catch (error) {
        toast(t(`state.${errorKind(error)}.title`), {
          description: t(`state.${errorKind(error)}.description`),
        });
      } finally {
        setPending((prev) => {
          const next = new Set(prev);
          next.delete(itemId);
          return next;
        });
      }
    },
    [can, mutateAsync],
  );

  // Where each file sent from a row stands now: still being read, or what it came to.
  const outcomesFor = (itemId: string): Outcome[] =>
    (sent[itemId] ?? []).map(({ id, name }) => {
      const file = (files.data ?? []).find((f) => f.id === id);
      const docs = (documents.data ?? []).filter((d) => d.file_id === id);
      const base = { id, name, doc: docs[0], counts: [] as string[] };
      if (file && file.status !== "registered" && docs.length === 0)
        return { ...base, state: "turnedAway" as const, text: file.reason ?? "" };
      const settled = seenAt[id] !== undefined && checklist.dataUpdatedAt > seenAt[id];
      if (!file || docs.length === 0 || !settled)
        return { ...base, state: "reading" as const, text: "" };
      const typed = docs.flatMap((d) => d.classification?.types ?? []).map(types.name);
      const counted = (checklist.data?.items ?? []).filter((i) =>
        docs.some((d) => (i.document_ids ?? []).includes(d.id)),
      );
      if (typed.length === 0) return { ...base, state: "unidentified" as const, text: "" };
      return {
        ...base,
        counts: counted.map((i) => i.item_id),
        state: counted.length > 0 ? ("counted" as const) : ("unasked" as const),
        text: t(counted.length > 0 ? "journey.outcome.counted" : "journey.outcome.unasked", {
          type: typed.join(" + "),
          items: counted.map((i) => i.name).join(", "),
        }),
      };
    });

  return {
    can,
    pendingFor: (itemId: string) => pending.has(itemId),
    send,
    outcomesFor,
    pinned,
  };
}

export type RowUploads = ReturnType<typeof useRowUploads>;
