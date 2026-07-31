import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const Route = createFileRoute("/admin/users")({
  head: () => ({
    meta: [
      { title: "Users and Roles — CreditIQ" },
      { name: "description", content: "Separate who may author a memo from who may approve it, and keep that separation provable to an examiner." },
      { property: "og:title", content: "Users and Roles — CreditIQ" },
      { property: "og:description", content: "Separate who may author a memo from who may approve it, and keep that separation provable to an examiner." },
    ],
  }),
  component: UsersRoles,
});

function UsersRoles() {
  return (
    <PlaceholderPage
      eyebrow="Admin"
      title="Users and Roles"
      purpose="Separate who may author a memo from who may approve it, and keep that separation provable to an examiner."
      aiAction="Copilot reviews role assignments and flags any user whose permissions breach segregation of duties."
      facts={[
            { label: "Users in West Region", value: "31 users — 14 analysts, 9 relationship managers, 6 credit managers, 2 administrators" },
            { label: "Segregation rule", value: "An analyst can never approve a memo they authored" },
            { label: "Last access review", value: "Completed 30 June 2026 by Ananya Deshmukh" },
      ]}
    />
  );
}
