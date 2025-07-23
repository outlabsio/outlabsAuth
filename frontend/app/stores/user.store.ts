import type { User } from '~/types/auth.types'

interface UserState {
  user: User | null;
  permissions: string[];
  language: string;
}

export const useUserStore = defineStore("user", {
  state: (): UserState => {
    // Try to get language from localStorage
    let language = "en";
    if (typeof localStorage !== "undefined") {
      const savedLang = localStorage.getItem("outlabs-language");
      if (savedLang) {
        language = savedLang;
      }
    }

    return {
      user: null,
      permissions: [],
      language,
    };
  },

  getters: {
    // User properties
    id: (state) => state.user?.id || null,
    email: (state) => state.user?.email || null,
    username: (state) => state.user?.username || null,
    fullName: (state) => {
      if (!state.user?.profile) return null
      const { first_name, last_name } = state.user.profile
      return [first_name, last_name].filter(Boolean).join(' ') || null
    },
    
    // Role checks
    isAdmin: (state) => {
      // Check if user has system_admin role or wildcard permission
      if (!state.user?.entities) return false;
      
      return state.user.entities.some(entity => 
        entity.roles?.some(role => 
          role.name === 'system_admin' || role.permissions?.includes('*')
        )
      );
    },
    isPlatformAdmin: (state) => {
      // Check if user has platform_admin role
      if (!state.user?.entities) return false;
      
      return state.user.entities.some(entity => 
        entity.roles?.some(role => 
          role.name === 'platform_admin' || role.name === 'platform_administrator'
        )
      );
    },
    isSystemUser: (state) => state.user?.is_system_user === true,
    isVerified: (state) => state.user?.email_verified === true,
    
    // Entity memberships
    entities: (state) => state.user?.entities || [],
    currentPlatform: (state) => state.user?.platform_id || null,
    
    // Permission checks
    hasPermission: (state) => (permission: string) => {
      // Check for wildcard permission
      if (state.permissions.includes('*')) {
        return true;
      }
      return state.permissions.includes(permission)
    },
  },

  actions: {
    setUser(userData: Partial<User>) {
      console.log('[UserStore] Setting user with data:', userData);
      
      // Merge with defaults to handle missing fields from API
      this.user = {
        id: userData.id || '',
        email: userData.email || '',
        profile: userData.profile || { first_name: '', last_name: '' },
        is_active: userData.is_active ?? true,
        is_system_user: userData.is_system_user ?? false,
        email_verified: userData.email_verified ?? false,
        created_at: userData.created_at || new Date().toISOString(),
        updated_at: userData.updated_at || new Date().toISOString(),
        entities: userData.entities || [],
        ...userData
      } as User;
      
      console.log('[UserStore] User entities:', this.user.entities);
      
      // Extract permissions from all roles across all entities
      this.permissions = this.extractPermissions(this.user);
      console.log('[UserStore] Extracted permissions:', this.permissions);
    },

    // Extract all permissions from user's roles
    extractPermissions(user: User): string[] {
      const permissions = new Set<string>();
      
      console.log('[UserStore] Extracting permissions from entities:', user.entities);
      
      // Add permissions from entity memberships
      user.entities?.forEach(membership => {
        console.log('[UserStore] Processing membership:', membership);
        membership.roles?.forEach(role => {
          console.log('[UserStore] Processing role:', role);
          // Add all permissions from this role
          role.permissions?.forEach(permission => {
            permissions.add(permission);
          });
          
          // Check for wildcard permission
          if (role.permissions?.includes('*')) {
            console.log('[UserStore] Found wildcard permission!');
            // If user has wildcard permission, they have all permissions
            // Add common permissions that might be checked
            const allPermissions = [
              'member:create', 'member:read', 'member:update', 'member:delete',
              'member:create_tree', 'member:read_tree', 'member:update_tree', 'member:delete_tree',
              'member:create_all', 'member:read_all', 'member:update_all', 'member:delete_all',
              'entity:create', 'entity:read', 'entity:update', 'entity:delete',
              'entity:create_tree', 'entity:read_tree', 'entity:update_tree', 'entity:delete_tree',
              'entity:create_all', 'entity:read_all', 'entity:update_all', 'entity:delete_all',
              'user:create', 'user:read', 'user:update', 'user:delete',
              'user:create_all', 'user:read_all', 'user:update_all', 'user:delete_all',
              'role:create', 'role:read', 'role:update', 'role:delete',
              'role:create_all', 'role:read_all', 'role:update_all', 'role:delete_all',
              'permission:create', 'permission:read', 'permission:update', 'permission:delete',
              'permission:create_all', 'permission:read_all', 'permission:update_all', 'permission:delete_all'
            ];
            allPermissions.forEach(p => permissions.add(p));
          }
        });
      });
      
      return Array.from(permissions);
    },

    // Set user language preference
    setLanguage(lang: string) {
      this.language = lang;
      // Save to localStorage for persistence
      localStorage.setItem("outlabs-language", lang);
    },

    // Hierarchical permission check
    can(permission: string, entityId?: string): boolean {
      // Superusers can do anything
      if (this.isAdmin) return true;
      
      // Platform admins can manage their platform
      if (this.isPlatformAdmin && permission.startsWith('platform:')) {
        return true;
      }
      
      // Check specific permissions
      return this.hasPermission(permission);
    },
    
    // Check if user has a specific role in an entity
    hasRoleInEntity(roleId: string, entityId: string): boolean {
      const membership = this.entities.find(e => e.id === entityId);
      if (!membership) return false;
      
      return membership.roles.some(r => r.id === roleId);
    },
    
    // Clear user data
    clear() {
      this.$reset();
    }
  },
});
