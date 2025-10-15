/**
 * Roles Store
 * Manages role CRUD operations and permission assignments
 */

import { defineStore } from 'pinia'
import type { Role, CreateRoleData, UpdateRoleData } from '~/types/role'
import type { PaginationParams, PaginatedResponse } from '~/types/api'
import { USE_MOCK_DATA, mockDelay, logMockCall, mockId } from '~/utils/mock'
import { mockRoles } from '~/utils/mockData'

export interface RoleFilters {
  search?: string
  is_global?: boolean
  entity_id?: string
  entity_type?: string
}

export const useRolesStore = defineStore('roles', () => {
  const authStore = useAuthStore()

  // State
  const state = reactive({
    roles: [] as Role[],
    selectedRole: null as Role | null,
    isLoading: false,
    error: null as string | null,
    pagination: {
      total: 0,
      page: 1,
      limit: 20,
      pages: 0
    }
  })

  // Mock roles storage (in-memory for mock mode)
  const mockRolesData = ref<Role[]>([...mockRoles])

  // Getters
  const roles = computed(() => state.roles)
  const selectedRole = computed(() => state.selectedRole)
  const isLoading = computed(() => state.isLoading)
  const error = computed(() => state.error)
  const pagination = computed(() => state.pagination)

  // Get global roles
  const globalRoles = computed(() => state.roles.filter(r => r.is_global))

  // Get context-specific roles
  const contextRoles = computed(() => state.roles.filter(r => !r.is_global))

  /**
   * Fetch roles with pagination, search, and filters
   */
  const fetchRoles = async (
    filters: RoleFilters = {},
    params: PaginationParams = {}
  ): Promise<void> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('GET', '/v1/roles', { filters, params })
        await mockDelay()

        // Apply filters
        let filtered = [...mockRolesData.value]

        // Search filter (name, display_name, description)
        if (filters.search) {
          const search = filters.search.toLowerCase()
          filtered = filtered.filter(
            role =>
              role.name.toLowerCase().includes(search) ||
              role.display_name.toLowerCase().includes(search) ||
              role.description?.toLowerCase().includes(search)
          )
        }

        // Global filter
        if (filters.is_global !== undefined) {
          filtered = filtered.filter(role => role.is_global === filters.is_global)
        }

        // Entity filter
        if (filters.entity_id) {
          filtered = filtered.filter(role => role.entity_id === filters.entity_id)
        }

        // Entity type filter
        if (filters.entity_type) {
          filtered = filtered.filter(role => role.entity_type === filters.entity_type)
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

        state.roles = filtered.slice(startIndex, endIndex)
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
      if (filters.is_global !== undefined) queryParams.append('is_global', String(filters.is_global))
      if (filters.entity_id) queryParams.append('entity_id', filters.entity_id)
      if (filters.entity_type) queryParams.append('entity_type', filters.entity_type)
      if (params.page) queryParams.append('page', String(params.page))
      if (params.limit) queryParams.append('limit', String(params.limit))
      if (params.sort_by) queryParams.append('sort_by', params.sort_by)
      if (params.sort_order) queryParams.append('sort_order', params.sort_order)

      const response = await authStore.apiCall<PaginatedResponse<Role>>(
        `/v1/roles?${queryParams.toString()}`
      )

      state.roles = response.items
      state.pagination = {
        total: response.total,
        page: response.page,
        limit: response.limit,
        pages: response.pages
      }
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch roles'
      console.error('Failed to fetch roles:', error)
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Fetch single role by ID
   */
  const fetchRole = async (roleId: string): Promise<Role | null> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('GET', `/v1/roles/${roleId}`)
        await mockDelay()

        const role = mockRolesData.value.find(r => r.id === roleId)
        if (!role) {
          throw new Error('Role not found')
        }

        state.selectedRole = role
        return role
      }

      // Real API call
      const role = await authStore.apiCall<Role>(`/v1/roles/${roleId}`)
      state.selectedRole = role
      return role
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch role'
      console.error('Failed to fetch role:', error)
      return null
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Create new role
   */
  const createRole = async (data: CreateRoleData): Promise<Role | null> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('POST', '/v1/roles', data)
        await mockDelay()

        // Check if name already exists
        const nameExists = mockRolesData.value.some(r => r.name === data.name)
        if (nameExists) {
          throw new Error('Role name already exists')
        }

        const newRole: Role = {
          id: mockId(),
          name: data.name,
          display_name: data.display_name,
          description: data.description || '',
          permissions: data.permissions || [],
          is_global: data.is_global !== undefined ? data.is_global : false,
          entity_id: data.entity_id,
          entity_type: data.entity_type,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          metadata: data.metadata || {}
        }

        mockRolesData.value.push(newRole)
        return newRole
      }

      // Real API call
      const role = await authStore.apiCall<Role>('/v1/roles', {
        method: 'POST',
        body: JSON.stringify(data)
      })

      return role
    } catch (error: any) {
      state.error = error.message || 'Failed to create role'
      console.error('Failed to create role:', error)
      throw error
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Update role
   */
  const updateRole = async (roleId: string, data: UpdateRoleData): Promise<Role | null> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('PATCH', `/v1/roles/${roleId}`, data)
        await mockDelay()

        const roleIndex = mockRolesData.value.findIndex(r => r.id === roleId)
        if (roleIndex === -1) {
          throw new Error('Role not found')
        }

        // Check for name conflicts
        if (data.name) {
          const nameExists = mockRolesData.value.some(
            r => r.name === data.name && r.id !== roleId
          )
          if (nameExists) {
            throw new Error('Role name already exists')
          }
        }

        const currentRole = mockRolesData.value[roleIndex]
        if (!currentRole) {
          throw new Error('Role not found')
        }

        const updatedRole: Role = {
          ...currentRole,
          name: data.name ?? currentRole.name,
          display_name: data.display_name ?? currentRole.display_name,
          description: data.description ?? currentRole.description,
          permissions: data.permissions ?? currentRole.permissions,
          is_global: data.is_global ?? currentRole.is_global,
          metadata: data.metadata ?? currentRole.metadata,
          updated_at: new Date().toISOString()
        }

        mockRolesData.value[roleIndex] = updatedRole
        state.selectedRole = updatedRole
        return updatedRole
      }

      // Real API call
      const role = await authStore.apiCall<Role>(`/v1/roles/${roleId}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      })

      state.selectedRole = role
      return role
    } catch (error: any) {
      state.error = error.message || 'Failed to update role'
      console.error('Failed to update role:', error)
      throw error
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Delete role
   */
  const deleteRole = async (roleId: string): Promise<boolean> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('DELETE', `/v1/roles/${roleId}`)
        await mockDelay()

        const roleIndex = mockRolesData.value.findIndex(r => r.id === roleId)
        if (roleIndex === -1) {
          throw new Error('Role not found')
        }

        mockRolesData.value.splice(roleIndex, 1)

        // Remove from state.roles if present
        const stateIndex = state.roles.findIndex(r => r.id === roleId)
        if (stateIndex !== -1) {
          state.roles.splice(stateIndex, 1)
        }

        // Clear selected role if it was deleted
        if (state.selectedRole?.id === roleId) {
          state.selectedRole = null
        }

        return true
      }

      // Real API call
      await authStore.apiCall(`/v1/roles/${roleId}`, {
        method: 'DELETE'
      })

      // Remove from local state
      const stateIndex = state.roles.findIndex(r => r.id === roleId)
      if (stateIndex !== -1) {
        state.roles.splice(stateIndex, 1)
      }

      if (state.selectedRole?.id === roleId) {
        state.selectedRole = null
      }

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to delete role'
      console.error('Failed to delete role:', error)
      return false
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Assign permissions to role
   */
  const assignPermissions = async (
    roleId: string,
    permissions: string[]
  ): Promise<boolean> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('POST', `/v1/roles/${roleId}/permissions`, { permissions })
        await mockDelay()

        const roleIndex = mockRolesData.value.findIndex(r => r.id === roleId)
        if (roleIndex === -1) {
          throw new Error('Role not found')
        }

        // Add new permissions (avoid duplicates)
        const role = mockRolesData.value[roleIndex]
        if (role) {
          const existingPermissions = role.permissions
          const newPermissions = [...new Set([...existingPermissions, ...permissions])]

          role.permissions = newPermissions
          role.updated_at = new Date().toISOString()

          if (state.selectedRole?.id === roleId) {
            state.selectedRole.permissions = newPermissions
            state.selectedRole.updated_at = new Date().toISOString()
          }
        }

        return true
      }

      // Real API call
      await authStore.apiCall(`/v1/roles/${roleId}/permissions`, {
        method: 'POST',
        body: JSON.stringify({ permissions })
      })

      // Refresh role data
      await fetchRole(roleId)
      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to assign permissions'
      console.error('Failed to assign permissions:', error)
      return false
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Remove permissions from role
   */
  const removePermissions = async (
    roleId: string,
    permissions: string[]
  ): Promise<boolean> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('DELETE', `/v1/roles/${roleId}/permissions`, { permissions })
        await mockDelay()

        const roleIndex = mockRolesData.value.findIndex(r => r.id === roleId)
        if (roleIndex === -1) {
          throw new Error('Role not found')
        }

        // Remove permissions
        const role = mockRolesData.value[roleIndex]
        if (role) {
          const existingPermissions = role.permissions
          const newPermissions = existingPermissions.filter(p => !permissions.includes(p))

          role.permissions = newPermissions
          role.updated_at = new Date().toISOString()

          if (state.selectedRole?.id === roleId) {
            state.selectedRole.permissions = newPermissions
            state.selectedRole.updated_at = new Date().toISOString()
          }
        }

        return true
      }

      // Real API call
      await authStore.apiCall(`/v1/roles/${roleId}/permissions`, {
        method: 'DELETE',
        body: JSON.stringify({ permissions })
      })

      // Refresh role data
      await fetchRole(roleId)
      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to remove permissions'
      console.error('Failed to remove permissions:', error)
      return false
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Clear selected role
   */
  const clearSelectedRole = (): void => {
    state.selectedRole = null
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
      mockRolesData.value = [...mockRoles]
      state.roles = []
      state.selectedRole = null
      state.error = null
    }
  }

  return {
    // State
    state: readonly(state),

    // Getters
    roles,
    selectedRole,
    isLoading,
    error,
    pagination,
    globalRoles,
    contextRoles,

    // Actions
    fetchRoles,
    fetchRole,
    createRole,
    updateRole,
    deleteRole,
    assignPermissions,
    removePermissions,
    clearSelectedRole,
    clearError,
    resetMockData
  }
})
