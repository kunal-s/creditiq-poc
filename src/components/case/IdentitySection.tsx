import { createFileRoute } from "@tanstack/react-router";
import { FileText, Users } from "lucide-react";
import type { CaseDetail, FieldValue, LogicalDocument, Party } from "@/api/types";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { Panel } from "@/components/common/Panel";
import { ErrorState, LoadingBlock, QueryView } from "@/components/common/States";
import { SourceChip } from "@/components/common/SourceChip";
import { FieldValueButton } from "@/components/common/FieldValueButton";
import { ConfidenceChip } from "@/components/common/ConfidenceChip";
import { FieldStatusChip } from "@/components/documents/chips";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { useLabels } from "@/domain/cases";
import { pageRange, useCaseDocuments, useDocumentTypes } from "@/domain/documents";
import { fieldLabel, useFields, useParties } from "@/domain/extraction";

/** Document-type groups whose fields describe identity (F-15.6, "Identity"). */
const IDENTITY_GROUPS = new Set(["constitution", "registration", "kyc"]);

/** Identifiers and parties, each with its source (F-10, F-15). */
export function IdentitySection({ c }: { c: CaseDetail }) {
  return (
    <div className="grid gap-4 px-4 py-5 sm:px-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-4">
        <Identifiers c={c} />
        <Parties caseId={c.id} />
        <IdentityFields caseId={c.id} />
      </div>
      <div className="min-w-0 space-y-4">
        <PartySummary caseId={c.id} />
      </div>
    </div>
  );
}

function Identifiers({ c }: { c: CaseDetail }) {
  const labels = useLabels();
  const rows: { key: string; value: string | null }[] = [
    { key: "borrower", value: c.borrower },
    { key: "constitution", value: labels.constitution(c.constitution) },
    { key: "pan", value: c.pan },
    { key: "gstin", value: c.gstin },
    { key: "cin", value: c.cin },
    { key: "udyam", value: c.udyam },
  ];
  return (
    <Panel
      title={t("identity.identifiers")}
      subtitle={t("identity.identifiersHelp")}
      testId="identifiers"
    >
      <dl className="divide-y divide-border">
        {rows.map((row) => {
          const h = c.header[row.key];
          const proposed = h?.proposed;
          const edited = proposed && h?.value && proposed !== h.value;
          return (
            <div key={row.key} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5">
              <dt className="w-full shrink-0 text-[12px] text-muted-foreground sm:w-44">
                {t(`proposalField.${row.key}`)}
              </dt>
              <dd className="tabular min-w-0 flex-1 break-words text-[13px] text-foreground">
                {row.value ?? (
                  <span className="text-muted-foreground">{t("identity.notOnRecord")}</span>
                )}
                {edited && (
                  <span className="ml-2 text-[11px] text-muted-foreground">
                    {t("identity.proposed", { value: proposed })}
                  </span>
                )}
              </dd>
              <SourceChip caseId={c.id} source={h?.source} />
            </div>
          );
        })}
      </dl>
    </Panel>
  );
}

function Parties({ caseId }: { caseId: string }) {
  const parties = useParties(caseId);
  const documents = useCaseDocuments(caseId);
  return (
    <Panel
      title={t("identity.parties")}
      subtitle={t("identity.partiesHelp")}
      testId="parties"
      action={
        parties.data && (
          <span className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            <Users className="h-3.5 w-3.5" /> {t("identity.partyCount", { n: parties.data.length })}
          </span>
        )
      }
    >
      <div className={parties.data && parties.data.length > 0 ? "" : "p-4"}>
        <QueryView
          query={parties}
          compact
          loading={<LoadingBlock rows={3} className="border-0 p-0" />}
          isEmpty={(d) => d.length === 0}
          empty={{ title: t("identity.noParties"), description: t("identity.noPartiesHelp") }}
        >
          {(list) => (
            <ul className="divide-y divide-border">
              {list.map((p) => (
                <PartyRow key={p.id} caseId={caseId} party={p} documents={documents.data ?? []} />
              ))}
            </ul>
          )}
        </QueryView>
      </div>
    </Panel>
  );
}

function PartyRow({
  caseId,
  party,
  documents,
}: {
  caseId: string;
  party: Party;
  documents: LogicalDocument[];
}) {
  const viewer = useDocViewer();
  const types = useDocumentTypes();
  const kyc = (party.kyc_document_ids ?? [])
    .map((id) => documents.find((d) => d.id === id))
    .filter((d): d is LogicalDocument => Boolean(d));
  return (
    <li className="px-4 py-2.5" data-testid="party">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="min-w-0 break-words text-[13px] font-medium text-foreground">
          {party.name}
        </span>
        <span className="text-[12px] text-muted-foreground">{t(`partyRole.${party.role}`)}</span>
        {party.pan && (
          <span className="tabular text-[12px] text-muted-foreground">
            {t("identifier.pan")} {party.pan}
          </span>
        )}
        {party.din && (
          <span className="tabular text-[12px] text-muted-foreground">
            {t("identifier.din")} {party.din}
          </span>
        )}
        <span className="ml-auto">
          <SourceChip caseId={caseId} source={party.source} />
        </span>
      </div>
      {party.role !== "borrower" && (
        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11.5px]">
          <span className="text-muted-foreground">{t("identity.kyc")}</span>
          {kyc.length === 0 ? (
            <span className="text-flag-foreground">{t("identity.noKyc")}</span>
          ) : (
            kyc.map((doc) => (
              <button
                key={doc.id}
                type="button"
                onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
                className="inline-flex items-center gap-1 rounded border border-border bg-surface px-1.5 py-0.5 font-medium text-primary hover:bg-muted"
              >
                <FileText className="h-3 w-3" />
                {doc.classification?.types.map(types.name).join(" + ") ||
                  t("document.unclassified")}{" "}
                · {pageRange(doc)}
              </button>
            ))
          )}
        </div>
      )}
    </li>
  );
}

function IdentityFields({ caseId }: { caseId: string }) {
  const fields = useFields(caseId);
  const documents = useCaseDocuments(caseId);
  const types = useDocumentTypes();
  const identityDoc = (docId: string) => {
    const doc = documents.data?.find((d) => d.id === docId);
    return (doc?.classification?.types ?? []).some((id) => {
      const group = types.byId(id)?.group;
      return group ? IDENTITY_GROUPS.has(group) : false;
    });
  };
  return (
    <Panel
      title={t("identity.fields")}
      subtitle={t("identity.fieldsHelp")}
      testId="identity-fields"
    >
      <div className="p-0">
        {fields.isError ? (
          <div className="p-4">
            <ErrorState error={fields.error} compact />
          </div>
        ) : !fields.data || !documents.data ? (
          <div className="p-4">
            <LoadingBlock rows={3} className="border-0 p-0" />
          </div>
        ) : (
          <FieldList
            caseId={caseId}
            fields={fields.data.filter((f) => identityDoc(f.document_id))}
          />
        )}
      </div>
    </Panel>
  );
}

function FieldList({ caseId, fields }: { caseId: string; fields: FieldValue[] }) {
  if (fields.length === 0) {
    return (
      <p className="px-4 py-6 text-center text-[12.5px] text-muted-foreground">
        {t("identity.noFields")}
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border">
      {fields.map((f) => (
        <li key={f.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5">
          <span className="w-full shrink-0 text-[12px] text-muted-foreground sm:w-44">
            {fieldLabel(f.field)}
          </span>
          <span className="min-w-0 flex-1">
            <FieldValueButton caseId={caseId} field={f} />
          </span>
          <ConfidenceChip
            confidence={f.confidence}
            components={f.confidence_components}
            flagged={f.status === "in_review"}
          />
          <FieldStatusChip status={f.status} />
        </li>
      ))}
    </ul>
  );
}

function PartySummary({ caseId }: { caseId: string }) {
  const parties = useParties(caseId);
  if (!parties.data) return null;
  const people = parties.data.filter((p) => p.role !== "borrower");
  const withKyc = people.filter((p) => (p.kyc_document_ids ?? []).length > 0).length;
  return (
    <Panel title={t("identity.summary")}>
      <dl className="divide-y divide-border text-[12.5px]">
        <div className="flex justify-between gap-3 px-4 py-2">
          <dt className="text-muted-foreground">{t("identity.parties")}</dt>
          <dd className="tabular">{parties.data.length}</dd>
        </div>
        <div className="flex justify-between gap-3 px-4 py-2">
          <dt className="text-muted-foreground">{t("identity.withKyc")}</dt>
          <dd className="tabular">{withKyc}</dd>
        </div>
        <div className="flex justify-between gap-3 px-4 py-2">
          <dt className="text-muted-foreground">{t("identity.withoutKyc")}</dt>
          <dd className="tabular">{people.length - withKyc}</dd>
        </div>
      </dl>
    </Panel>
  );
}
