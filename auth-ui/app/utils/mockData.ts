/**
 * Mock Data for Development
 * Realistic sample data for testing UI without backend
 */

import type { User } from '~/types/auth'
import type { Entity, EntityContext } from '~/types/entity'

// Mock Users
export const mockUsers: User[] = [
  {
    id: 'user_1',
    email: 'admin@outlabs.com',
    username: 'admin',
    full_name: 'Admin User',
    is_active: true,
    is_superuser: true,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-15T00:00:00Z',
    metadata: {
      avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=admin',
      department: 'Engineering',
      title: 'System Administrator'
    }
  },
  {
    id: 'user_2',
    email: 'john.doe@outlabs.com',
    username: 'johndoe',
    full_name: 'John Doe',
    is_active: true,
    is_superuser: false,
    created_at: '2025-01-05T00:00:00Z',
    updated_at: '2025-01-14T00:00:00Z',
    metadata: {
      avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=john',
      department: 'Engineering',
      title: 'Senior Developer'
    }
  },
  {
    id: 'user_3',
    email: 'jane.smith@outlabs.com',
    username: 'janesmith',
    full_name: 'Jane Smith',
    is_active: true,
    is_superuser: false,
    created_at: '2025-01-10T00:00:00Z',
    updated_at: '2025-01-15T00:00:00Z',
    metadata: {
      avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=jane',
      department: 'Sales',
      title: 'Sales Manager'
    }
  },
  {
    id: 'user_4',
    email: 'bob.wilson@outlabs.com',
    username: 'bobwilson',
    full_name: 'Bob Wilson',
    is_active: true,
    is_superuser: false,
    created_at: '2025-01-12T00:00:00Z',
    updated_at: '2025-01-15T00:00:00Z',
    metadata: {
      avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=bob',
      department: 'Engineering',
      title: 'Frontend Developer'
    }
  },
  {
    id: 'user_5',
    email: 'alice.brown@outlabs.com',
    username: 'alicebrown',
    full_name: 'Alice Brown',
    is_active: false,
    is_superuser: false,
    created_at: '2025-01-08T00:00:00Z',
    updated_at: '2025-01-15T00:00:00Z',
    metadata: {
      avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=alice',
      department: 'Marketing',
      title: 'Marketing Specialist'
    }
  }
]

// Mock Roles
export const mockRoles = [
  {
    id: 'role_1',
    name: 'admin',
    display_name: 'Administrator',
    description: 'Full system access',
    permissions: ['*:*'],
    is_global: true,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'role_2',
    name: 'manager',
    display_name: 'Manager',
    description: 'Manage team members and resources',
    permissions: [
      'user:read',
      'user:update',
      'entity:read',
      'entity:update_tree',
      'role:read'
    ],
    is_global: false,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-10T00:00:00Z'
  },
  {
    id: 'role_3',
    name: 'developer',
    display_name: 'Developer',
    description: 'Access to development resources',
    permissions: [
      'user:read',
      'entity:read',
      'project:read',
      'project:update'
    ],
    is_global: false,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-05T00:00:00Z'
  },
  {
    id: 'role_4',
    name: 'viewer',
    display_name: 'Viewer',
    description: 'Read-only access',
    permissions: [
      'user:read',
      'entity:read',
      'role:read'
    ],
    is_global: true,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  }
]

// Mock Entities
export const mockEntities: Entity[] = [
  {
    id: 'entity_1',
    name: 'Outlabs',
    entity_type: 'organization',
    entity_class: 'STRUCTURAL',
    parent_id: undefined,
    description: 'Main organization',
    metadata: {
      industry: 'Technology',
      founded: '2020'
    },
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'entity_2',
    name: 'Engineering',
    entity_type: 'department',
    entity_class: 'STRUCTURAL',
    parent_id: 'entity_1',
    description: 'Engineering department',
    metadata: {
      team_size: 15,
      budget: 500000
    },
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-10T00:00:00Z'
  },
  {
    id: 'entity_3',
    name: 'Backend Team',
    entity_type: 'team',
    entity_class: 'STRUCTURAL',
    parent_id: 'entity_2',
    description: 'Backend development team',
    metadata: {
      tech_stack: ['Python', 'FastAPI', 'MongoDB']
    },
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-12T00:00:00Z'
  },
  {
    id: 'entity_4',
    name: 'Frontend Team',
    entity_type: 'team',
    entity_class: 'STRUCTURAL',
    parent_id: 'entity_2',
    description: 'Frontend development team',
    metadata: {
      tech_stack: ['Vue', 'Nuxt', 'TypeScript']
    },
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-12T00:00:00Z'
  },
  {
    id: 'entity_5',
    name: 'Sales',
    entity_type: 'department',
    entity_class: 'STRUCTURAL',
    parent_id: 'entity_1',
    description: 'Sales department',
    metadata: {
      team_size: 8,
      budget: 300000
    },
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-08T00:00:00Z'
  },
  {
    id: 'entity_6',
    name: 'Project Alpha',
    entity_type: 'project',
    entity_class: 'ACCESS_GROUP',
    parent_id: 'entity_1',
    description: 'Cross-functional project team',
    metadata: {
      status: 'active',
      deadline: '2025-06-30'
    },
    created_at: '2025-01-05T00:00:00Z',
    updated_at: '2025-01-15T00:00:00Z'
  }
]

// Mock Entity Contexts (for context switcher)
export const mockEntityContexts: EntityContext[] = [
  {
    id: 'entity_1',
    name: 'Outlabs',
    entity_type: 'organization',
    entity_class: 'STRUCTURAL',
    is_system: false
  },
  {
    id: 'entity_2',
    name: 'Engineering',
    entity_type: 'department',
    entity_class: 'STRUCTURAL',
    is_system: false
  },
  {
    id: 'entity_3',
    name: 'Backend Team',
    entity_type: 'team',
    entity_class: 'STRUCTURAL',
    is_system: false
  }
]

// Mock Permissions
export const mockPermissions = [
  { id: 'perm_1', name: 'user:read', description: 'Read user information' },
  { id: 'perm_2', name: 'user:create', description: 'Create new users' },
  { id: 'perm_3', name: 'user:update', description: 'Update user information' },
  { id: 'perm_4', name: 'user:delete', description: 'Delete users' },
  { id: 'perm_5', name: 'user:manage', description: 'Full user management' },
  { id: 'perm_6', name: 'role:read', description: 'Read role information' },
  { id: 'perm_7', name: 'role:create', description: 'Create new roles' },
  { id: 'perm_8', name: 'role:update', description: 'Update roles' },
  { id: 'perm_9', name: 'role:delete', description: 'Delete roles' },
  { id: 'perm_10', name: 'entity:read', description: 'Read entity information' },
  { id: 'perm_11', name: 'entity:create', description: 'Create new entities' },
  { id: 'perm_12', name: 'entity:update', description: 'Update entities' },
  { id: 'perm_13', name: 'entity:update_tree', description: 'Update entity and descendants' },
  { id: 'perm_14', name: 'entity:delete', description: 'Delete entities' },
  { id: 'perm_15', name: '*:*', description: 'Full system access' }
]

// Mock API Keys
export const mockApiKeys = [
  {
    id: 'key_1',
    name: 'Production API',
    prefix: 'ola_prod_',
    key: 'ola_prod_****************************abcd',
    created_at: '2025-01-10T00:00:00Z',
    last_used_at: '2025-01-15T10:30:00Z',
    expires_at: '2026-01-10T00:00:00Z',
    is_active: true,
    metadata: {
      environment: 'production',
      service: 'api-gateway'
    }
  },
  {
    id: 'key_2',
    name: 'Development API',
    prefix: 'ola_dev_',
    key: 'ola_dev_****************************xyz1',
    created_at: '2025-01-12T00:00:00Z',
    last_used_at: '2025-01-15T14:20:00Z',
    expires_at: '2025-04-12T00:00:00Z',
    is_active: true,
    metadata: {
      environment: 'development',
      service: 'test-service'
    }
  },
  {
    id: 'key_3',
    name: 'Legacy API',
    prefix: 'ola_leg_',
    key: 'ola_leg_****************************old9',
    created_at: '2024-06-01T00:00:00Z',
    last_used_at: '2024-12-20T00:00:00Z',
    expires_at: null,
    is_active: false,
    metadata: {
      environment: 'production',
      service: 'legacy-system',
      deprecated: true
    }
  }
]

// Helper function to get mock user by credentials
export const getMockUserByCredentials = (email: string, password: string): User | null => {
  // For demo: any password works with existing users
  return mockUsers.find(u => u.email === email) || null
}

// Helper function to get entity hierarchy
export const getMockEntityHierarchy = (entityId: string) => {
  const entity = mockEntities.find(e => e.id === entityId)
  if (!entity) return null

  // Get path (all ancestors)
  const path: Entity[] = []
  let current = entity
  while (current) {
    path.unshift(current)
    if (current.parent_id) {
      current = mockEntities.find(e => e.id === current.parent_id)!
    } else {
      break
    }
  }

  // Get descendants (all children recursively)
  const descendants: Entity[] = []
  const findDescendants = (parentId: string) => {
    const children = mockEntities.filter(e => e.parent_id === parentId)
    children.forEach(child => {
      descendants.push(child)
      findDescendants(child.id)
    })
  }
  findDescendants(entityId)

  return { path, descendants }
}
