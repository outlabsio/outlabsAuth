/**
 * Permissions API
 * API functions for permission management
 */

import type { Permission } from '~/types/role'
import type { UserPermissions } from '~/stores/permissions.store'
import type {
  AbacCondition,
  AbacConditionCreateData,
  AbacConditionUpdateData,
  ConditionGroup,
  ConditionGroupCreateData,
  ConditionGroupUpdateData
} from '~/types/abac'
import { createAPIClient } from './client'

/**
 * Permission creation data
 */
export interface CreatePermissionData {
  name: string
  display_name: string
  description?: string
  is_system?: boolean
  is_active?: boolean
  tags?: string[]
  metadata?: Record<string, any>
}

/**
 * Permission update data
 */
export interface UpdatePermissionData {
  display_name?: string
  description?: string
  is_active?: boolean
  tags?: string[]
  metadata?: Record<string, any>
}

export function createPermissionsAPI() {
  const client = createAPIClient()

  return {
    /**
     * Fetch all available permissions
     * Note: Backend returns paginated data, we request a large limit to get all
     */
    async fetchAvailablePermissions(): Promise<Permission[]> {
      const response = await client.call<{
        items: Permission[]
        total: number
        page: number
        limit: number
        pages: number
      }>('/v1/permissions/?page=1&limit=1000')
      return response.items
    },

    /**
     * Fetch current user's permissions in current context
     */
    async fetchUserPermissions(): Promise<UserPermissions> {
      const contextStore = useContextStore()
      const contextHeaders: Record<string, string> = {}
      const authStore = useAuthStore()

      if (contextStore.selectedEntity && !contextStore.selectedEntity.is_system) {
        contextHeaders['X-Entity-Context'] = contextStore.selectedEntity.id
      }

      const response = await client.call<UserPermissions | string[]>('/v1/permissions/me', {
        headers: contextHeaders
      })

      if (Array.isArray(response)) {
        return {
          permissions: response,
          roles: [],
          is_superuser: authStore.currentUser?.is_superuser ?? false
        }
      }

      return {
        permissions: response.permissions || [],
        roles: response.roles || [],
        is_superuser: response.is_superuser ?? authStore.currentUser?.is_superuser ?? false
      }
    },

    /**
     * Create a new permission
     */
    async createPermission(data: CreatePermissionData): Promise<Permission> {
      return client.call<Permission>('/v1/permissions/', {
        method: 'POST',
        body: data
      })
    },

    /**
     * Get permission by ID
     */
    async getPermission(permissionId: string): Promise<Permission> {
      return client.call<Permission>(`/v1/permissions/${permissionId}`)
    },

    /**
     * Update permission
     */
    async updatePermission(permissionId: string, data: UpdatePermissionData): Promise<Permission> {
      return client.call<Permission>(`/v1/permissions/${permissionId}`, {
        method: 'PATCH',
        body: data
      })
    },

    /**
     * Delete permission
     */
    async deletePermission(permissionId: string): Promise<void> {
      return client.call<void>(`/v1/permissions/${permissionId}`, {
        method: 'DELETE'
      })
    },

    /**
     * ABAC - Condition groups
     */
    async fetchConditionGroups(permissionId: string): Promise<ConditionGroup[]> {
      return client.call<ConditionGroup[]>(`/v1/permissions/${permissionId}/condition-groups`)
    },
    async createConditionGroup(
      permissionId: string,
      data: ConditionGroupCreateData
    ): Promise<ConditionGroup> {
      return client.call<ConditionGroup>(`/v1/permissions/${permissionId}/condition-groups`, {
        method: 'POST',
        body: JSON.stringify(data)
      })
    },
    async updateConditionGroup(
      permissionId: string,
      groupId: string,
      data: ConditionGroupUpdateData
    ): Promise<ConditionGroup> {
      return client.call<ConditionGroup>(`/v1/permissions/${permissionId}/condition-groups/${groupId}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      })
    },
    async deleteConditionGroup(permissionId: string, groupId: string): Promise<void> {
      return client.call<void>(`/v1/permissions/${permissionId}/condition-groups/${groupId}`, {
        method: 'DELETE'
      })
    },

    /**
     * ABAC - Conditions
     */
    async fetchConditions(permissionId: string): Promise<AbacCondition[]> {
      return client.call<AbacCondition[]>(`/v1/permissions/${permissionId}/conditions`)
    },
    async createCondition(
      permissionId: string,
      data: AbacConditionCreateData
    ): Promise<AbacCondition> {
      return client.call<AbacCondition>(`/v1/permissions/${permissionId}/conditions`, {
        method: 'POST',
        body: JSON.stringify(data)
      })
    },
    async updateCondition(
      permissionId: string,
      conditionId: string,
      data: AbacConditionUpdateData
    ): Promise<AbacCondition> {
      return client.call<AbacCondition>(`/v1/permissions/${permissionId}/conditions/${conditionId}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      })
    },
    async deleteCondition(permissionId: string, conditionId: string): Promise<void> {
      return client.call<void>(`/v1/permissions/${permissionId}/conditions/${conditionId}`, {
        method: 'DELETE'
      })
    }
  }
}
