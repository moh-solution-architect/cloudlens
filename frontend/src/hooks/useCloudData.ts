import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";

export function useCostSummary() {
  return useQuery({
    queryKey: ["costSummary"],
    queryFn: api.getCostSummary,
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });
}

export function useRecommendations(filters?: {
  provider?: string[];
  rec_type?: string[];
  min_savings?: number;
}) {
  return useQuery({
    queryKey: ["recommendations", filters],
    queryFn: () => api.getRecommendations(filters),
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });
}
