/**
 * User helper composable
 * Enriches API user data with computed fields for UI consumption
 */
import type { User } from '~/types/auth'

/**
 * Enrich user data with computed fields
 * Adds username, full_name, is_active derived from backend data
 */
export function enrichUser(user: User): User {
  return {
    ...user,
    // Derive username from email (part before @)
    username: user.email.split('@')[0],
    // Combine first_name and last_name
    full_name: [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email.split('@')[0],
    // Convert status to boolean
    is_active: user.status === 'active'
  }
}

/**
 * Enrich an array of users
 */
export function enrichUsers(users: User[]): User[] {
  return users.map(enrichUser)
}

export function useUserHelpers() {
  return {
    enrichUser,
    enrichUsers
  }
}
