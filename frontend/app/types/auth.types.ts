// Entity types
export interface Entity {
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  entity_class: "STRUCTURAL" | "ACCESS_GROUP";
  entity_type: string;
  parent_entity_id?: string | null;
  platform_id?: string | null;
  status: string;
  direct_permissions?: string[];
  config?: Record<string, any>;
  valid_from?: string | null;
  valid_until?: string | null;
  created_at: string;
  updated_at?: string | null;
  slug?: string;
  parent_entity?: any;
  allowed_child_types?: string[];
  allowed_entity_types?: string[];
}

// User types
export interface UserProfile {
  first_name: string;
  last_name: string;
  phone?: string | null;
  avatar_url?: string | null;
  preferences?: Record<string, any> | null;
}

export interface EntityMembership {
  id: string;
  name: string;
  slug: string;
  entity_type: string;
  entity_class: "STRUCTURAL" | "ACCESS_GROUP";
  parent_id?: string | null;
  roles: Array<{ id: string; name: string }>;
  status: string;
  joined_at: string;
}

export interface User {
  _id?: string;
  id: string;
  username?: string;
  email: string;
  profile: UserProfile;
  is_active: boolean;
  is_system_user: boolean;
  is_platform_admin?: boolean;
  is_superuser?: boolean;
  email_verified: boolean;
  last_login?: string | null;
  last_password_change?: string | null;
  created_at: string;
  updated_at: string;
  platform_id?: string | null;
  entities: EntityMembership[];
  entity_memberships?: any[];
}

// Role type
export interface Role {
  _id?: string;
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  entity_id?: string;
  entity_name?: string;
  entity?: string | Entity;
  assignable_at_types?: string[];
  is_system_role: boolean;
  is_global?: boolean;
  permissions: string[];
  platform_id?: string | null;
  assignable_at_levels?: string[];
  created_at: string;
  updated_at: string;
}

// Permission type
export interface Permission {
  _id?: string;
  id: string;
  code: string;
  name: string;
  description?: string | null;
  resource: string;
  action: string;
  scope?: string | null;
  permission_type: "system" | "custom";
  platform_id?: string | null;
  requires_all?: string[];
  requires_any?: string[];
  excludes?: string[];
  created_at: string;
  updated_at: string;
}

// Platform type
export interface Platform {
  _id?: string;
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  settings?: Record<string, any>;
  features?: string[];
  status: "active" | "inactive" | "suspended" | "maintenance" | "archived";
  created_at: string;
  updated_at: string;
}

// Auth types
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// Paginated response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Helper functions
export function isStructuralEntity(entity: Entity): boolean {
  return entity.entity_class === "STRUCTURAL";
}

export function isAccessGroup(entity: Entity): boolean {
  return entity.entity_class === "ACCESS_GROUP";
}

// Re-export commonly used types
export type EntityClass = "STRUCTURAL" | "ACCESS_GROUP";
export type PermissionType = "system" | "custom";
export type Status = "active" | "inactive" | "suspended" | "maintenance" | "archived";
