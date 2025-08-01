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
  first_name?: string | null;
  last_name?: string | null;
  phone?: string | null;
  avatar_url?: string | null;
  preferences?: Record<string, any>;
  full_name?: string;
}

export interface UserEntityRole {
  id: string;
  name: string;
  display_name: string;
  permissions: string[];
}

export interface UserEntity {
  id: string;
  name: string;
  slug: string;
  entity_type: string;
  entity_class: EntityClass;
  parent_id?: string | null;
  roles: UserEntityRole[];
  status: string;
  joined_at: string;
}

export interface User {
  id: string;
  email: string;
  profile: UserProfile;
  is_active: boolean;
  is_system_user: boolean;
  email_verified: boolean;
  last_login?: string | null;
  last_password_change?: string | null;
  created_at: string;
  updated_at?: string | null;
  entities: UserEntity[];
  failed_login_attempts?: number;
  locked_until?: string | null;
}

export interface UserListResponse {
  items: User[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UserEntityAssignment {
  entity_id: string;
  role_ids: string[];
  status?: string;
  valid_from?: string | null;
  valid_until?: string | null;
}

export interface UserCreateRequest {
  email: string;
  password?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  entity_assignments: UserEntityAssignment[];
  is_active?: boolean;
  send_welcome_email?: boolean;
}

export interface UserUpdateRequest {
  email?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  is_active?: boolean;
  entity_assignments?: UserEntityAssignment[];
}

export interface UserInviteRequest {
  email: string;
  entity_id: string;
  role_id: string;
  first_name?: string;
  last_name?: string;
  send_email?: boolean;
}

export interface UserInviteResponse {
  user: User;
  temporary_password?: string | null;
  invitation_sent: boolean;
  message: string;
}

export interface UserMembership {
  user_id: string;
  entity: {
    id: string;
    name: string;
    slug: string;
    entity_type: string;
    entity_class: EntityClass;
  };
  roles: UserEntityRole[];
  joined_at: string;
  joined_by?: {
    id: string;
    email: string;
    full_name: string;
  };
  valid_from?: string | null;
  valid_until?: string | null;
  status: string;
}

export interface UserMembershipListResponse {
  user_id: string;
  memberships: UserMembership[];
  total: number;
}

export interface EntityMember {
  id: string;
  user_id: string;
  user_email: string;
  user_name: string;
  entity_id: string;
  entity_name: string;
  entity_system_name?: string;
  roles: Array<{
    id: string;
    name: string;
    permissions: string[];
  }>;
  status: string;
  valid_from?: string | null;
  valid_until?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface UserBulkActionRequest {
  user_ids: string[];
  action: "activate" | "deactivate" | "lock";
}

export interface UserBulkActionResponse {
  successful: string[];
  failed: Array<{ user_id: string; error: string }>;
  total_processed: number;
  total_successful: number;
  total_failed: number;
}

export interface UserStatsResponse {
  total_users: number;
  active_users: number;
  inactive_users: number;
  locked_users: number;
  recent_signups: number;
  recent_logins: number;
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
  entity_system_name?: string;
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
