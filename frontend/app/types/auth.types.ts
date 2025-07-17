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

// Permission types
export type OperatorType = 
  | "EQUALS" 
  | "NOT_EQUALS" 
  | "LESS_THAN" 
  | "LESS_THAN_OR_EQUAL"
  | "GREATER_THAN" 
  | "GREATER_THAN_OR_EQUAL" 
  | "IN" 
  | "NOT_IN"
  | "CONTAINS" 
  | "NOT_CONTAINS" 
  | "STARTS_WITH" 
  | "ENDS_WITH"
  | "REGEX_MATCH" 
  | "EXISTS" 
  | "NOT_EXISTS";

export interface Condition {
  attribute: string; // Must start with user., resource., entity., or environment.
  operator: OperatorType;
  value: string | number | boolean | any[] | Record<string, any>;
}

export interface Permission {
  id?: string;
  name: string; // resource:action format
  display_name: string;
  description?: string;
  resource: string;
  action: string;
  scope?: string;
  entity_id?: string;
  is_system: boolean;
  is_active: boolean;
  tags: string[];
  conditions: Condition[];
  metadata: Record<string, any>;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
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
