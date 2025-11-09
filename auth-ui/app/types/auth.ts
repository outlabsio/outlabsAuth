/**
 * Authentication Types
 * Based on OutlabsAuth library authentication system
 */

export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  status: string; // "active" | "suspended" | "banned" | "deleted"
  email_verified: boolean;
  is_superuser: boolean;
  created_at?: string;
  updated_at?: string;
  metadata?: Record<string, any>;

  // Computed fields (derived on frontend)
  username?: string;
  full_name?: string;
  is_active?: boolean;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isInitialized: boolean;
  config: AuthConfig | null;
  isConfigLoaded: boolean;
}

export interface SystemStatus {
  initialized: boolean;
  requires_setup: boolean;
  admin_exists: boolean;
  database_connected: boolean;
}

/**
 * Permission option for config endpoint (simplified format for UI dropdowns)
 * Note: This is different from the full Permission type in types/role.ts
 */
export interface PermissionOption {
  value: string;
  label: string;
  category: string;
  description?: string;
}

/**
 * Auth configuration from backend
 * Allows UI to detect SimpleRBAC vs EnterpriseRBAC
 */
export interface AuthConfig {
  preset: "SimpleRBAC" | "EnterpriseRBAC";
  features: {
    entity_hierarchy: boolean;
    context_aware_roles: boolean;
    abac: boolean;
    tree_permissions: boolean;
    api_keys: boolean;
    user_status: boolean;
    activity_tracking: boolean;
  };
  available_permissions: PermissionOption[];
}
