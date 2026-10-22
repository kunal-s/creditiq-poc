import { Eye } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { toast } from "sonner";
import type { TxnCategoryRef, TxnRow, TxnSummary } from "@/api/types";
import { Chip, Panel, type Tone } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { evidenceRequest, useDocViewer } from "@/components/docviewer/DocViewer";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/config/terminology";
import { refusal } from "@/domain/errors";
import { useCan } from "@/domain/session";
import {
  monthLabel,
  rupees,
  useCategorise,
  useClearCategory,
  useTxns,
  type TxnFilter,
} from "@/domain/transactions";
import { cn } from "@/lib/utils";

const PAGE = 100;
const selectClass =
  "h-8 min-w-0 rounded border border-border bg-surface px-2 text-[12.5px] text-foreground outline-none focus:border-primary/60 focus:ring-2 focus:ring-primary/20";

const METHOD_TONE: Record<TxnRow["method"], Tone> = {
  rule: "muted",
  model: "info",
  manual: "primary",
};

/** The transactions, filtered; each row says how it was read and opens its page. A person with the right can file a
 * row under another category, with a reason. The screen arranges; the engine decides nothing here. */
export function TransactionsTable({ caseId, summary }: { caseId: string; summary: TxnSummary }) {
  const [category, setCategory] = useState("");
  const [month, setMonth] = useState("");
  const [account, setAccount] = useState("");
  const [show, setShow] = useState<"all" | "open" | "person">("all");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const [filing, setFiling] = useState<TxnRow | null>(null);
  const q = useDeferredValue(search.trim());
  const filter: TxnFilter = {
    limit,
    ...(category ? { category } : {}),
    ...(month ? { month } : {}),
    ...(account ? { account } : {}),
    ...(show === "open" ? { needs_review: true } : {}),
    ...(show === "person" ? { status: "manual" } : {}),
    ...(q ? { q } : {}),
  };
  const list = useTxns(caseId, filter);
  const viewer = useDocViewer();
  const canFile = useCan("review.decide");
  const label = (id: string) => (summary.catalogue ?? []).find((c) => c.id === id)?.label ?? id;
  const narrow =
    <T,>(set: (v: T) => void) =>
    (v: T) => {
      set(v);
      setLimit(PAGE);
    };

  return (
    <Panel
      title={t("banking.txn.title")}
      subtitle={
        list.data
          ? t("banking.txn.subtitle", { shown: list.data.items.length, total: list.data.total })
          : undefined
      }
      testId="banking-transactions"
    >
      <div className="flex flex-wrap items-end gap-3 border-b border-border px-4 py-3">
        <label className="block">
          <span className="field-label">{t("banking.txn.filters.category")}</span>
          <select
            className={cn(selectClass, "mt-1 block")}
            value={category}
            onChange={(e) => narrow(setCategory)(e.target.value)}
            data-testid="banking-filter-category"
          >
            <option value="">{t("banking.txn.filters.all")}</option>
            {summary.categories.map((c) => (
              <option key={c.category} value={c.category}>
                {c.label} ({c.count})
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="field-label">{t("banking.txn.filters.month")}</span>
          <select
            className={cn(selectClass, "mt-1 block")}
            value={month}
            onChange={(e) => narrow(setMonth)(e.target.value)}
            data-testid="banking-filter-month"
          >
            <option value="">{t("banking.txn.filters.all")}</option>
            {summary.months.map((m) => (
              <option key={m.month} value={m.month}>
                {monthLabel(m.month)}
              </option>
            ))}
          </select>
        </label>
        {summary.accounts.length > 1 && (
          <label className="block">
            <span className="field-label">{t("banking.txn.filters.account")}</span>
            <select
              className={cn(selectClass, "mt-1 block")}
              value={account}
              onChange={(e) => narrow(setAccount)(e.target.value)}
              data-testid="banking-filter-account"
            >
              <option value="">{t("banking.txn.filters.all")}</option>
              {summary.accounts.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="block">
          <span className="field-label">{t("banking.txn.filters.status")}</span>
          <select
            className={cn(selectClass, "mt-1 block")}
            value={show}
            onChange={(e) => narrow(setShow)(e.target.value as typeof show)}
            data-testid="banking-filter-status"
          >
            <option value="all">{t("banking.txn.filters.statusAll")}</option>
            <option value="open">
              {t("banking.txn.filters.statusOpen")} ({summary.unsettled})
            </option>
            <option value="person">
              {t("banking.txn.filters.statusPerson")} ({summary.by_person})
            </option>
          </select>
        </label>
        <label className="block min-w-[12rem] flex-1">
          <span className="field-label">{t("banking.txn.filters.search")}</span>
          <input
            type="search"
            className={cn(selectClass, "mt-1 block w-full")}
            value={search}
            onChange={(e) => narrow(setSearch)(e.target.value)}
            data-testid="banking-filter-search"
          />
        </label>
      </div>

      {list.isPending ? (
        <LoadingBlock rows={4} className="border-0" />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} compact />
      ) : list.data.items.length === 0 ? (
        <p
          className="px-4 py-6 text-center text-[13px] text-muted-foreground"
          data-testid="banking-empty-list"
        >
          {t("banking.txn.empty")}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[46rem] text-[12.5px]" data-testid="banking-table">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-2 font-medium">{t("banking.txn.date")}</th>
                <th className="px-2 py-2 font-medium">{t("banking.txn.narration")}</th>
                <th className="px-2 py-2 text-right font-medium">{t("banking.txn.debit")}</th>
                <th className="px-2 py-2 text-right font-medium">{t("banking.txn.credit")}</th>
                <th className="px-2 py-2 font-medium">{t("banking.txn.category")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((r) => (
                <tr
                  key={r.txn_id}
                  className={cn(
                    "border-b border-border/60 align-top",
                    r.needs_review && "bg-flag-soft/40",
                  )}
                  data-testid="banking-txn"
                  data-category={r.category}
                  data-method={r.method}
                  data-open={r.needs_review ? "true" : "false"}
                >
                  <td className="tabular whitespace-nowrap px-4 py-2 text-muted-foreground">
                    {r.date ?? "—"}
                  </td>
                  <td className="max-w-[22rem] px-2 py-2">
                    <p className="break-words text-foreground">{r.narration}</p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-1 text-[11.5px] text-muted-foreground">
                      {r.counterparty && <span>{r.counterparty}</span>}
                      {(r.flags ?? []).map((f) => (
                        <span key={f} className="rounded border border-border px-1">
                          {t(`banking.txn.flag.${f}`)}
                        </span>
                      ))}
                    </p>
                    {r.reason && (
                      <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                        {t("banking.txn.reason", { reason: r.reason })}
                      </p>
                    )}
                  </td>
                  <td className="tabular px-2 py-2 text-right">{r.debit ? rupees(r.debit) : ""}</td>
                  <td className="tabular px-2 py-2 text-right">
                    {r.credit ? rupees(r.credit) : ""}
                  </td>
                  <td className="px-2 py-2">
                    <p className="flex flex-wrap items-center gap-1.5">
                      <span
                        className="font-medium text-foreground"
                        data-testid="banking-txn-category"
                      >
                        {r.category_label}
                      </span>
                      {r.needs_review ? (
                        <Chip tone="flag">{t("banking.counts.open")}</Chip>
                      ) : (
                        <Chip tone={METHOD_TONE[r.method]}>
                          {t(`banking.txn.method.${r.method}`)}
                        </Chip>
                      )}
                    </p>
                    {r.needs_review && r.candidates?.[0] && (
                      <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                        {t("banking.txn.suggested", { label: label(r.candidates[0]!) })}
                      </p>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-right">
                    <span className="inline-flex items-center gap-2">
                      {canFile && (
                        <button
                          type="button"
                          onClick={() => setFiling(r)}
                          className="text-[12px] font-medium text-primary hover:underline"
                          data-testid="banking-file"
                        >
                          {t(r.method === "manual" ? "banking.txn.change" : "banking.txn.file")}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          const request = evidenceRequest(caseId, r.evidence ?? []);
                          if (request) viewer.open(request);
                        }}
                        className="inline-flex items-center text-muted-foreground hover:text-primary"
                        aria-label={t("banking.txn.page")}
                        title={t("banking.txn.page")}
                        data-testid="banking-txn-page"
                      >
                        <Eye className="h-4 w-4" aria-hidden />
                      </button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.data.items.length < list.data.total && (
            <div className="border-t border-border px-4 py-2.5 text-center">
              <button
                type="button"
                onClick={() => setLimit((n) => n + PAGE)}
                className="text-[12.5px] font-medium text-primary hover:underline"
                data-testid="banking-more"
              >
                {t("banking.txn.more")}
              </button>
            </div>
          )}
        </div>
      )}
      {filing && (
        <FileDialog
          caseId={caseId}
          row={filing}
          catalogue={(summary.catalogue ?? []).filter(
            (c) => c.direction === (filing.credit ? "credit" : "debit"),
          )}
          onClose={() => setFiling(null)}
        />
      )}
    </Panel>
  );
}

/** File one transaction under a category, with the reason; or take a person's decision off it. */
function FileDialog({
  caseId,
  row,
  catalogue,
  onClose,
}: {
  caseId: string;
  row: TxnRow;
  catalogue: TxnCategoryRef[];
  onClose: () => void;
}) {
  const [category, setCategory] = useState(
    row.method === "manual" ? row.category : (row.candidates?.[0] ?? ""),
  );
  const [reason, setReason] = useState("");
  const file = useCategorise(caseId);
  const clear = useClearCategory(caseId);
  const refused = file.isError ? refusal(file.error) : clear.isError ? refusal(clear.error) : null;
  const ready = category !== "" && reason.trim().length >= 3;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg" data-testid="banking-file-dialog">
        <DialogHeader>
          <DialogTitle>{t("banking.file.title")}</DialogTitle>
          <DialogDescription>
            {row.account} · {row.date ?? "—"} · {rupees(row.credit || row.debit)}
          </DialogDescription>
        </DialogHeader>
        <p className="rounded border border-border bg-surface-muted px-3 py-2 text-[12.5px] text-foreground">
          {row.narration}
        </p>
        <label className="block">
          <span className="field-label">{t("banking.file.category")}</span>
          <select
            className={cn(selectClass, "mt-1 block w-full")}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            data-testid="banking-file-category"
          >
            <option value="">{t("banking.file.choose")}</option>
            {catalogue.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="field-label">{t("banking.file.reason")}</span>
          <input
            className={cn(selectClass, "mt-1 block w-full")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="banking-file-reason"
          />
          <span className="mt-1 block text-[11.5px] text-muted-foreground">
            {t("banking.file.reasonHint")}
          </span>
        </label>
        {refused && (
          <p
            className="text-[12.5px] text-destructive"
            role="alert"
            data-testid="banking-file-refused"
          >
            {refused}
          </p>
        )}
        <DialogFooter className="gap-2 sm:justify-between">
          {row.method === "manual" ? (
            <button
              type="button"
              onClick={() =>
                clear.mutate(row.txn_id, {
                  onSuccess: () => {
                    toast.success(t("banking.file.removed"));
                    onClose();
                  },
                })
              }
              className="text-[12.5px] font-medium text-destructive hover:underline"
              data-testid="banking-file-remove"
            >
              {t("banking.file.remove")}
            </button>
          ) : (
            <span />
          )}
          <span className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-border px-3 py-1.5 text-[13px]"
            >
              {t("banking.file.cancel")}
            </button>
            <button
              type="button"
              disabled={!ready || file.isPending}
              onClick={() =>
                file.mutate(
                  { txn: row.txn_id, body: { category, reason: reason.trim() } },
                  {
                    onSuccess: () => {
                      toast.success(t("banking.file.recorded"));
                      onClose();
                    },
                  },
                )
              }
              className="rounded bg-primary px-3 py-1.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
              data-testid="banking-file-save"
            >
              {t("banking.file.save")}
            </button>
          </span>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
