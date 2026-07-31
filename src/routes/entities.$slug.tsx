import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { DIRECTORS, ENTITIES, getEntity } from "@/data/identity";

export const Route = createFileRoute("/entities/$slug")({
  head: ({ params }) => {
    const e = getEntity(params.slug);
    const title = `${e?.name ?? "Entity"} — CreditIQ`;
    const description = e
      ? `${e.name}: CIN ${e.cin}, registered ${e.registeredOffice}, directors, group relationship and exposure with Continental Commercial Bank.`
      : "Entity record in the CreditIQ borrower master.";
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
  component: EntityDetail,
});

function EntityDetail() {
  const { slug } = Route.useParams();
  const e = getEntity(slug);
  if (!e) throw notFound();
  const directors = e.directorSlugs.map((s) => DIRECTORS.find((d) => d.slug === s)!);
  const others = ENTITIES.filter((x) => x.slug !== e.slug);

  return (
    <div className="pb-10">
      <PageHeader
        eyebrow={`${e.relationship} · ${e.sector}`}
        title={e.name}
        purpose={`${e.status} · Incorporated ${e.incorporated} · ${e.registeredOffice}`}
        actions={
          <Link
            to="/appraisals/$id/identity"
            params={{ id: "CAM-2026-0418" }}
            className="flex h-8 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
          >
            Back to entity resolution
          </Link>
        }
      />
      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-4">
          <Panel title="Registry identity">
            <dl className="divide-y divide-border text-[13px]">
              {[
                ["CIN", e.cin],
                ["PAN", e.panMasked],
                ["GSTIN", e.gstin],
                ["LEI", e.lei ? `${e.lei} · valid to ${e.leiValidTo}` : (e.leiNote ?? "Not obtained")],
                ["Authorised capital", e.authorisedCapital],
                ["Paid-up capital", e.paidUpCapital],
                ["Statutory filings", e.lastFilingAgm],
              ].map(([k, v]) => (
                <div key={k} className="flex gap-4 px-4 py-2.5">
                  <dt className="w-44 shrink-0 text-muted-foreground">{k}</dt>
                  <dd className="min-w-0 flex-1 text-foreground tabular">{v}</dd>
                </div>
              ))}
            </dl>
            {!e.lei && (
              <p className="flex items-center gap-2 border-t border-border bg-flag-soft px-4 py-2.5 text-[12px] text-flag-foreground">
                <AlertTriangle className="h-3.5 w-3.5" /> LEI not obtained — recorded as an open item on
                appraisal CAM-2026-0418.
              </p>
            )}
          </Panel>

          <Panel title="Directors">
            <ul className="divide-y divide-border">
              {directors.map((d) => (
                <li key={d.slug} className="flex flex-wrap items-center gap-4 px-4 py-2.5 text-[12.5px]">
                  <Link
                    to="/people/$slug"
                    params={{ slug: d.slug }}
                    className="w-52 font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {d.name}
                  </Link>
                  <span className="text-muted-foreground">{d.role}</span>
                  <span className="ml-auto text-muted-foreground tabular">DIN {d.din}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Exposure with this bank">
            <p className="px-4 py-3 text-[12.5px] leading-relaxed text-foreground">{e.exposure}</p>
          </Panel>
          <Panel title="Group perimeter">
            <ul className="divide-y divide-border">
              {others.map((o) => (
                <li key={o.slug} className="px-4 py-2.5">
                  <Link
                    to="/entities/$slug"
                    params={{ slug: o.slug }}
                    className="text-[12.5px] font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {o.name}
                  </Link>
                  <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
                    {o.relationship} · shares director Rajesh Malhotra
                  </span>
                </li>
              ))}
            </ul>
          </Panel>
          {e.appraisalId && (
            <div className="rounded border border-border bg-surface p-4 text-[12.5px] text-muted-foreground">
              Live appraisal{" "}
              <Link
                to="/appraisals/$id/identity"
                params={{ id: e.appraisalId }}
                className="font-medium text-primary hover:underline"
              >
                {e.appraisalId}
              </Link>{" "}
              is in progress for this entity.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
