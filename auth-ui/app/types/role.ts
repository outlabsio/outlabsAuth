/**
 * Role Types
 * Based on OutlabsAuth library role system
 */

export interface Role {
  id: string
  name: string
  display_name: string
  description?: string
  permissions: string[]
  is_global: boolean
  entity_id?: string
  entity_type?: string
  created_at: string
  updated_at: string
  metadata?: Record<string, any>
}

export interface CreateRoleData {
  name: string
  display_name: string
  description?: string
  permissions: string[]
}

export interface UpdateRoleData {
  name?: string
  display_name?: string
  description?: string
  permissions?: string[]
  is_global?: boolean
  metadata?: Record<string, any>
}

export interface Permission {
  id: string
  name: string
  display_name: string
  description?: string
  resource: string
  action: string
  scope?: string
  is_system: boolean
  is_active: boolean
  tags?: string[]
  created_at: string
  updated_at: string
  metadata?: Record<string, any>
}
