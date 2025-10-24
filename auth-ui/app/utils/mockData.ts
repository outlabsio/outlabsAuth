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
  // System-wide permissions
  {
    id: 'perm_1',
    name: '*:*',
    display_name: 'All Permissions',
    description: 'Full system access - grants all permissions across all resources',
    resource: '*',
    action: '*',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['system', 'admin'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },

  // User management
  {
    id: 'perm_2',
    name: 'user:read',
    display_name: 'Read Users',
    description: 'View user profiles and information',
    resource: 'user',
    action: 'read',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['user-management', 'read-only'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_3',
    name: 'user:create',
    display_name: 'Create Users',
    description: 'Create new user accounts',
    resource: 'user',
    action: 'create',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['user-management', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_4',
    name: 'user:update',
    display_name: 'Update Users',
    description: 'Modify existing user information',
    resource: 'user',
    action: 'update',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['user-management', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_5',
    name: 'user:delete',
    display_name: 'Delete Users',
    description: 'Remove user accounts from the system',
    resource: 'user',
    action: 'delete',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['user-management', 'write', 'dangerous'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_6',
    name: 'user:create_tree',
    display_name: 'Create Users (Tree)',
    description: 'Create users in current entity and all descendant entities',
    resource: 'user',
    action: 'create',
    scope: 'tree',
    is_system: true,
    is_active: true,
    tags: ['user-management', 'write', 'hierarchical'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },

  // Role management
  {
    id: 'perm_7',
    name: 'role:read',
    display_name: 'Read Roles',
    description: 'View role definitions and permissions',
    resource: 'role',
    action: 'read',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['access-control', 'read-only'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_8',
    name: 'role:create',
    display_name: 'Create Roles',
    description: 'Define new roles and assign permissions',
    resource: 'role',
    action: 'create',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['access-control', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_9',
    name: 'role:update',
    display_name: 'Update Roles',
    description: 'Modify existing role permissions',
    resource: 'role',
    action: 'update',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['access-control', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_10',
    name: 'role:delete',
    display_name: 'Delete Roles',
    description: 'Remove roles from the system',
    resource: 'role',
    action: 'delete',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['access-control', 'write', 'dangerous'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },

  // Entity management
  {
    id: 'perm_11',
    name: 'entity:read',
    display_name: 'Read Entities',
    description: 'View entity information and hierarchy',
    resource: 'entity',
    action: 'read',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['entity-management', 'read-only'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_12',
    name: 'entity:create',
    display_name: 'Create Entities',
    description: 'Create new entities in the hierarchy',
    resource: 'entity',
    action: 'create',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['entity-management', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_13',
    name: 'entity:update',
    display_name: 'Update Entities',
    description: 'Modify entity information',
    resource: 'entity',
    action: 'update',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['entity-management', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_14',
    name: 'entity:delete',
    display_name: 'Delete Entities',
    description: 'Remove entities from the hierarchy',
    resource: 'entity',
    action: 'delete',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['entity-management', 'write', 'dangerous'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_15',
    name: 'entity:read_tree',
    display_name: 'Read Entities (Tree)',
    description: 'View entity and all descendant entities in hierarchy',
    resource: 'entity',
    action: 'read',
    scope: 'tree',
    is_system: true,
    is_active: true,
    tags: ['entity-management', 'read-only', 'hierarchical'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_16',
    name: 'entity:update_tree',
    display_name: 'Update Entities (Tree)',
    description: 'Modify entity and all descendants',
    resource: 'entity',
    action: 'update',
    scope: 'tree',
    is_system: true,
    is_active: true,
    tags: ['entity-management', 'write', 'hierarchical'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },

  // Permission management
  {
    id: 'perm_17',
    name: 'permission:read',
    display_name: 'Read Permissions',
    description: 'View available permissions',
    resource: 'permission',
    action: 'read',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['access-control', 'read-only'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_18',
    name: 'permission:create',
    display_name: 'Create Permissions',
    description: 'Define new custom permissions',
    resource: 'permission',
    action: 'create',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['access-control', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_19',
    name: 'permission:update',
    display_name: 'Update Permissions',
    description: 'Modify permission definitions',
    resource: 'permission',
    action: 'update',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['access-control', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_20',
    name: 'permission:delete',
    display_name: 'Delete Permissions',
    description: 'Remove custom permissions',
    resource: 'permission',
    action: 'delete',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['access-control', 'write', 'dangerous'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },

  // API Key management
  {
    id: 'perm_21',
    name: 'api_key:read',
    display_name: 'Read API Keys',
    description: 'View API key information (excluding key values)',
    resource: 'api_key',
    action: 'read',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['api-management', 'read-only'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_22',
    name: 'api_key:create',
    display_name: 'Create API Keys',
    description: 'Generate new API keys for programmatic access',
    resource: 'api_key',
    action: 'create',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['api-management', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },
  {
    id: 'perm_23',
    name: 'api_key:revoke',
    display_name: 'Revoke API Keys',
    description: 'Invalidate and revoke API keys',
    resource: 'api_key',
    action: 'revoke',
    scope: undefined,
    is_system: true,
    is_active: true,
    tags: ['api-management', 'write'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z'
  },

  // Custom application permissions
  {
    id: 'perm_24',
    name: 'invoice:read',
    display_name: 'Read Invoices',
    description: 'View invoice information',
    resource: 'invoice',
    action: 'read',
    scope: undefined,
    is_system: false,
    is_active: true,
    tags: ['finance', 'read-only'],
    created_at: '2025-01-05T00:00:00Z',
    updated_at: '2025-01-05T00:00:00Z'
  },
  {
    id: 'perm_25',
    name: 'invoice:create',
    display_name: 'Create Invoices',
    description: 'Generate new invoices',
    resource: 'invoice',
    action: 'create',
    scope: undefined,
    is_system: false,
    is_active: true,
    tags: ['finance', 'write'],
    created_at: '2025-01-05T00:00:00Z',
    updated_at: '2025-01-05T00:00:00Z'
  },
  {
    id: 'perm_26',
    name: 'invoice:approve',
    display_name: 'Approve Invoices',
    description: 'Approve invoices for payment',
    resource: 'invoice',
    action: 'approve',
    scope: undefined,
    is_system: false,
    is_active: true,
    tags: ['finance', 'approval', 'write'],
    created_at: '2025-01-05T00:00:00Z',
    updated_at: '2025-01-05T00:00:00Z',
    metadata: {
      requiresApproval: true,
      approvalThreshold: 10000
    }
  },
  {
    id: 'perm_27',
    name: 'invoice:approve_tree',
    display_name: 'Approve Invoices (Tree)',
    description: 'Approve invoices for current entity and all descendants',
    resource: 'invoice',
    action: 'approve',
    scope: 'tree',
    is_system: false,
    is_active: true,
    tags: ['finance', 'approval', 'write', 'hierarchical'],
    created_at: '2025-01-05T00:00:00Z',
    updated_at: '2025-01-05T00:00:00Z'
  },
  {
    id: 'perm_28',
    name: 'report:read',
    display_name: 'Read Reports',
    description: 'View generated reports',
    resource: 'report',
    action: 'read',
    scope: undefined,
    is_system: false,
    is_active: true,
    tags: ['reporting', 'read-only'],
    created_at: '2025-01-08T00:00:00Z',
    updated_at: '2025-01-08T00:00:00Z'
  },
  {
    id: 'perm_29',
    name: 'report:export',
    display_name: 'Export Reports',
    description: 'Export reports in various formats',
    resource: 'report',
    action: 'export',
    scope: undefined,
    is_system: false,
    is_active: true,
    tags: ['reporting', 'export'],
    created_at: '2025-01-08T00:00:00Z',
    updated_at: '2025-01-08T00:00:00Z'
  },
  {
    id: 'perm_30',
    name: 'project:read',
    display_name: 'Read Projects',
    description: 'View project information',
    resource: 'project',
    action: 'read',
    scope: undefined,
    is_system: false,
    is_active: true,
    tags: ['project-management', 'read-only'],
    created_at: '2025-01-10T00:00:00Z',
    updated_at: '2025-01-10T00:00:00Z'
  },
  {
    id: 'perm_31',
    name: 'project:update',
    display_name: 'Update Projects',
    description: 'Modify project information',
    resource: 'project',
    action: 'update',
    scope: undefined,
    is_system: false,
    is_active: true,
    tags: ['project-management', 'write'],
    created_at: '2025-01-10T00:00:00Z',
    updated_at: '2025-01-10T00:00:00Z'
  },
  {
    id: 'perm_32',
    name: 'department:manage_tree',
    display_name: 'Manage Department (Tree)',
    description: 'Full management access to department and all sub-departments',
    resource: 'department',
    action: 'manage',
    scope: 'tree',
    is_system: false,
    is_active: true,
    tags: ['organization', 'write', 'hierarchical'],
    created_at: '2025-01-12T00:00:00Z',
    updated_at: '2025-01-12T00:00:00Z'
  },

  // Deprecated permission (example)
  {
    id: 'perm_33',
    name: 'legacy:access',
    display_name: 'Legacy System Access',
    description: 'Access to deprecated legacy system',
    resource: 'legacy',
    action: 'access',
    scope: undefined,
    is_system: false,
    is_active: false,
    tags: ['deprecated', 'legacy'],
    created_at: '2024-06-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    metadata: {
      deprecated: true,
      deprecationDate: '2025-01-01T00:00:00Z',
      replacedBy: 'project:read'
    }
  }
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
