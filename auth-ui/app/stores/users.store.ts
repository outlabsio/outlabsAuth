/**
 * Users Store
 * Manages user CRUD operations, roles, and memberships
 */

import { defineStore } from 'pinia'
import type { User } from '~/types/auth'
import type { PaginationParams, PaginatedResponse } from '~/types/api'
import { USE_MOCK_DATA, mockDelay, logMockCall, mockId } from '~/utils/mock'
import { mockUsers } from '~/utils/mockData'

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

  // Mock users storage (in-memory for mock mode)
  const mockUsersData = ref<User[]>([...mockUsers])

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

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('GET', '/v1/users', { filters, params })
        await mockDelay()

        // Apply filters
        let filtered = [...mockUsersData.value]

        // Search filter (email, username, full_name)
        if (filters.search) {
          const search = filters.search.toLowerCase()
          filtered = filtered.filter(
            user =>
              user.email.toLowerCase().includes(search) ||
              user.username.toLowerCase().includes(search) ||
              user.full_name?.toLowerCase().includes(search)
          )
        }

        // Active filter
        if (filters.is_active !== undefined) {
          filtered = filtered.filter(user => user.is_active === filters.is_active)
        }

        // Superuser filter
        if (filters.is_superuser !== undefined) {
          filtered = filtered.filter(user => user.is_superuser === filters.is_superuser)
        }

        // Sorting
        const sortBy = params.sort_by || 'created_at'
        const sortOrder = params.sort_order || 'desc'
        filtered.sort((a: any, b: any) => {
          const aVal = a[sortBy]
          const bVal = b[sortBy]
          if (sortOrder === 'asc') {
            return aVal > bVal ? 1 : -1
          } else {
            return aVal < bVal ? 1 : -1
          }
        })

        // Pagination
        const page = params.page || 1
        const limit = params.limit || 20
        const total = filtered.length
        const pages = Math.ceil(total / limit)
        const startIndex = (page - 1) * limit
        const endIndex = startIndex + limit

        state.users = filtered.slice(startIndex, endIndex)
        state.pagination = {
          total,
          page,
          limit,
          pages
        }
        return
      }

      // Real API call
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

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('GET', `/v1/users/${userId}`)
        await mockDelay()

        const user = mockUsersData.value.find(u => u.id === userId)
        if (!user) {
          throw new Error('User not found')
        }

        state.selectedUser = user
        return user
      }

      // Real API call
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

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('POST', '/v1/users', data)
        await mockDelay()

        // Check if email already exists
        const emailExists = mockUsersData.value.some(u => u.email === data.email)
        if (emailExists) {
          throw new Error('Email already exists')
        }

        // Check if username already exists
        const usernameExists = mockUsersData.value.some(u => u.username === data.username)
        if (usernameExists) {
          throw new Error('Username already exists')
        }

        const newUser: User = {
          id: mockId(),
          email: data.email,
          username: data.username,
          full_name: data.full_name || '',
          is_active: data.is_active !== undefined ? data.is_active : true,
          is_superuser: data.is_superuser || false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          metadata: data.metadata || {}
        }

        mockUsersData.value.push(newUser)
        return newUser
      }

      // Real API call
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

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('PATCH', `/v1/users/${userId}`, data)
        await mockDelay()

        const userIndex = mockUsersData.value.findIndex(u => u.id === userId)
        if (userIndex === -1) {
          throw new Error('User not found')
        }

        // Check for email conflicts
        if (data.email) {
          const emailExists = mockUsersData.value.some(
            u => u.email === data.email && u.id !== userId
          )
          if (emailExists) {
            throw new Error('Email already exists')
          }
        }

        // Check for username conflicts
        if (data.username) {
          const usernameExists = mockUsersData.value.some(
            u => u.username === data.username && u.id !== userId
          )
          if (usernameExists) {
            throw new Error('Username already exists')
          }
        }

        const currentUser = mockUsersData.value[userIndex]
        if (!currentUser) {
          throw new Error('User not found')
        }

        const updatedUser: User = {
          ...currentUser,
          email: data.email ?? currentUser.email,
          username: data.username ?? currentUser.username,
          full_name: data.full_name ?? currentUser.full_name,
          is_active: data.is_active ?? currentUser.is_active,
          is_superuser: data.is_superuser ?? currentUser.is_superuser,
          metadata: data.metadata ?? currentUser.metadata,
          updated_at: new Date().toISOString()
        }

        mockUsersData.value[userIndex] = updatedUser
        state.selectedUser = updatedUser
        return updatedUser
      }

      // Real API call
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

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('DELETE', `/v1/users/${userId}`)
        await mockDelay()

        const userIndex = mockUsersData.value.findIndex(u => u.id === userId)
        if (userIndex === -1) {
          throw new Error('User not found')
        }

        mockUsersData.value.splice(userIndex, 1)

        // Remove from state.users if present
        const stateIndex = state.users.findIndex(u => u.id === userId)
        if (stateIndex !== -1) {
          state.users.splice(stateIndex, 1)
        }

        // Clear selected user if it was deleted
        if (state.selectedUser?.id === userId) {
          state.selectedUser = null
        }

        return true
      }

      // Real API call
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

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('POST', `/v1/users/${userId}/change-password`, {
          currentPassword: '***',
          newPassword: '***'
        })
        await mockDelay()

        // In mock mode, just succeed
        return true
      }

      // Real API call
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

  /**
   * Reset mock data (useful for testing)
   */
  const resetMockData = (): void => {
    if (USE_MOCK_DATA) {
      mockUsersData.value = [...mockUsers]
      state.users = []
      state.selectedUser = null
      state.error = null
    }
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
    clearError,
    resetMockData
  }
})
