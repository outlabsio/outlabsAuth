/**
 * Permissions Queries & Mutations
 * Pinia Colada queries and mutations for permission management
 */

import { defineQueryOptions, defineMutation, useQueryCache } from '@pinia/colada'
import { createPermissionsAPI, type CreatePermissionData, type UpdatePermissionData } from '~/api/permissions'

/**
 * Query Keys for permissions
 * Hierarchical structure for cache management
 */
export const PERMISSION_KEYS = {
  all: ['permissions'] as const,
  available: () => [...PERMISSION_KEYS.all, 'available'] as const,
  user: () => [...PERMISSION_KEYS.all, 'user'] as const,
  userInContext: (entityId?: string) =>
    [...PERMISSION_KEYS.user(), { entityId }] as const,
  detail: (id: string) => [...PERMISSION_KEYS.all, 'detail', id] as const,
}

/**
 * Permissions Query Options
 * Reusable query definitions
 */
export const permissionsQueries = {
  /**
   * Query for all available permissions in the system
   * Longer staleTime since permissions change rarely
   */
  available: () =>
    defineQueryOptions({
      key: PERMISSION_KEYS.available(),
      query: async () => {
        const permissionsAPI = createPermissionsAPI()
        return permissionsAPI.fetchAvailablePermissions()
      },
      staleTime: 60000, // 60 seconds - permissions rarely change
    }),

  /**
   * Query for current user's permissions in the current context
   * Auto-refetches when context changes
   */
  userPermissions: (entityId?: string) =>
    defineQueryOptions({
      key: PERMISSION_KEYS.userInContext(entityId),
      query: async () => {
        const permissionsAPI = createPermissionsAPI()
        return permissionsAPI.fetchUserPermissions()
      },
      staleTime: 30000, // 30 seconds - user permissions might change when roles updated
    }),

  /**
   * Query for a specific permission by ID
   */
  detail: (id: string) =>
    defineQueryOptions({
      key: PERMISSION_KEYS.detail(id),
      query: async () => {
        const permissionsAPI = createPermissionsAPI()
        return permissionsAPI.getPermission(id)
      },
      staleTime: 60000,
    }),
}

/**
 * Permissions Mutations
 * Create, update, and delete operations
 */
export const permissionsMutations = {
  /**
   * Create a new permission
   */
  create: () =>
    defineMutation({
      mutation: async (data: CreatePermissionData) => {
        const permissionsAPI = createPermissionsAPI()
        return permissionsAPI.createPermission(data)
      },
      onSuccess: () => {
        // Invalidate permissions list cache
        const queryCache = useQueryCache()
        queryCache.invalidateQueries({ key: PERMISSION_KEYS.available() })
      },
    }),

  /**
   * Update an existing permission
   */
  update: () =>
    defineMutation({
      mutation: async ({ id, data }: { id: string; data: UpdatePermissionData }) => {
        const permissionsAPI = createPermissionsAPI()
        return permissionsAPI.updatePermission(id, data)
      },
      onSuccess: (_data, variables) => {
        // Invalidate specific permission and list cache
        const queryCache = useQueryCache()
        queryCache.invalidateQueries({ key: PERMISSION_KEYS.detail(variables.id) })
        queryCache.invalidateQueries({ key: PERMISSION_KEYS.available() })
      },
    }),

  /**
   * Delete a permission
   */
  delete: () =>
    defineMutation({
      mutation: async (id: string) => {
        const permissionsAPI = createPermissionsAPI()
        return permissionsAPI.deletePermission(id)
      },
      onSuccess: (_data, id) => {
        // Invalidate specific permission and list cache
        const queryCache = useQueryCache()
        queryCache.invalidateQueries({ key: PERMISSION_KEYS.detail(id) })
        queryCache.invalidateQueries({ key: PERMISSION_KEYS.available() })

        // Show success toast
        const toast = useToast()
        toast.add({
          title: 'Permission deleted',
          description: 'The permission has been deleted successfully',
          color: 'success'
        })
      },
    }),
}

/**
 * Create Permission Mutation
 * Use this composable in components for proper Pinia Colada integration
 */
export function useCreatePermissionMutation() {
  const queryCache = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async (data: CreatePermissionData) => {
      const permissionsAPI = createPermissionsAPI()
      return permissionsAPI.createPermission(data)
    },
    onSuccess: (data) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: PERMISSION_KEYS.available() })

      toast.add({
        title: 'Permission created',
        description: `Permission "${data.name}" has been created successfully`,
        color: 'success'
      })
    },
    onError: (error: any) => {
      // Extract error message from response body (error.data.detail) or fallback to error.message
      const errorMessage = error.data?.detail || error.message || 'Failed to create permission'

      toast.add({
        title: 'Error creating permission',
        description: errorMessage,
        color: 'error'
      })
    },
  })
}

/**
 * Delete Permission Mutation
 * Use this composable in components for proper Pinia Colada integration
 */
export function useDeletePermissionMutation() {
  const queryCache = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async (permissionId: string) => {
      const permissionsAPI = createPermissionsAPI()
      return permissionsAPI.deletePermission(permissionId)
    },
    onSuccess: (_data, permissionId) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: PERMISSION_KEYS.available() })
      // Invalidate detail query for deleted permission
      queryCache.invalidateQueries({ key: PERMISSION_KEYS.detail(permissionId) })

      toast.add({
        title: 'Permission deleted',
        description: 'The permission has been deleted successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      // Extract error message from response body (error.data.detail) or fallback to error.message
      const errorMessage = error.data?.detail || error.message || 'Failed to delete permission'

      toast.add({
        title: 'Error deleting permission',
        description: errorMessage,
        color: 'error'
      })
    },
  })
}

/**
 * Update Permission Mutation
 * Use this composable in components for proper Pinia Colada integration
 */
export function useUpdatePermissionMutation() {
  const queryCache = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({ id, data }: { id: string; data: UpdatePermissionData }) => {
      const permissionsAPI = createPermissionsAPI()
      return permissionsAPI.updatePermission(id, data)
    },
    onSuccess: (data, variables) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: PERMISSION_KEYS.available() })
      queryCache.invalidateQueries({ key: PERMISSION_KEYS.detail(variables.id) })

      toast.add({
        title: 'Permission updated',
        description: `Permission "${data.name}" has been updated successfully`,
        color: 'success'
      })
    },
    onError: (error: any) => {
      // Extract error message from response body (error.data.detail) or fallback to error.message
      console.error('[UPDATE PERMISSION ERROR] Full error:', error)
      console.error('[UPDATE PERMISSION ERROR] error.data:', error.data)
      console.error('[UPDATE PERMISSION ERROR] error.data.detail:', error.data?.detail)
      console.error('[UPDATE PERMISSION ERROR] error.message:', error.message)

      // FastAPI returns validation errors as an array in error.data.detail
      let errorMessage = 'Failed to update permission'
      if (error.data?.detail) {
        if (Array.isArray(error.data.detail)) {
          // Extract messages from validation error array
          errorMessage = error.data.detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ')
        } else {
          errorMessage = error.data.detail
        }
      } else if (error.message) {
        errorMessage = error.message
      }

      toast.add({
        title: 'Error updating permission',
        description: errorMessage,
        color: 'error'
      })
    },
  })
}
