/**
 * Authentication Types
 * Based on OutlabsAuth library authentication system
 */

export interface User {
  id: string
  email: string
  username: string
  full_name?: string
  is_active: boolean
  is_superuser: boolean
  created_at: string
  updated_at: string
  metadata?: Record<string, any>
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean
  isInitialized: boolean
}

export interface SystemStatus {
  initialized: boolean
  requires_setup: boolean
  admin_exists: boolean
  database_connected: boolean
}
