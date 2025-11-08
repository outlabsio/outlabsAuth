/**
 * Entities Queries
 * Pinia Colada queries and mutations for entity management
 *
 * NOTE: Entities have a tree structure, so cache invalidation is more complex
 */

import { defineQueryOptions, useMutation, useQueryCache } from '@pinia/colada'
import { createEntitiesAPI } from '~/api/entities'
import type { Entity } from '~/types/entity'
import type { EntityFilters, CreateEntityData, UpdateEntityData } from '~/stores/entities.store'
import type { PaginationParams } from '~/types/api'

/**
 * Query Keys for entities
 * Hierarchical structure for cache management
 */
export const ENTITY_KEYS = {
  all: ['entities'] as const,
  lists: () => [...ENTITY_KEYS.all, 'list'] as const,
  list: (filters: EntityFilters, params: PaginationParams) =>
    [...ENTITY_KEYS.lists(), { filters, params }] as const,
  details: () => [...ENTITY_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...ENTITY_KEYS.details(), id] as const,
  hierarchies: () => [...ENTITY_KEYS.all, 'hierarchy'] as const,
  hierarchy: (id: string) => [...ENTITY_KEYS.hierarchies(), id] as const,
}

/**
 * Entities Query Options
 * Reusable query definitions
 */
export const entitiesQueries = {
  /**
   * Query for paginated entity list
   */
  list: (filters: EntityFilters = {}, params: PaginationParams = {}) =>
    defineQueryOptions({
      key: ENTITY_KEYS.list(filters, params),
      query: async () => {
        const entitiesAPI = createEntitiesAPI()
        return entitiesAPI.fetchEntities(filters, params)
      },
      staleTime: 10000, // 10 seconds
    }),

  /**
   * Query for single entity detail
   */
  detail: (id: string) =>
    defineQueryOptions({
      key: ENTITY_KEYS.detail(id),
      query: async () => {
        const entitiesAPI = createEntitiesAPI()
        return entitiesAPI.fetchEntity(id)
      },
      staleTime: 15000, // 15 seconds
    }),

  /**
   * Query for entity hierarchy (tree structure)
   */
  hierarchy: (id: string) =>
    defineQueryOptions({
      key: ENTITY_KEYS.hierarchy(id),
      query: async () => {
        const entitiesAPI = createEntitiesAPI()
        return entitiesAPI.getEntityHierarchy(id)
      },
      staleTime: 15000, // 15 seconds
    }),
}

/**
 * Create Entity Mutation
 * Automatically invalidates entity list queries and parent hierarchy
 */
export function useCreateEntityMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async (data: CreateEntityData) => {
      const entitiesAPI = createEntitiesAPI()
      return entitiesAPI.createEntity(data)
    },
    onSuccess: (newEntity) => {
      // Invalidate all entity list queries
      queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.lists() })

      // If entity has a parent, invalidate parent's hierarchy
      if (newEntity.parent_id) {
        queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.hierarchy(newEntity.parent_id) })
      }

      toast.add({
        title: 'Entity created',
        description: 'The entity has been created successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error creating entity',
        description: error.message || 'Failed to create entity',
        color: 'error'
      })
    },
  })
}

/**
 * Update Entity Mutation
 * Automatically invalidates affected queries
 */
export function useUpdateEntityMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({ entityId, data }: { entityId: string; data: UpdateEntityData }) => {
      const entitiesAPI = createEntitiesAPI()
      return entitiesAPI.updateEntity(entityId, data)
    },
    onSuccess: (_data, { entityId }) => {
      // Invalidate specific entity detail
      queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.detail(entityId) })
      // Invalidate entity hierarchy (name/metadata might have changed)
      queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.hierarchy(entityId) })
      // Invalidate all entity lists
      queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.lists() })

      toast.add({
        title: 'Entity updated',
        description: 'The entity has been updated successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error updating entity',
        description: error.message || 'Failed to update entity',
        color: 'error'
      })
    },
  })
}

/**
 * Move Entity Mutation
 * Complex cache invalidation due to tree structure changes
 */
export function useMoveEntityMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({ entityId, newParentId, oldParentId }: {
      entityId: string
      newParentId: string | null
      oldParentId?: string | null
    }) => {
      const entitiesAPI = createEntitiesAPI()
      await entitiesAPI.moveEntity(entityId, newParentId)
      return { entityId, newParentId, oldParentId }
    },
    onSuccess: ({ entityId, newParentId, oldParentId }) => {
      // Invalidate the moved entity's detail and hierarchy
      queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.detail(entityId) })
      queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.hierarchy(entityId) })

      // Invalidate new parent's hierarchy
      if (newParentId) {
        queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.hierarchy(newParentId) })
      }

      // Invalidate old parent's hierarchy if different from new parent
      if (oldParentId && oldParentId !== newParentId) {
        queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.hierarchy(oldParentId) })
      }

      // Invalidate all lists (entity appears in different places now)
      queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.lists() })

      toast.add({
        title: 'Entity moved',
        description: 'The entity has been moved successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error moving entity',
        description: error.message || 'Failed to move entity',
        color: 'error'
      })
    },
  })
}

/**
 * Delete Entity Mutation
 * With optimistic updates and hierarchical cache invalidation
 */
export function useDeleteEntityMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({ entityId, parentId }: { entityId: string; parentId?: string | null }) => {
      const entitiesAPI = createEntitiesAPI()
      await entitiesAPI.deleteEntity(entityId)
      return { entityId, parentId }
    },
    onMutate: async ({ entityId }) => {
      // Cancel ongoing queries
      await queryClient.cancelQueries({ queryKey: ENTITY_KEYS.all })

      // Snapshot current state for rollback
      const previousLists = queryClient.getQueriesData({ queryKey: ENTITY_KEYS.lists() })

      // Optimistically update all entity lists
      queryClient.setQueriesData<any>(
        { queryKey: ENTITY_KEYS.lists() },
        (old: any) => {
          if (!old?.items) return old
          return {
            ...old,
            items: old.items.filter((entity: Entity) => entity.id !== entityId),
            total: old.total - 1
          }
        }
      )

      return { previousLists, entityId }
    },
    onError: (error: any, _vars, context) => {
      // Rollback on error
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data)
        })
      }

      toast.add({
        title: 'Error deleting entity',
        description: error.message || 'Failed to delete entity',
        color: 'error'
      })
    },
    onSuccess: ({ entityId, parentId }) => {
      // Invalidate to refetch fresh data
      queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.lists() })

      // Remove detail and hierarchy queries for deleted entity
      queryClient.removeQueries({ queryKey: ENTITY_KEYS.detail(entityId) })
      queryClient.removeQueries({ queryKey: ENTITY_KEYS.hierarchy(entityId) })

      // Invalidate parent's hierarchy if exists
      if (parentId) {
        queryClient.invalidateQueries({ queryKey: ENTITY_KEYS.hierarchy(parentId) })
      }

      toast.add({
        title: 'Entity deleted',
        description: 'The entity has been deleted successfully',
        color: 'success'
      })
    },
  })
}
