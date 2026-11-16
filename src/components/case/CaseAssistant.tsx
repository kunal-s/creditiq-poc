import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { ChatPanel, type ChatLabels, type Tone } from "@copilot-ui";
import { useAssistantDock } from "@/components/shell/AssistantDock";
import { t } from "@/config/terminology";
import { sessionToken, useCan } from "@/domain/session";

// The assistant for the open appraisal: a launcher, and a panel docked beside the page (shell/AssistantDock) so the
// appraisal stays visible and usable while it is open. The panel itself is the reusable one in
// services/copilot/ui; everything it shows is worded here, from the terminology file. It appears only when the
// assistant service's address is configured (VITE_COPILOT_URL).

const ASSISTANT_URL = import.meta.env["VITE_COPILOT_URL"] as string | undefined;

// How the status words the assistant returns are shown (these are the engine's own values, not text for the user).
const STATUS_TONES: Record<string, Tone> = {
  rejected: "danger",
  exception: "warning",
  in_exception: "warning",
  unclassified: "warning",
};

// An empty conversation shows only the open tab's starting questions: no intro, no note.
function assistantLabels(): ChatLabels {
  return {
    title: t("assistant.title"),
    placeholder: t("assistant.placeholder"),
    send: t("assistant.send"),
    newConversation: t("assistant.newConversation"),
    close: t("assistant.close"),
    copy: t("assistant.copy"),
    copied: t("assistant.copied"),
    hint: t("assistant.hint"),
    startingActions: t("assistant.startingActions"),
    thinking: t("assistant.thinking"),
    sources: t("assistant.sources"),
    columns: {
      document: t("assistant.column.document"),
      status: t("assistant.column.status"),
      reason: t("assistant.column.reason"),
      rule: t("assistant.column.rule"),
      period: t("assistant.column.period"),
      inputs: t("assistant.column.inputs"),
      working: t("assistant.column.working"),
      value: t("assistant.column.value"),
    },
    action: {
      fields: {
        to: t("assistant.action.field.to"),
        subject: t("assistant.action.field.subject"),
        body: t("assistant.action.field.body"),
      },
      confirm: t("assistant.action.confirm"),
      cancel: t("assistant.action.cancel"),
      working: t("assistant.action.working"),
    },
    errors: {
      signedOut: t("assistant.error.signedOut"),
      unavailable: t("assistant.error.unavailable"),
      network: t("assistant.error.network"),
      tooLong: t("assistant.error.tooLong"),
      notDone: t("assistant.error.notDone"),
    },
  };
}

// The starting questions follow the open tab: the document questions on Files, the ratios on Financials and Policy.
// Other tabs offer none; any question can still be typed. The ratios need the financials (output.read).
const DOCUMENT_SUGGESTIONS = ["suggestionRejected", "suggestionProblems", "suggestionDraft"];
const RATIO_SUGGESTIONS = [
  "suggestionRatio",
  "suggestionDebtEbitda",
  "suggestionRoe",
  "suggestionReceivableDays",
];

function suggestionKeys(page: string | undefined, readsFinancials: boolean): string[] {
  if (page === "documents") return DOCUMENT_SUGGESTIONS;
  if (page === "policy" && readsFinancials) return RATIO_SUGGESTIONS;
  return [];
}

export function CaseAssistant({
  caseId,
  borrower,
  page,
}: {
  caseId: string;
  borrower: string;
  /** The open tab's key (nav.ts CASE_TABS), which decides the starting questions. */
  page?: string | undefined;
}) {
  const allowed = useCan("case.read");
  const readsFinancials = useCan("output.read"); // the ratios are worked out from the spread, which needs it
  const dock = useAssistantDock();
  const labels = useMemo(() => assistantLabels(), []);
  const suggestions = useMemo(
    () => suggestionKeys(page, readsFinancials).map((key) => t(`assistant.${key}`)),
    [page, readsFinancials],
  );
  const enabled = Boolean(ASSISTANT_URL) && allowed && dock !== null;
  const setAvailable = dock?.setAvailable;
  useEffect(() => {
    if (!enabled || !setAvailable) return;
    setAvailable(true);
    return () => setAvailable(false);
  }, [enabled, setAvailable]);

  // The panel stays mounted once opened, so closing it keeps the conversation and what was typed.
  const [opened, setOpened] = useState(false);
  const open = dock?.open ?? false;
  useEffect(() => {
    if (open) setOpened(true);
  }, [open]);

  if (!enabled || !ASSISTANT_URL || !dock) return null;
  return (
    <>
      {dock.node &&
        opened &&
        createPortal(
          <ChatPanel
            endpoint={ASSISTANT_URL}
            getToken={sessionToken}
            context={{ case_id: caseId }}
            labels={labels}
            suggestions={suggestions}
            storageKey="creditiq.assistant"
            contextLabel={t("assistant.context", { borrower, id: caseId })}
            tones={STATUS_TONES}
            onClose={() => dock.setOpen(false)}
            autoFocus={open}
          />,
          dock.node,
        )}
    </>
  );
}
