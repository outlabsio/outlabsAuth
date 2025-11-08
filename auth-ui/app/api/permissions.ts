/**
 * Permissions API
 * API functions for permission management
 */

import type { Permission } from '~/types/role'
import type { UserPermissions } from '~/stores/permissions.store'
import { createAPIClient } from './client'

export function createPermissionsAPI() {
  const client = createAPIClient()

  return {
    /**
     * Fetch all available permissions
     */
    async fetchAvailablePermissions(): Promise<Permission[]> {
      return client.call<Permission[]>('/v1/permissions')
    },

    /**
     * Fetch current user's permissions in current context
     */
    async fetchUserPermissions(): Promise<UserPermissions> {
      const contextStore = useContextStore()
      const contextHeaders: Record<string, string> = {}

      if (contextStore.selectedEntity && !contextStore.selectedEntity.is_system) {
        contextHeaders['X-Entity-Context'] = contextStore.selectedEntity.id
      }

      return client.call<UserPermissions>('/v1/users/me/permissions', {
        headers: contextHeaders
      })
    }
  }
}
