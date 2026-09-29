import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useCases() {
  return useQuery({ queryKey: ["cases"], queryFn: api.listCases });
}

export function useCase(id: string | undefined) {
  return useQuery({
    queryKey: ["cases", id],
    queryFn: () => api.getCase(id as string),
    enabled: Boolean(id),
    retry: false,
  });
}

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
}

/** INR amount in the Indian convention: crore above 1 crore, lakh above 1 lakh. */
export function formatInr(amount: number): string {
  if (amount >= 1e7) return `INR ${(amount / 1e7).toFixed(2)} cr`;
  if (amount >= 1e5) return `INR ${(amount / 1e5).toFixed(2)} lakh`;
  return `INR ${amount.toLocaleString("en-IN")}`;
}
