import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/simple-fetch";
import { type Role, type PaginatedResponse } from "@/lib/api/types";

interface RoleFilters {
  entityId?: string;
  isGlobal?: boolean;
  search?: string;
  page?: number;
  pageSize?: number;
  enabled?: boolean;
}

function buildRoleUrl(filters?: RoleFilters): string {
  const params = new URLSearchParams();
  
  if (filters?.entityId) {
    params.append("entity_id", filters.entityId);
  }
  if (filters?.isGlobal !== undefined) {
    params.append("is_global", String(filters.isGlobal));
  }
  if (filters?.search) {
    params.append("search", filters.search);
  }
  if (filters?.page) {
    params.append("page", filters.page.toString());
  }
  if (filters?.pageSize) {
    params.append("page_size", filters.pageSize.toString());
  }
  
  const queryString = params.toString();
  return `/v1/roles/${queryString ? `?${queryString}` : ""}`;
}

// Get roles list
export function useRoles(filters?: RoleFilters) {
  const { enabled = true, ...queryFilters } = filters || {};
  
  return useQuery({
    queryKey: ["roles", queryFilters],
    queryFn: () => api.get<PaginatedResponse<Role>>(buildRoleUrl(queryFilters)),
    enabled,
  });
}

// Get single role
export function useRole(roleId: string | null) {
  return useQuery({
    queryKey: ["role", roleId],
    queryFn: () => api.get<Role>(`/v1/roles/${roleId}`),
    enabled: !!roleId,
  });
}

// Role usage stats type
interface RoleUsageStats {
  role_id: string;
  role_name: string;
  active_assignments: number;
  total_assignments: number;
  entities_used_in: number;
  last_assigned?: string | null;
}

// Get role usage stats
export function useRoleUsage(roleId: string | null) {
  return useQuery({
    queryKey: ["role-usage", roleId],
    queryFn: async () => {
      const response = await api.get<{ stats: RoleUsageStats[] }>(`/v1/roles/${roleId}/usage`);
      return response.stats[0];
    },
    enabled: !!roleId,
    staleTime: 60000, // Cache for 1 minute
  });
}

// Create role mutation
export function useCreateRole() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<Role>) => 
      api.post<Role>("/v1/roles/", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
  });
}

// Update role mutation
export function useUpdateRole() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Role> & { id: string }) => 
      api.patch<Role>(`/v1/roles/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      queryClient.invalidateQueries({ queryKey: ["role", variables.id] });
    },
  });
}

// Delete role mutation
export function useDeleteRole() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => 
      api.delete(`/v1/roles/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
  });
}

// Clone role mutation
export function useCloneRole() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, name, displayName }: { id: string; name: string; displayName: string }) => 
      api.post(`/v1/roles/${id}/clone`, { name, display_name: displayName }, roleSchema),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
  });
}