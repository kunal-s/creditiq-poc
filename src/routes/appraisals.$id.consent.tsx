import { createFileRoute, Link, notFound, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Building2, CalendarClock, Check, Lock, MessageCircle, ShieldCheck, X } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { getAppraisal } from "@/data/seed";
import { CONSENT_ACCOUNTS, CONSENT_WINDOW, setAcqState, useAcqState } from "@/data/acquisition";

export const Route = createFileRoute("/appraisals/$id/consent")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Consent journey — ${a?.borrower ?? "Borrower"} — CreditIQ`;
    const description =
      "Borrower-facing consent for sharing bank-account data with Continental Commercial Bank: who is asking, what is shared, for what purpose, for how long, and how to revoke it.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary" },
      ],
    };
  },
  component: ConsentJourney,
});

function ConsentJourney() {
  const { id } = Route.useParams();
  const a = getAppraisal(id);
  if (!a) throw notFound();
  const acq = useAcqState();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string[]>(CONSENT_ACCOUNTS.map((x) => x.id));

  const toggle = (accId: string) =>
    setSelected((s) => (s.includes(accId) ? s.filter((x) => x !== accId) : [...s, accId]));

  return (
    <div>
      <PageHeader
        eyebrow={`Appraisal ${a.id} · Consent`}
        title="Consent journey"
        purpose="What the borrower sees on their own device. Nothing is fetched from either bank until this is approved, and it can be withdrawn at any time."
        actions={
          <Link
            to="/appraisals/$id/data"
            params={{ id: a.id }}
            className="flex h-9 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
          >
            Back to acquisition console
          </Link>
        }
      />

      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="mx-auto w-full max-w-[560px] rounded border border-border bg-surface shadow-sm">
          <div className="flex items-center gap-2 border-b border-border bg-surface-muted px-4 py-2.5 text-[11.5px] text-muted-foreground">
            <Lock className="h-3.5 w-3.5" />
            Secure borrower link · {acq.consentRef} · expires 24 hours after it is sent
          </div>

          <div className="px-5 py-5">
            <p className="field-label">Request for your bank information</p>
            <h2 className="mt-1 text-[17px] font-semibold text-foreground">
              Continental Commercial Bank is asking to see transactions on two of your accounts
            </h2>
            <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
              You are {a.borrower}. Your bank is reviewing an enhancement of your working capital
              limit. To check the money that actually moves through your accounts, they are asking to
              read your bank statements electronically instead of you emailing PDFs.
            </p>

            <dl className="mt-4 divide-y divide-border rounded border border-border">
              <div className="flex gap-3 px-3 py-2.5 text-[12.5px]">
                <dt className="w-32 shrink-0 text-muted-foreground">Who is asking</dt>
                <dd>
                  Continental Commercial Bank, Corporate and Commercial Credit, West Region ·
                  requested by Elena Rossi, Credit Analyst
                </dd>
              </div>
              <div className="flex gap-3 px-3 py-2.5 text-[12.5px]">
                <dt className="w-32 shrink-0 text-muted-foreground">What is shared</dt>
                <dd>
                  Transaction history and balances for the two accounts below. No passwords, no
                  ability to move money, no access to any other account.
                </dd>
              </div>
              <div className="flex gap-3 px-3 py-2.5 text-[12.5px]">
                <dt className="w-32 shrink-0 text-muted-foreground">Why</dt>
                <dd>
                  This credit appraisal only — {a.id}, {a.proposal}
                </dd>
              </div>
              <div className="flex gap-3 px-3 py-2.5 text-[12.5px]">
                <dt className="w-32 shrink-0 text-muted-foreground">For how long</dt>
                <dd>
                  Statements covering {CONSENT_WINDOW}, fetched once. The permission itself ends when
                  the appraisal is decided, and no later than 31 October 2026.
                </dd>
              </div>
            </dl>

            <p className="mt-4 field-label">Accounts in this request</p>
            <ul className="mt-1.5 space-y-2">
              {CONSENT_ACCOUNTS.map((acc) => (
                <li
                  key={acc.id}
                  className="flex items-start gap-3 rounded border border-border px-3 py-2.5"
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(acc.id)}
                    onChange={() => toggle(acc.id)}
                    className="mt-0.5 h-4 w-4 accent-[var(--color-primary)]"
                    aria-label={`Share ${acc.bank} ${acc.masked}`}
                  />
                  <div className="min-w-0 flex-1 text-[12.5px]">
                    <p className="font-medium text-foreground">
                      {acc.bank} · {acc.masked}
                    </p>
                    <p className="text-[11.5px] text-muted-foreground">
                      {acc.type} · {acc.branch} · {acc.note}
                    </p>
                  </div>
                  <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                </li>
              ))}
            </ul>

            <div className="mt-4 flex items-start gap-2 rounded border border-border bg-surface-muted px-3 py-2.5 text-[12px] text-muted-foreground">
              <CalendarClock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              You can withdraw this permission whenever you like, from your Account Aggregator app or
              by telling your relationship manager. Withdrawing it stops any further access; it does
              not delete statements already shared for this appraisal.
            </div>

            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                disabled={selected.length === 0}
                onClick={() => {
                  setAcqState({ bank: "consented" });
                  toast("Consent approved", {
                    description:
                      "Both accounts fetched under CONS-2026-0418-A. The bank-data row is now received with provenance 'consent'.",
                  });
                  navigate({ to: "/appraisals/$id/data", params: { id: a.id } });
                }}
                className="flex h-10 flex-1 items-center justify-center gap-1.5 rounded bg-primary px-4 text-[13px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                <Check className="h-4 w-4" /> Approve and share
              </button>
              <button
                type="button"
                onClick={() => {
                  setAcqState({ bank: "declined" });
                  toast("Consent declined", {
                    description:
                      "No bank data was fetched. Statements can be supplied through the manual fallback and will be marked provenance 'fallback'.",
                  });
                  navigate({ to: "/appraisals/$id/upload", params: { id: a.id } });
                }}
                className="flex h-10 items-center justify-center gap-1.5 rounded border border-border bg-surface px-4 text-[13px] font-medium text-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" /> Decline
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded border border-border bg-surface p-4">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold">
              <MessageCircle className="h-3.5 w-3.5 text-primary" /> What this means
            </p>
            <ul className="mt-2 space-y-2 text-[12.5px] leading-relaxed text-muted-foreground">
              <li>You are letting your bank read statements. You are not giving anyone your login.</li>
              <li>Only the two accounts you tick are shared, and only for the dates shown.</li>
              <li>Nobody can take money out of your accounts with this permission.</li>
              <li>If you say no, you can still send statements yourself; it just takes longer.</li>
            </ul>
          </div>

          <div className="rounded border border-border bg-surface p-4 text-[12.5px] leading-relaxed text-muted-foreground">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold text-foreground">
              <ShieldCheck className="h-3.5 w-3.5 text-primary" /> Analyst view
            </p>
            <p className="mt-1.5">
              Current state:{" "}
              <span className="font-medium text-foreground">
                {acq.bank === "consented"
                  ? "approved — data received under consent"
                  : acq.bank === "declined"
                    ? "declined — fallback required"
                    : acq.bank === "fallback"
                      ? "declined, statements received by fallback"
                      : acq.bank === "requested"
                        ? "request sent, awaiting borrower"
                        : "request not yet sent"}
              </span>
              . The consent artefact, its purpose code and its expiry are retained in the{" "}
              <Link to="/audit" className="font-medium text-primary hover:underline">
                audit trail
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
