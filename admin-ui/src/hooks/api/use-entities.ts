import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/simple-fetch";
import { type Entity, type PaginatedResponse } from "@/lib/api/types";

interface EntityFilters {
  parentId?: string;
  status?: string;
  entityClass?: string;
  entityType?: string;
  search?: string;
  page?: number;
  perPage?: number;
  enabled?: boolean;
}

function buildEntityUrl(filters?: EntityFilters): string {
  const params = new URLSearchParams();
  
  if (filters?.parentId) {
    params.append("parent_entity_id", filters.parentId);
  }
  if (filters?.status) {
    params.append("status", filters.status);
  }
  if (filters?.entityClass) {
    params.append("entity_class", filters.entityClass);
  }
  if (filters?.entityType) {
    params.append("entity_type", filters.entityType);
  }
  if (filters?.search) {
    params.append("search", filters.search);
  }
  if (filters?.page) {
    params.append("page", filters.page.toString());
  }
  if (filters?.perPage) {
    params.append("per_page", filters.perPage.toString());
  }
  
  const queryString = params.toString();
  return `/v1/entities/${queryString ? `?${queryString}` : ""}`;
}

// Get entities list
export function useEntities(filters?: EntityFilters) {
  const { enabled = true, ...queryFilters } = filters || {};
  
  return useQuery({
    queryKey: ["entities", queryFilters],
    queryFn: () => api.get<PaginatedResponse<Entity>>(buildEntityUrl(queryFilters)),
    enabled,
  });
}

// Get single entity
export function useEntity(entityId: string | null) {
  return useQuery({
    queryKey: ["entity", entityId],
    queryFn: () => api.get<Entity>(`/v1/entities/${entityId}`),
    enabled: !!entityId,
  });
}

// Get entity path (breadcrumb)
export function useEntityPath(entityId: string | null) {
  return useQuery({
    queryKey: ["entity-path", entityId],
    queryFn: () => api.get<Entity[]>(`/v1/entities/${entityId}/path`),
    enabled: !!entityId,
  });
}

// Get entity types
export function useEntityTypes() {
  return useQuery({
    queryKey: ["entity-types"],
    queryFn: () => api.get<string[]>("/v1/entities/entity-types"),
  });
}

// Create entity mutation
export function useCreateEntity() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<Entity>) => 
      api.post<Entity>("/v1/entities/", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      queryClient.invalidateQueries({ queryKey: ["entity-types"] });
    },
  });
}

// Update entity mutation
export function useUpdateEntity() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Entity> & { id: string }) => 
      api.patch<Entity>(`/v1/entities/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      queryClient.invalidateQueries({ queryKey: ["entity", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["entity-path"] });
    },
  });
}

// Delete entity mutation
export function useDeleteEntity() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => 
      api.delete(`/v1/entities/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      queryClient.invalidateQueries({ queryKey: ["entity-types"] });
    },
  });
}