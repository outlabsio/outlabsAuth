import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/simple-fetch";
import { type Platform } from "@/lib/api/types";

interface PlatformFilters {
  status?: string;
  search?: string;
  enabled?: boolean;
}

function buildPlatformUrl(filters?: PlatformFilters): string {
  const params = new URLSearchParams();
  
  if (filters?.status) {
    params.append("status", filters.status);
  }
  if (filters?.search) {
    params.append("search", filters.search);
  }
  
  const queryString = params.toString();
  return `/v1/platforms/${queryString ? `?${queryString}` : ""}`;
}

// Get platforms list
export function usePlatforms(filters?: PlatformFilters) {
  const { enabled = true, ...queryFilters } = filters || {};
  
  return useQuery({
    queryKey: ["platforms", queryFilters],
    queryFn: () => api.get<{ items: Platform[] }>(buildPlatformUrl(queryFilters)),
    enabled,
  });
}

// Get single platform
export function usePlatform(platformId: string | null) {
  return useQuery({
    queryKey: ["platform", platformId],
    queryFn: () => api.get<Platform>(`/v1/platforms/${platformId}`),
    enabled: !!platformId,
  });
}

// Platform stats type
interface PlatformStats {
  user_count: number;
  entity_count: number;
  role_count: number;
  active_sessions: number;
}

// Get platform stats
export function usePlatformStats(platformId: string | null) {
  return useQuery({
    queryKey: ["platform-stats", platformId],
    queryFn: () => api.get<PlatformStats>(`/v1/platforms/${platformId}/stats`),
    enabled: !!platformId,
  });
}

// Create platform mutation
export function useCreatePlatform() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<Platform>) => 
      api.post<Platform>("/v1/platforms/", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platforms"] });
    },
  });
}

// Update platform mutation
export function useUpdatePlatform() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Platform> & { id: string }) => 
      api.patch<Platform>(`/v1/platforms/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["platforms"] });
      queryClient.invalidateQueries({ queryKey: ["platform", variables.id] });
    },
  });
}

// Delete platform mutation
export function useDeletePlatform() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => 
      api.delete(`/v1/platforms/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platforms"] });
    },
  });
}