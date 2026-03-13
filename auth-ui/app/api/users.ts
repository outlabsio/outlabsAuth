/**
 * Users API
 * API functions for user management
 */

import type { User } from '~/types/auth'
import type { PaginationParams, PaginatedResponse } from '~/types/api'
import type { UserFilters, CreateUserData, UpdateUserData } from '~/stores/users.store'
import { createAPIClient } from './client'

export function createUsersAPI() {
  const client = createAPIClient()
  const authStore = useAuthStore()

  return {
    /**
     * Fetch users with pagination and filters
     */
    async fetchUsers(
      filters: UserFilters = {},
      params: PaginationParams = {}
    ): Promise<PaginatedResponse<User>> {
      const queryString = client.buildQueryString({
        search: filters.search,
        status: filters.status,
        is_superuser: filters.is_superuser,
        entity_id: filters.entity_id,
        page: params.page,
        limit: params.limit,
        sort_by: params.sort_by,
        sort_order: params.sort_order
      })

      return client.call<PaginatedResponse<User>>(`/v1/users${queryString}`)
    },

    /**
     * Fetch single user by ID
     */
    async fetchUser(userId: string): Promise<User> {
      return client.call<User>(`/v1/users/${userId}`)
    },

    /**
     * Create new user
     */
    async createUser(data: CreateUserData): Promise<User> {
      return client.call<User>('/v1/users', {
        method: 'POST',
        body: data
      })
    },

    /**
     * Update user
     */
    async updateUser(userId: string, data: UpdateUserData): Promise<User> {
      return client.call<User>(`/v1/users/${userId}`, {
        method: 'PATCH',
        body: data
      })
    },

    /**
     * Delete user
     */
    async deleteUser(userId: string): Promise<void> {
      return client.call<void>(`/v1/users/${userId}`, {
        method: 'DELETE'
      })
    },

    /**
     * Change user password
     */
    /**
     * Invite a user by email
     */
    async inviteUser(data: {
      email: string
      first_name?: string
      last_name?: string
      role_ids?: string[]
      entity_id?: string
    }): Promise<User> {
      return client.call<User>('/v1/auth/invite', {
        method: 'POST',
        body: data
      })
    },

    /**
     * Resend invitation to an INVITED user
     */
    async resendInvite(userId: string): Promise<User> {
      return client.call<User>(`/v1/users/${userId}/resend-invite`, {
        method: 'POST'
      })
    },

    async changePassword(
      userId: string,
      currentPassword: string,
      newPassword: string
    ): Promise<void> {
      const currentUserId = authStore.currentUser?.id
      const isSelfChange = userId === 'me' || userId === currentUserId

      if (isSelfChange) {
        return client.call<void>('/v1/users/me/change-password', {
          method: 'POST',
          body: {
            current_password: currentPassword,
            new_password: newPassword
          }
        })
      }

      return client.call<void>(`/v1/users/${userId}/password`, {
        method: 'PATCH',
        body: {
          new_password: newPassword
        }
      })
    }
  }
}
