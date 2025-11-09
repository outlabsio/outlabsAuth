/**
 * User Store (Single User)
 * Manages viewing/editing a SINGLE user
 * Separate from users.store.ts which handles list operations
 */

import { defineStore } from 'pinia'
import type { User } from '~/types/auth'
import type { Role, Permission } from '~/types/role'

export interface UserMembership {
  role: Role
  granted_at: string
  granted_by?: string
}

export interface UserPermissionSource {
  permission: Permission
  source: 'role' | 'direct'
  role_name?: string // If from role, which role granted it
}

export const useUserStore = defineStore('user', () => {
  const authStore = useAuthStore()

  // State
  const state = reactive({
    // Current user being viewed/edited
    currentUser: null as User | null,

    // User's role memberships
    userRoles: [] as UserMembership[],

    // User's effective permissions (from roles + direct)
    userPermissions: [] as UserPermissionSource[],

    // Loading states
    isLoadingUser: false,
    isLoadingRoles: false,
    isLoadingPermissions: false,

    // Error handling
    error: null as string | null
  })

  // Getters
  const currentUser = computed(() => state.currentUser)
  const userRoles = computed(() => state.userRoles)
  const userPermissions = computed(() => state.userPermissions)
  const isLoading = computed(() =>
    state.isLoadingUser || state.isLoadingRoles || state.isLoadingPermissions
  )
  const error = computed(() => state.error)

  /**
   * Fetch user by ID
   */
  const fetchUser = async (userId: string): Promise<User | null> => {
    try {
      state.isLoadingUser = true
      state.error = null

      const user = await authStore.apiCall<User>(`/v1/users/${userId}`)
      state.currentUser = user
      return user
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch user'
      console.error('[user.store] Failed to fetch user:', error)
      return null
    } finally {
      state.isLoadingUser = false
    }
  }

  /**
   * Fetch user's role memberships
   * In SimpleRBAC: global roles assigned to user
   * In EnterpriseRBAC: roles with entity context
   */
  const fetchUserRoles = async (userId: string): Promise<UserMembership[]> => {
    try {
      state.isLoadingRoles = true
      state.error = null

      // SimpleRBAC endpoint: /v1/users/:id/roles
      const roles = await authStore.apiCall<Role[]>(`/v1/users/${userId}/roles`)

      // Convert to UserMembership format
      state.userRoles = roles.map(role => ({
        role,
        granted_at: new Date().toISOString() // TODO: Backend should provide this
      }))

      return state.userRoles
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch user roles'
      console.error('[user.store] Failed to fetch user roles:', error)
      return []
    } finally {
      state.isLoadingRoles = false
    }
  }

  /**
   * Fetch user's effective permissions
   * Returns permissions from roles + any directly assigned permissions
   */
  const fetchUserPermissions = async (userId: string): Promise<UserPermissionSource[]> => {
    try {
      state.isLoadingPermissions = true
      state.error = null

      // SimpleRBAC endpoint: /v1/users/:id/permissions
      const permissions = await authStore.apiCall<Permission[]>(
        `/v1/users/${userId}/permissions`
      )

      // Convert to UserPermissionSource format
      // TODO: Backend should indicate source (role vs direct)
      state.userPermissions = permissions.map(permission => ({
        permission,
        source: 'role' as const // Default to role for now
      }))

      return state.userPermissions
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch user permissions'
      console.error('[user.store] Failed to fetch user permissions:', error)
      return []
    } finally {
      state.isLoadingPermissions = false
    }
  }

  /**
   * Assign a role to the user
   * SimpleRBAC: Assigns global role
   * EnterpriseRBAC: Would need entity_id parameter
   */
  const assignRole = async (userId: string, roleId: string): Promise<boolean> => {
    try {
      state.error = null

      await authStore.apiCall(`/v1/users/${userId}/roles/${roleId}`, {
        method: 'POST'
      })

      // Refresh user roles
      await fetchUserRoles(userId)

      // Show success toast
      const toast = useToast()
      toast.add({
        title: 'Role assigned',
        description: 'Role has been assigned to the user successfully',
        color: 'success'
      })

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to assign role'
      console.error('[user.store] Failed to assign role:', error)

      const toast = useToast()
      toast.add({
        title: 'Error assigning role',
        description: state.error,
        color: 'error'
      })

      return false
    }
  }

  /**
   * Remove a role from the user
   */
  const removeRole = async (userId: string, roleId: string): Promise<boolean> => {
    try {
      state.error = null

      await authStore.apiCall(`/v1/users/${userId}/roles/${roleId}`, {
        method: 'DELETE'
      })

      // Refresh user roles
      await fetchUserRoles(userId)

      // Show success toast
      const toast = useToast()
      toast.add({
        title: 'Role removed',
        description: 'Role has been removed from the user successfully',
        color: 'success'
      })

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to remove role'
      console.error('[user.store] Failed to remove role:', error)

      const toast = useToast()
      toast.add({
        title: 'Error removing role',
        description: state.error,
        color: 'error'
      })

      return false
    }
  }

  /**
   * Update user basic information
   * Note: This uses the mutation from users.store, but updates local state
   */
  const updateUser = async (userId: string, data: {
    email?: string
    full_name?: string
    is_active?: boolean
    metadata?: Record<string, any>
  }): Promise<boolean> => {
    try {
      state.error = null

      const updatedUser = await authStore.apiCall<User>(`/v1/users/${userId}`, {
        method: 'PATCH',
        body: data
      })

      state.currentUser = updatedUser

      // Show success toast
      const toast = useToast()
      toast.add({
        title: 'User updated',
        description: 'User information has been updated successfully',
        color: 'success'
      })

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to update user'
      console.error('[user.store] Failed to update user:', error)

      const toast = useToast()
      toast.add({
        title: 'Error updating user',
        description: state.error,
        color: 'error'
      })

      return false
    }
  }

  /**
   * Change user password
   */
  const changePassword = async (
    userId: string,
    currentPassword: string,
    newPassword: string
  ): Promise<boolean> => {
    try {
      state.error = null

      await authStore.apiCall(`/v1/users/${userId}/change-password`, {
        method: 'POST',
        body: {
          current_password: currentPassword,
          new_password: newPassword
        }
      })

      // Show success toast
      const toast = useToast()
      toast.add({
        title: 'Password changed',
        description: 'Password has been changed successfully',
        color: 'success'
      })

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to change password'
      console.error('[user.store] Failed to change password:', error)

      const toast = useToast()
      toast.add({
        title: 'Error changing password',
        description: state.error,
        color: 'error'
      })

      return false
    }
  }

  /**
   * Clear current user and reset state
   */
  const clearUser = (): void => {
    state.currentUser = null
    state.userRoles = []
    state.userPermissions = []
    state.error = null
  }

  /**
   * Clear error
   */
  const clearError = (): void => {
    state.error = null
  }

  return {
    // State
    state: readonly(state),

    // Getters
    currentUser,
    userRoles,
    userPermissions,
    isLoading,
    error,

    // Actions
    fetchUser,
    fetchUserRoles,
    fetchUserPermissions,
    assignRole,
    removeRole,
    updateUser,
    changePassword,
    clearUser,
    clearError
  }
})
