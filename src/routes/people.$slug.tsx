import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { getDirector } from "@/data/identity";

export const Route = createFileRoute("/people/$slug")({
  head: ({ params }) => {
    const d = getDirector(params.slug);
    const title = `${d?.name ?? "Director"} — CreditIQ`;
    const description = d
      ? `${d.name}, ${d.role}, DIN ${d.din}: directorships, shareholding and disqualification status as held on the MCA DIN master.`
      : "Director record in the CreditIQ entity graph.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "profile" },
        { name: "twitter:card", content: "summary" },
      ],
    };
  },
  component: PersonDetail,
});

function PersonDetail() {
  const { slug } = Route.useParams();
  const d = getDirector(slug);
  if (!d) throw notFound();

  return (
    <div className="pb-10">
      <PageHeader
        eyebrow={`Director · DIN ${d.din}`}
        title={d.name}
        purpose={`${d.role} of Northwind Manufacturing Ltd, appointed ${d.appointed}. ${d.source}.`}
        actions={
          <Link
            to="/entities/$slug"
            params={{ slug: "northwind-manufacturing" }}
            className="flex h-8 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
          >
            Northwind Manufacturing Ltd
          </Link>
        }
      />
      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Other directorships" subtitle="Used to draw the group perimeter for this appraisal.">
          <ul className="divide-y divide-border">
            {d.otherDirectorships.map((o) => (
              <li key={o.name} className="flex flex-wrap items-center gap-4 px-4 py-2.5 text-[12.5px]">
                {o.entitySlug ? (
                  <Link
                    to="/entities/$slug"
                    params={{ slug: o.entitySlug }}
                    className="w-64 font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {o.name}
                  </Link>
                ) : (
                  <span className="w-64 font-medium text-foreground">{o.name}</span>
                )}
                <span className="text-muted-foreground">{o.role}</span>
                <span className="ml-auto text-muted-foreground">{o.status}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Particulars">
          <dl className="divide-y divide-border text-[12.5px]">
            {[
              ["DIN", d.din],
              ["Age", `${d.age}`],
              ["Nationality", d.nationality],
              ["Shareholding in borrower", d.shareholding],
              ["Disqualification", d.disqualified ? "Disqualified under s.164(2)" : "None on record"],
            ].map(([k, v]) => (
              <div key={k} className="px-4 py-2.5">
                <span className="field-label block">{k}</span>
                <span className="mt-0.5 block text-foreground tabular">{v}</span>
              </div>
            ))}
          </dl>
        </Panel>
      </div>
    </div>
  );
}
