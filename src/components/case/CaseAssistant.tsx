import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { ChatPanel, type ChatLabels, type Tone } from "@copilot-ui";
import { useAssistantDock } from "@/components/shell/AssistantDock";
import { t } from "@/config/terminology";
import { sessionToken, useCan, useSession } from "@/domain/session";

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

/** "Good morning, Ananya." by the hour of the user's own clock: a greeting, nothing more. */
function greeting(name: string): string {
  const hour = new Date().getHours();
  const part = hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
  return t(`assistant.greeting.${part}`, { name });
}

function assistantLabels(name: string): ChatLabels {
  return {
    title: t("assistant.title"),
    placeholder: t("assistant.placeholder"),
    send: t("assistant.send"),
    newConversation: t("assistant.newConversation"),
    close: t("assistant.close"),
    copy: t("assistant.copy"),
    copied: t("assistant.copied"),
    hint: t("assistant.hint"),
    intro: name ? `${greeting(name)} ${t("assistant.intro")}` : t("assistant.intro"),
    startingActions: t("assistant.startingActions"),
    groundingTitle: t("assistant.groundingTitle"),
    grounding: t("assistant.grounding"),
    thinking: t("assistant.thinking"),
    sources: t("assistant.sources"),
    columns: {
      document: t("assistant.column.document"),
      status: t("assistant.column.status"),
      reason: t("assistant.column.reason"),
      rule: t("assistant.column.rule"),
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

export function CaseAssistant({ caseId, borrower }: { caseId: string; borrower: string }) {
  const allowed = useCan("case.read");
  const dock = useAssistantDock();
  const firstName = useSession()?.user.name.split(" ")[0] ?? "";
  const labels = useMemo(() => assistantLabels(firstName), [firstName]);
  const suggestions = useMemo(
    () => [
      t("assistant.suggestionRejected"),
      t("assistant.suggestionProblems"),
      t("assistant.suggestionDraft"),
    ],
    [],
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
