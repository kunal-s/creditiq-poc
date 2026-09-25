import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useUsers() {
  return useQuery({ queryKey: ["users"], queryFn: api.listUsers });
}

export function useRoles() {
  return useQuery({ queryKey: ["roles"], queryFn: api.listRoles });
}
