# Case assistant panel

A self-contained React chat panel for the case assistant service. It imports nothing from the host app: the host
passes the service address, a token getter, what is open (`context`) and every visible string (`labels`). It uses
Tailwind utility classes with the shadcn semantic tokens (`bg-background`, `text-foreground`, `border-border`,
`bg-muted`, `bg-primary`, `text-destructive`), so it follows the host's theme.

```tsx
<ChatPanel
  endpoint="http://localhost:8020"
  getToken={() => token}
  context={{ case_id: "1042" }}   // a different context is a different conversation
  labels={labels}                 // see ChatLabels
  suggestions={["Why was a document rejected?"]}
  storageKey="assistant"          // optional: remember the session id in this tab
  onClose={() => setOpen(false)}  // optional: shows a close button (Escape closes too)
/>
```

The panel fills its container and is meant to be docked beside the page, not shown in a dialog; how it is docked is the
host's business (CreditIQ: `src/components/shell/AssistantDock.tsx`, a resizable column the page makes room for).

`useCopilotChat` is the same logic without the markup. The service streams server-sent events from `POST /chat`; the
parser is in `src/sse.ts` and is tested with `npm run test:copilot-ui`. The panel itself is covered by the screen
tests. Text is rendered as plain text, never as HTML or markdown.
