/**
 * Users Queries
 * Pinia Colada queries and mutations for user management
 */

import { defineQueryOptions, useMutation, useQueryCache } from '@pinia/colada'
import { createUsersAPI } from '~/api/users'
import { enrichUser, enrichUsers } from '~/composables/useUserHelpers'
import type { User } from '~/types/auth'
import type { UserFilters, CreateUserData, UpdateUserData } from '~/stores/users.store'
import type { PaginationParams } from '~/types/api'

/**
 * Query Keys for users
 * Hierarchical structure for cache management
 */
export const USER_KEYS = {
  all: ['users'] as const,
  lists: () => [...USER_KEYS.all, 'list'] as const,
  list: (filters: UserFilters, params: PaginationParams) =>
    [...USER_KEYS.lists(), { filters, params }] as const,
  details: () => [...USER_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...USER_KEYS.details(), id] as const,
}

/**
 * Users Query Options
 * Reusable query definitions
 */
export const usersQueries = {
  /**
   * Query for paginated user list
   */
  list: (filters: UserFilters = {}, params: PaginationParams = {}) =>
    defineQueryOptions({
      key: USER_KEYS.list(filters, params),
      query: async () => {
        const usersAPI = createUsersAPI()
        const result = await usersAPI.fetchUsers(filters, params)
        // Enrich users with computed fields (username, full_name, is_active)
        return {
          ...result,
          items: enrichUsers(result.items)
        }
      },
      staleTime: 5000, // 5 seconds
    }),

  /**
   * Query for single user detail
   */
  detail: (id: string) =>
    defineQueryOptions({
      key: USER_KEYS.detail(id),
      query: async () => {
        const usersAPI = createUsersAPI()
        const user = await usersAPI.fetchUser(id)
        // Enrich user with computed fields (username, full_name, is_active)
        return enrichUser(user)
      },
      staleTime: 10000, // 10 seconds
    }),
}

/**
 * Create User Mutation
 * Automatically invalidates user list queries
 */
export function useCreateUserMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async (data: CreateUserData) => {
      const usersAPI = createUsersAPI()
      return usersAPI.createUser(data)
    },
    onSuccess: () => {
      // Invalidate all user list queries
      queryClient.invalidateQueries({ key: USER_KEYS.lists() })
      toast.add({
        title: 'User created',
        description: 'The user has been created successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error creating user',
        description: error.message || 'Failed to create user',
        color: 'error'
      })
    },
  })
}

/**
 * Update User Mutation
 * Automatically invalidates affected queries
 */
export function useUpdateUserMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({ userId, data }: { userId: string; data: UpdateUserData }) => {
      const usersAPI = createUsersAPI()
      return usersAPI.updateUser(userId, data)
    },
    onSuccess: (_data, { userId }) => {
      // Invalidate specific user detail
      queryClient.invalidateQueries({ key: USER_KEYS.detail(userId) })
      // Invalidate all user lists (user might appear in filtered lists)
      queryClient.invalidateQueries({ key: USER_KEYS.lists() })
      toast.add({
        title: 'User updated',
        description: 'The user has been updated successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error updating user',
        description: error.message || 'Failed to update user',
        color: 'error'
      })
    },
  })
}

/**
 * Delete User Mutation
 */
export function useDeleteUserMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async (userId: string) => {
      const usersAPI = createUsersAPI()
      return usersAPI.deleteUser(userId)
    },
    onSuccess: (_data, userId) => {
      // Invalidate to refetch fresh data
      queryClient.invalidateQueries({ key: USER_KEYS.lists() })
      // Invalidate detail query for deleted user
      queryClient.invalidateQueries({ key: USER_KEYS.detail(userId) })

      toast.add({
        title: 'User deleted',
        description: 'The user has been deleted successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error deleting user',
        description: error.message || 'Failed to delete user',
        color: 'error'
      })
    },
  })
}

/**
 * Invite User Mutation
 * Creates an INVITED user and invalidates user lists
 */
export function useInviteUserMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async (data: {
      email: string
      first_name?: string
      last_name?: string
      role_ids?: string[]
      entity_id?: string
    }) => {
      const usersAPI = createUsersAPI()
      return usersAPI.inviteUser(data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ key: USER_KEYS.lists() })
      toast.add({
        title: 'Invitation sent',
        description: 'The user has been invited successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error sending invitation',
        description: error.message || 'Failed to invite user',
        color: 'error'
      })
    },
  })
}

/**
 * Resend Invite Mutation
 */
export function useResendInviteMutation() {
  const toast = useToast()

  return useMutation({
    mutation: async (userId: string) => {
      const usersAPI = createUsersAPI()
      return usersAPI.resendInvite(userId)
    },
    onSuccess: () => {
      toast.add({
        title: 'Invitation resent',
        description: 'The invitation has been resent successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error resending invitation',
        description: error.message || 'Failed to resend invitation',
        color: 'error'
      })
    },
  })
}

/**
 * Update User Status Mutation
 * Invalidates affected user detail and list queries
 */
export function useUpdateUserStatusMutation() {
  const queryClient = useQueryCache()
  const toast = useToast()

  return useMutation({
    mutation: async ({
      userId,
      status,
      options
    }: {
      userId: string
      status: "active" | "suspended" | "banned"
      options?: {
        suspended_until?: string
        reason?: string
      }
    }) => {
      const usersAPI = createUsersAPI()
      return usersAPI.updateUserStatus(userId, status, options)
    },
    onSuccess: (_data, { userId, status }) => {
      queryClient.invalidateQueries({ key: USER_KEYS.detail(userId) })
      queryClient.invalidateQueries({ key: USER_KEYS.lists() })

      toast.add({
        title: 'User status updated',
        description: `The user is now ${status}.`,
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error updating status',
        description: error.message || 'Failed to update user status',
        color: 'error'
      })
    },
  })
}

/**
 * Change Password Mutation
 */
export function useChangePasswordMutation() {
  const toast = useToast()

  return useMutation({
    mutation: async ({
      userId,
      currentPassword,
      newPassword
    }: {
      userId: string
      currentPassword: string
      newPassword: string
    }) => {
      const usersAPI = createUsersAPI()
      return usersAPI.changePassword(userId, currentPassword, newPassword)
    },
    onSuccess: () => {
      toast.add({
        title: 'Password changed',
        description: 'The password has been changed successfully',
        color: 'success'
      })
    },
    onError: (error: any) => {
      toast.add({
        title: 'Error changing password',
        description: error.message || 'Failed to change password',
        color: 'error'
      })
    },
  })
}
