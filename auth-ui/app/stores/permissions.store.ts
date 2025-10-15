/**
 * Permissions Store
 * Manages permission checking and available permissions
 */

import { defineStore } from 'pinia'
import type { Permission } from '~/types/role'
import { USE_MOCK_DATA, mockDelay, logMockCall } from '~/utils/mock'
import { mockPermissions } from '~/utils/mockData'

export interface UserPermissions {
  permissions: string[]
  roles: string[]
  is_superuser: boolean
}

export interface PermissionCheck {
  resource: string
  action: string
  entity_id?: string
}

export const usePermissionsStore = defineStore('permissions', () => {
  const authStore = useAuthStore()
  const contextStore = useContextStore()

  // State
  const state = reactive({
    availablePermissions: [] as Permission[],
    userPermissions: null as UserPermissions | null,
    isLoading: false,
    error: null as string | null
  })

  // Getters
  const availablePermissions = computed(() => state.availablePermissions)
  const userPermissions = computed(() => state.userPermissions)
  const isLoading = computed(() => state.isLoading)
  const error = computed(() => state.error)

  /**
   * Parse permission string into resource and action
   * Format: "resource:action" or "resource:action_tree"
   */
  const parsePermission = (permission: string): { resource: string; action: string } => {
    const [resource, action] = permission.split(':')
    return { resource: resource || '*', action: action || '*' }
  }

  /**
   * Check if permission matches a pattern
   * Supports wildcards: *, resource:*, *:action
   */
  const matchesPermission = (userPerm: string, requiredPerm: string): boolean => {
    // Exact match
    if (userPerm === requiredPerm) return true

    // Wildcard all permissions
    if (userPerm === '*:*' || userPerm === '*') return true

    const userParsed = parsePermission(userPerm)
    const requiredParsed = parsePermission(requiredPerm)

    // Resource wildcard: resource:*
    if (userParsed.resource === requiredParsed.resource && userParsed.action === '*') {
      return true
    }

    // Action wildcard: *:action
    if (userParsed.resource === '*' && userParsed.action === requiredParsed.action) {
      return true
    }

    return false
  }

  /**
   * Fetch available permissions (all possible permissions in system)
   */
  const fetchAvailablePermissions = async (): Promise<void> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('GET', '/v1/permissions')
        await mockDelay()

        state.availablePermissions = [...mockPermissions]
        return
      }

      // Real API call
      const permissions = await authStore.apiCall<Permission[]>('/v1/permissions')
      state.availablePermissions = permissions
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch permissions'
      console.error('Failed to fetch permissions:', error)
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Fetch current user's permissions in current context
   */
  const fetchUserPermissions = async (): Promise<void> => {
    try {
      state.isLoading = true
      state.error = null

      const currentUser = authStore.currentUser
      if (!currentUser) {
        throw new Error('No authenticated user')
      }

      // Mock mode
      if (USE_MOCK_DATA) {
        const entityId = contextStore.selectedEntity?.id
        logMockCall('GET', '/v1/users/me/permissions', { entity_id: entityId })
        await mockDelay()

        // For mock: superuser gets all permissions
        if (currentUser.is_superuser) {
          state.userPermissions = {
            permissions: ['*:*'],
            roles: ['admin'],
            is_superuser: true
          }
          return
        }

        // For regular users: return subset of permissions based on mock roles
        // In a real implementation, this would come from the backend
        state.userPermissions = {
          permissions: [
            'user:read',
            'entity:read',
            'role:read',
            'project:read'
          ],
          roles: ['viewer'],
          is_superuser: false
        }
        return
      }

      // Real API call
      const contextHeaders: Record<string, string> = {}
      if (contextStore.selectedEntity && !contextStore.selectedEntity.is_system) {
        contextHeaders['X-Entity-Context'] = contextStore.selectedEntity.id
      }

      const permissions = await authStore.apiCall<UserPermissions>(
        '/v1/users/me/permissions',
        { headers: contextHeaders }
      )

      state.userPermissions = permissions
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch user permissions'
      console.error('Failed to fetch user permissions:', error)
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Check if current user has permission
   * Supports both simple (resource:action) and tree permissions (resource:action_tree)
   */
  const hasPermission = (permission: string): boolean => {
    const currentUser = authStore.currentUser
    if (!currentUser) return false

    // Superusers have all permissions
    if (currentUser.is_superuser) return true

    // Check user permissions
    if (!state.userPermissions) return false

    return state.userPermissions.permissions.some(userPerm =>
      matchesPermission(userPerm, permission)
    )
  }

  /**
   * Check if current user has ALL of the specified permissions
   */
  const hasAllPermissions = (permissions: string[]): boolean => {
    return permissions.every(perm => hasPermission(perm))
  }

  /**
   * Check if current user has ANY of the specified permissions
   */
  const hasAnyPermission = (permissions: string[]): boolean => {
    return permissions.some(perm => hasPermission(perm))
  }

  /**
   * Check if current user has a role
   */
  const hasRole = (roleName: string): boolean => {
    if (!state.userPermissions) return false
    return state.userPermissions.roles.includes(roleName)
  }

  /**
   * Check if current user has ANY of the specified roles
   */
  const hasAnyRole = (roleNames: string[]): boolean => {
    return roleNames.some(role => hasRole(role))
  }

  /**
   * Get permissions for a specific resource
   */
  const getResourcePermissions = (resource: string): string[] => {
    return state.availablePermissions
      .filter(p => p.name.startsWith(resource + ':'))
      .map(p => p.name)
  }

  /**
   * Get all resources from available permissions
   */
  const getResources = (): string[] => {
    const resources = new Set<string>()
    state.availablePermissions.forEach(p => {
      const { resource } = parsePermission(p.name)
      if (resource !== '*') {
        resources.add(resource)
      }
    })
    return Array.from(resources).sort()
  }

  /**
   * Get all actions for a resource
   */
  const getResourceActions = (resource: string): string[] => {
    const actions = new Set<string>()
    state.availablePermissions.forEach(p => {
      const parsed = parsePermission(p.name)
      if (parsed.resource === resource && parsed.action !== '*') {
        actions.add(parsed.action)
      }
    })
    return Array.from(actions).sort()
  }

  /**
   * Search permissions by query
   */
  const searchPermissions = (query: string): Permission[] => {
    const search = query.toLowerCase()
    return state.availablePermissions.filter(
      p =>
        p.name.toLowerCase().includes(search) ||
        p.description?.toLowerCase().includes(search)
    )
  }

  /**
   * Clear error
   */
  const clearError = (): void => {
    state.error = null
  }

  /**
   * Initialize permissions (called after auth and context initialization)
   */
  const initialize = async (): Promise<void> => {
    await fetchAvailablePermissions()
    if (authStore.isAuthenticated) {
      await fetchUserPermissions()
    }
  }

  /**
   * Refresh user permissions (call after context switch)
   */
  const refresh = async (): Promise<void> => {
    if (authStore.isAuthenticated) {
      await fetchUserPermissions()
    }
  }

  return {
    // State
    state: readonly(state),

    // Getters
    availablePermissions,
    userPermissions,
    isLoading,
    error,

    // Actions
    fetchAvailablePermissions,
    fetchUserPermissions,
    hasPermission,
    hasAllPermissions,
    hasAnyPermission,
    hasRole,
    hasAnyRole,
    getResourcePermissions,
    getResources,
    getResourceActions,
    searchPermissions,
    parsePermission,
    clearError,
    initialize,
    refresh
  }
})
