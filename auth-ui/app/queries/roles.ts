/**
 * Roles Queries
 * Pinia Colada queries and mutations for role management
 */

import { defineQueryOptions, useMutation, useQueryCache } from '@pinia/colada'
import { createRolesAPI } from '~/api/roles'
import type { Role, CreateRoleData, UpdateRoleData } from '~/types/role'
import type { RoleFilters } from '~/stores/roles.store'
import type { PaginationParams } from '~/types/api'

/**
 * Query Keys for roles
 * Hierarchical structure for cache management
 */
export const ROLE_KEYS = {
  all: ['roles'] as const,
  lists: () => [...ROLE_KEYS.all, 'list'] as const,
  list: (filters: RoleFilters, params: PaginationParams) =>
    [...ROLE_KEYS.lists(), { filters, params }] as const,
  details: () => [...ROLE_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...ROLE_KEYS.details(), id] as const,
}

/**
 * Roles Query Options
 * Reusable query definitions
 */
export const rolesQueries = {
  /**
   * Query for paginated role list
   */
  list: (filters: RoleFilters = {}, params: PaginationParams = {}) =>
    defineQueryOptions({
      key: ROLE_KEYS.list(filters, params),
      query: async () => {
        const rolesAPI = createRolesAPI()
        return rolesAPI.fetchRoles(filters, params)
      },
      staleTime: 5000, // 5 seconds
    }),

  /**
   * Query for single role detail
   */
  detail: (id: string) =>
    defineQueryOptions({
      key: ROLE_KEYS.detail(id),
      query: async () => {
        const rolesAPI = createRolesAPI()
        return rolesAPI.fetchRole(id)
      },
      staleTime: 10000, // 10 seconds
    }),
}

/**
 * Create Role Mutation
 * Automatically invalidates role list queries
 */
export function useCreateRoleMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async (data: CreateRoleData) => {
      const rolesAPI = createRolesAPI()
      return rolesAPI.createRole(data)
    },
    onSuccess: () => {
      // Invalidate all role list queries
      queryClient.invalidateQueries({ queryKey: ROLE_KEYS.lists() })
      toast.add({
        title: 'Role created',
        description: 'The role has been created successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error creating role',
        description: error.message || 'Failed to create role',
        color: 'error'
      })
    },
  })
}

/**
 * Update Role Mutation
 * Automatically invalidates affected queries
 */
export function useUpdateRoleMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({ roleId, data }: { roleId: string; data: UpdateRoleData }) => {
      const rolesAPI = createRolesAPI()
      return rolesAPI.updateRole(roleId, data)
    },
    onSuccess: (_data, { roleId }) => {
      // Invalidate specific role detail
      queryClient.invalidateQueries({ queryKey: ROLE_KEYS.detail(roleId) })
      // Invalidate all role lists (role might appear in filtered lists)
      queryClient.invalidateQueries({ queryKey: ROLE_KEYS.lists() })
      toast.add({
        title: 'Role updated',
        description: 'The role has been updated successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error updating role',
        description: error.message || 'Failed to update role',
        color: 'error'
      })
    },
  })
}

/**
 * Delete Role Mutation
 * With optimistic updates for instant UI feedback
 */
export function useDeleteRoleMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async (roleId: string) => {
      const rolesAPI = createRolesAPI()
      return rolesAPI.deleteRole(roleId)
    },
    onMutate: async (roleId) => {
      // Cancel ongoing queries
      await queryClient.cancelQueries({ queryKey: ROLE_KEYS.all })

      // Snapshot current state for rollback
      const previousLists = queryClient.getQueriesData({ queryKey: ROLE_KEYS.lists() })

      // Optimistically update all role lists
      queryClient.setQueriesData<any>(
        { queryKey: ROLE_KEYS.lists() },
        (old: any) => {
          if (!old?.items) return old
          return {
            ...old,
            items: old.items.filter((role: Role) => role.id !== roleId),
            total: old.total - 1
          }
        }
      )

      return { previousLists, roleId }
    },
    onError: (error: any, _roleId, context) => {
      // Rollback on error
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data)
        })
      }

      toast.add({
        title: 'Error deleting role',
        description: error.message || 'Failed to delete role',
        color: 'error'
      })
    },
    onSuccess: (_data, roleId) => {
      // Invalidate to refetch fresh data
      queryClient.invalidateQueries({ queryKey: ROLE_KEYS.lists() })
      // Remove detail query for deleted role
      queryClient.removeQueries({ queryKey: ROLE_KEYS.detail(roleId) })

      toast.add({
        title: 'Role deleted',
        description: 'The role has been deleted successfully',
        color: 'success'
      })
    },
  })
}

/**
 * Assign Permissions Mutation
 * Updates role to add permissions
 */
export function useAssignPermissionsMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({ roleId, permissions }: { roleId: string; permissions: string[] }) => {
      const rolesAPI = createRolesAPI()
      return rolesAPI.assignPermissions(roleId, permissions)
    },
    onSuccess: (_data, { roleId }) => {
      // Invalidate specific role detail (permissions changed)
      queryClient.invalidateQueries({ queryKey: ROLE_KEYS.detail(roleId) })
      // Invalidate role lists (might affect filtered views)
      queryClient.invalidateQueries({ queryKey: ROLE_KEYS.lists() })
      toast.add({
        title: 'Permissions assigned',
        description: 'Permissions have been assigned to the role',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error assigning permissions',
        description: error.message || 'Failed to assign permissions',
        color: 'error'
      })
    },
  })
}

/**
 * Remove Permissions Mutation
 * Updates role to remove permissions
 */
export function useRemovePermissionsMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({ roleId, permissions }: { roleId: string; permissions: string[] }) => {
      const rolesAPI = createRolesAPI()
      return rolesAPI.removePermissions(roleId, permissions)
    },
    onSuccess: (_data, { roleId }) => {
      // Invalidate specific role detail (permissions changed)
      queryClient.invalidateQueries({ queryKey: ROLE_KEYS.detail(roleId) })
      // Invalidate role lists (might affect filtered views)
      queryClient.invalidateQueries({ queryKey: ROLE_KEYS.lists() })
      toast.add({
        title: 'Permissions removed',
        description: 'Permissions have been removed from the role',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error removing permissions',
        description: error.message || 'Failed to remove permissions',
        color: 'error'
      })
    },
  })
}
