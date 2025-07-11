import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/simple-fetch";
import { type Permission, type PaginatedResponse } from "@/lib/api/types";

interface PermissionFilters {
  platformId?: string;
  permissionType?: "system" | "custom";
  resource?: string;
  search?: string;
  page?: number;
  pageSize?: number;
  enabled?: boolean;
}

function buildPermissionUrl(filters?: PermissionFilters): string {
  const params = new URLSearchParams();
  
  if (filters?.platformId) {
    params.append("platform_id", filters.platformId);
  }
  if (filters?.permissionType) {
    params.append("permission_type", filters.permissionType);
  }
  if (filters?.resource) {
    params.append("resource", filters.resource);
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
  return `/v1/permissions/${queryString ? `?${queryString}` : ""}`;
}

// Get permissions list
export function usePermissions(filters?: PermissionFilters) {
  const { enabled = true, ...queryFilters } = filters || {};
  
  return useQuery({
    queryKey: ["permissions", queryFilters],
    queryFn: () => api.get<PaginatedResponse<Permission>>(buildPermissionUrl(queryFilters)),
    enabled,
  });
}

// Get single permission
export function usePermission(permissionId: string | null) {
  return useQuery({
    queryKey: ["permission", permissionId],
    queryFn: () => api.get<Permission>(`/v1/permissions/${permissionId}`),
    enabled: !!permissionId,
  });
}

// Create permission mutation
export function useCreatePermission() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<Permission>) => 
      api.post<Permission>("/v1/permissions/", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
    },
  });
}

// Update permission mutation
export function useUpdatePermission() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Permission> & { id: string }) => 
      api.patch<Permission>(`/v1/permissions/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
      queryClient.invalidateQueries({ queryKey: ["permission", variables.id] });
    },
  });
}

// Delete permission mutation
export function useDeletePermission() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => 
      api.delete(`/v1/permissions/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
    },
  });
}