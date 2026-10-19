import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { canBank, useAuth } from "../features/auth/AuthProvider";
export function useAccounts() {
  const { user } = useAuth();
  return useInfiniteQuery({
    queryKey: ["accounts", user?.id],
    queryFn: ({ pageParam }) => api.accounts(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: canBank(user),
  });
}
export function usePayments() {
  const { user } = useAuth();
  return useInfiniteQuery({
    queryKey: ["payments", user?.id],
    queryFn: ({ pageParam }) => api.payments(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: canBank(user),
  });
}
export function useHealth(service: "auth" | "payment") {
  return useQuery({
    queryKey: ["health", service],
    queryFn: () => api.health(service),
    refetchInterval: 30000,
    retry: false,
  });
}
