/**
 * Entity Types
 * For entity hierarchy and context management
 */

export type EntityClass = 'STRUCTURAL' | 'ACCESS_GROUP'

export interface Entity {
  id: string
  name: string
  entity_type: string
  entity_class: EntityClass
  parent_id?: string
  description?: string
  metadata?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface EntityContext {
  id: string
  name: string
  entity_type: string
  entity_class: EntityClass
  is_system?: boolean
}

// System context for platform-level admin
export const SYSTEM_CONTEXT: EntityContext = {
  id: 'system',
  name: 'System Administration',
  entity_type: 'SYSTEM',
  entity_class: 'STRUCTURAL',
  is_system: true
}
