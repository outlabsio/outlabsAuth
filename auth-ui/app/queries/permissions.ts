/**
 * Permissions Queries
 * Pinia Colada queries for permission management
 *
 * Note: Permissions are mostly read-only (managed through roles)
 * so we only have queries, no mutations
 */

import { defineQueryOptions } from '@pinia/colada'
import { createPermissionsAPI } from '~/api/permissions'

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
}
