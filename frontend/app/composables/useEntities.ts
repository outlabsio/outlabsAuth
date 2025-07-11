import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import type { Entity, PaginatedResponse } from '~/types/auth.types'

// Query key factory for consistency
export const entityKeys = {
  all: ['entities'] as const,
  lists: () => [...entityKeys.all, 'list'] as const,
  list: (filters: Record<string, any>) => [...entityKeys.lists(), filters] as const,
  details: () => [...entityKeys.all, 'detail'] as const,
  detail: (id: string) => [...entityKeys.details(), id] as const,
  types: () => [...entityKeys.all, 'types'] as const,
}

// Fetch entities with pagination and filters
export const useEntities = (filters: Ref<Record<string, any>> = ref({})) => {
  const authStore = useAuthStore()
  
  return useQuery({
    queryKey: computed(() => entityKeys.list(filters.value)),
    queryFn: async () => {
      const params = new URLSearchParams()
      
      // Add filters to query params
      Object.entries(filters.value).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          params.append(key, String(value))
        }
      })
      
      const queryString = params.toString()
      const url = `/v1/entities${queryString ? `?${queryString}` : ''}`
      
      return await authStore.apiCall<PaginatedResponse<Entity>>(url)
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: computed(() => authStore.isAuthenticated),
  })
}

// Fetch single entity by ID
export const useEntity = (entityId: Ref<string | null>) => {
  const authStore = useAuthStore()
  
  return useQuery({
    queryKey: computed(() => entityId.value ? entityKeys.detail(entityId.value) : []),
    queryFn: async () => {
      if (!entityId.value) throw new Error('Entity ID is required')
      return await authStore.apiCall<Entity>(`/v1/entities/${entityId.value}`)
    },
    enabled: computed(() => !!entityId.value && authStore.isAuthenticated),
  })
}

// Fetch entity types for autocomplete
export const useEntityTypes = () => {
  const authStore = useAuthStore()
  
  return useQuery({
    queryKey: entityKeys.types(),
    queryFn: async () => {
      return await authStore.apiCall<string[]>('/v1/entities/entity-types')
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
    enabled: computed(() => authStore.isAuthenticated),
  })
}

// Create entity mutation
export const useCreateEntity = () => {
  const authStore = useAuthStore()
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: Partial<Entity>) => {
      return await authStore.apiCall<Entity>('/v1/entities', {
        method: 'POST',
        body: data,
      })
    },
    onSuccess: () => {
      // Invalidate entities list to refetch
      queryClient.invalidateQueries({ queryKey: entityKeys.lists() })
    },
  })
}

// Update entity mutation
export const useUpdateEntity = () => {
  const authStore = useAuthStore()
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Entity> }) => {
      return await authStore.apiCall<Entity>(`/v1/entities/${id}`, {
        method: 'PATCH',
        body: data,
      })
    },
    onSuccess: (updatedEntity) => {
      // Update the specific entity in cache
      queryClient.setQueryData(entityKeys.detail(updatedEntity.id), updatedEntity)
      // Invalidate lists to ensure consistency
      queryClient.invalidateQueries({ queryKey: entityKeys.lists() })
    },
  })
}

// Delete entity mutation
export const useDeleteEntity = () => {
  const authStore = useAuthStore()
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (id: string) => {
      return await authStore.apiCall(`/v1/entities/${id}`, {
        method: 'DELETE',
      })
    },
    onSuccess: (_, deletedId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: entityKeys.detail(deletedId) })
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: entityKeys.lists() })
    },
  })
}