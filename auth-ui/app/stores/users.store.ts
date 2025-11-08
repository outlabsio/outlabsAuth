/**
 * Users Store
 * Manages user CRUD operations, roles, and memberships
 */

import { defineStore } from 'pinia'
import type { User } from '~/types/auth'
import type { PaginationParams, PaginatedResponse } from '~/types/api'

export interface UserFilters {
  search?: string
  is_active?: boolean
  is_superuser?: boolean
  entity_id?: string
}

export interface CreateUserData {
  email: string
  username: string
  password: string
  full_name?: string
  is_active?: boolean
  is_superuser?: boolean
  metadata?: Record<string, any>
}

export interface UpdateUserData {
  email?: string
  username?: string
  full_name?: string
  is_active?: boolean
  is_superuser?: boolean
  metadata?: Record<string, any>
}

export const useUsersStore = defineStore('users', () => {
  const authStore = useAuthStore()

  // State
  const state = reactive({
    users: [] as User[],
    selectedUser: null as User | null,
    isLoading: false,
    error: null as string | null,
    pagination: {
      total: 0,
      page: 1,
      limit: 20,
      pages: 0
    }
  })

  // Getters
  const users = computed(() => state.users)
  const selectedUser = computed(() => state.selectedUser)
  const isLoading = computed(() => state.isLoading)
  const error = computed(() => state.error)
  const pagination = computed(() => state.pagination)

  /**
   * Fetch users with pagination, search, and filters
   */
  const fetchUsers = async (
    filters: UserFilters = {},
    params: PaginationParams = {}
  ): Promise<void> => {
    try {
      state.isLoading = true
      state.error = null

      const queryParams = new URLSearchParams()
      if (filters.search) queryParams.append('search', filters.search)
      if (filters.is_active !== undefined) queryParams.append('is_active', String(filters.is_active))
      if (filters.is_superuser !== undefined) queryParams.append('is_superuser', String(filters.is_superuser))
      if (filters.entity_id) queryParams.append('entity_id', filters.entity_id)
      if (params.page) queryParams.append('page', String(params.page))
      if (params.limit) queryParams.append('limit', String(params.limit))
      if (params.sort_by) queryParams.append('sort_by', params.sort_by)
      if (params.sort_order) queryParams.append('sort_order', params.sort_order)

      const response = await authStore.apiCall<PaginatedResponse<User>>(
        `/v1/users?${queryParams.toString()}`
      )

      state.users = response.items
      state.pagination = {
        total: response.total,
        page: response.page,
        limit: response.limit,
        pages: response.pages
      }
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch users'
      console.error('Failed to fetch users:', error)
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Fetch single user by ID
   */
  const fetchUser = async (userId: string): Promise<User | null> => {
    try {
      state.isLoading = true
      state.error = null

      const user = await authStore.apiCall<User>(`/v1/users/${userId}`)
      state.selectedUser = user
      return user
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch user'
      console.error('Failed to fetch user:', error)
      return null
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Create new user
   */
  const createUser = async (data: CreateUserData): Promise<User | null> => {
    try {
      state.isLoading = true
      state.error = null

      const user = await authStore.apiCall<User>('/v1/users', {
        method: 'POST',
        body: JSON.stringify(data)
      })

      return user
    } catch (error: any) {
      state.error = error.message || 'Failed to create user'
      console.error('Failed to create user:', error)
      throw error
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Update user
   */
  const updateUser = async (userId: string, data: UpdateUserData): Promise<User | null> => {
    try {
      state.isLoading = true
      state.error = null

      const user = await authStore.apiCall<User>(`/v1/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      })

      state.selectedUser = user
      return user
    } catch (error: any) {
      state.error = error.message || 'Failed to update user'
      console.error('Failed to update user:', error)
      throw error
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Delete user
   */
  const deleteUser = async (userId: string): Promise<boolean> => {
    try {
      state.isLoading = true
      state.error = null

      await authStore.apiCall(`/v1/users/${userId}`, {
        method: 'DELETE'
      })

      // Remove from local state
      const stateIndex = state.users.findIndex(u => u.id === userId)
      if (stateIndex !== -1) {
        state.users.splice(stateIndex, 1)
      }

      if (state.selectedUser?.id === userId) {
        state.selectedUser = null
      }

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to delete user'
      console.error('Failed to delete user:', error)
      return false
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Activate user
   */
  const activateUser = async (userId: string): Promise<boolean> => {
    try {
      const user = await updateUser(userId, { is_active: true })
      return user !== null
    } catch (error) {
      return false
    }
  }

  /**
   * Deactivate user
   */
  const deactivateUser = async (userId: string): Promise<boolean> => {
    try {
      const user = await updateUser(userId, { is_active: false })
      return user !== null
    } catch (error) {
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
      state.isLoading = true
      state.error = null

      await authStore.apiCall(`/v1/users/${userId}/change-password`, {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      })

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to change password'
      console.error('Failed to change password:', error)
      return false
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Clear selected user
   */
  const clearSelectedUser = (): void => {
    state.selectedUser = null
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
    users,
    selectedUser,
    isLoading,
    error,
    pagination,

    // Actions
    fetchUsers,
    fetchUser,
    createUser,
    updateUser,
    deleteUser,
    activateUser,
    deactivateUser,
    changePassword,
    clearSelectedUser,
    clearError
  }
})
