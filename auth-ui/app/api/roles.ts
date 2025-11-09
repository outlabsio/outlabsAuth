/**
 * Roles API
 * API functions for role management
 */

import type { Role, CreateRoleData, UpdateRoleData } from '~/types/role'
import type { PaginationParams, PaginatedResponse } from '~/types/api'
import type { RoleFilters } from '~/stores/roles.store'
import { createAPIClient } from './client'

export function createRolesAPI() {
  const client = createAPIClient()

  return {
    /**
     * Fetch roles with pagination and filters
     */
    async fetchRoles(
      filters: RoleFilters = {},
      params: PaginationParams = {}
    ): Promise<PaginatedResponse<Role>> {
      const queryString = client.buildQueryString({
        search: filters.search,
        is_global: filters.is_global,
        entity_id: filters.entity_id,
        entity_type: filters.entity_type,
        page: params.page,
        limit: params.limit,
        sort_by: params.sort_by,
        sort_order: params.sort_order
      })

      return client.call<PaginatedResponse<Role>>(`/v1/roles/${queryString}`)
    },

    /**
     * Fetch single role by ID
     */
    async fetchRole(roleId: string): Promise<Role> {
      return client.call<Role>(`/v1/roles/${roleId}`)
    },

    /**
     * Create new role
     */
    async createRole(data: CreateRoleData): Promise<Role> {
      return client.call<Role>('/v1/roles', {
        method: 'POST',
        body: JSON.stringify(data)
      })
    },

    /**
     * Update role
     */
    async updateRole(roleId: string, data: UpdateRoleData): Promise<Role> {
      return client.call<Role>(`/v1/roles/${roleId}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      })
    },

    /**
     * Delete role
     */
    async deleteRole(roleId: string): Promise<void> {
      return client.call<void>(`/v1/roles/${roleId}`, {
        method: 'DELETE'
      })
    },

    /**
     * Assign permissions to role
     */
    async assignPermissions(roleId: string, permissions: string[]): Promise<void> {
      return client.call<void>(`/v1/roles/${roleId}/permissions`, {
        method: 'POST',
        body: JSON.stringify({ permissions })
      })
    },

    /**
     * Remove permissions from role
     */
    async removePermissions(roleId: string, permissions: string[]): Promise<void> {
      return client.call<void>(`/v1/roles/${roleId}/permissions`, {
        method: 'DELETE',
        body: JSON.stringify({ permissions })
      })
    }
  }
}
