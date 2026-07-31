import { Link, notFound } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";
import { getAppraisal, ATTENTION } from "@/data/seed";

export function StepPage({
  id,
  title,
  purpose,
  aiAction,
}: {
  id: string;
  title: string;
  purpose: string;
  aiAction: string;
}) {
  const a = getAppraisal(id);
  if (!a) throw notFound();
  const flags = ATTENTION.filter((x) => x.appraisalId === a.id && x.kind === "discrepancy");

  return (
    <PlaceholderPage
      eyebrow={`Appraisal ${a.id} · ${title}`}
      title={`${title} — ${a.borrower}`}
      purpose={purpose}
      aiAction={aiAction}
      facts={[
        { label: "Proposal", value: a.proposal },
        { label: "Facilities", value: a.facilities },
        { label: "Identifiers", value: `PAN ${a.pan} · GSTIN ${a.gstin}` },
        { label: "Current stage", value: `${a.stage} · ${a.branch}` },
        { label: "Analyst / RM", value: `${a.analyst} · ${a.rm}` },
        { label: "Risk rating", value: `${a.rating} (${a.ratingLabel})` },
        {
          label: "Open discrepancies",
          value:
            flags.length === 0 ? (
              "None outstanding"
            ) : (
              <ul className="space-y-1">
                {flags.map((f) => (
                  <li key={f.id}>
                    <Link
                      to="/appraisals/$id/cross-verification"
                      params={{ id: a.id }}
                      className="text-flag-foreground hover:underline"
                    >
                      {f.id} — {f.title}
                    </Link>
                  </li>
                ))}
              </ul>
            ),
        },
      ]}
    />
  );
}