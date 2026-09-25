import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Case } from "@/api/types";

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

export function findCase(cases: Case[] | undefined, id: string | undefined) {
  return cases?.find((c) => c.id === id);
}
