import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { TxnCategoryRequest, TxnPage } from "@/api/types";

/** What narrows the transaction list; an empty value means no narrowing. */
export type TxnFilter = {
  category?: string;
  account?: string;
  month?: string;
  status?: string;
  q?: string;
  needs_review?: boolean;
  limit: number;
};

const key = (caseId: string) => ["cases", caseId, "transactions"] as const;

export function useTxnSummary(caseId: string) {
  return useQuery({
    queryKey: [...key(caseId), "summary"],
    queryFn: () => api.caseTransactionsSummary(caseId),
  });
}

export function useBankConduct(caseId: string) {
  return useQuery({
    queryKey: [...key(caseId), "conduct"],
    queryFn: () => api.caseBankConduct(caseId),
  });
}

export function useTxns(caseId: string, filter: TxnFilter) {
  return useQuery<TxnPage>({
    queryKey: [...key(caseId), "list", filter],
    queryFn: () => api.caseTransactions(caseId, filter),
    placeholderData: keepPreviousData,
  });
}

/** A person's decision on a row changes the credits the facts and checks read, and the review queue. */
function useAfterDecision(caseId: string) {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: ["cases", caseId] });
    void client.invalidateQueries({ queryKey: ["review"] });
  };
}

export function useCategorise(caseId: string) {
  const after = useAfterDecision(caseId);
  return useMutation({
    mutationFn: ({ txn, body }: { txn: string; body: TxnCategoryRequest }) =>
      api.categoriseTransaction(caseId, txn, body),
    onSuccess: after,
  });
}

export function useClearCategory(caseId: string) {
  const after = useAfterDecision(caseId);
  return useMutation({
    mutationFn: (txn: string) => api.clearTransactionCategory(caseId, txn),
    onSuccess: after,
  });
}

/** An amount in whole rupees, Indian grouping: a register entry. */
export function rupees(amount: number): string {
  return Math.round(amount).toLocaleString("en-IN");
}

/** An amount in INR lakh to two places: the monthly and category summaries. */
export function lakh(amount: number): string {
  return (amount / 100_000).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2025-09" as "Sep 2025", as the other tabs write a month. */
export function monthLabel(month: string): string {
  const [y, m] = month.split("-");
  return `${MONTHS[Number(m) - 1] ?? m} ${y}`;
}
