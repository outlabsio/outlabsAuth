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
    isAdmin: (state) => state.user?.is_superuser === true,
    isPlatformAdmin: (state) => state.user?.is_platform_admin === true,
    isSystemUser: (state) => state.user?.is_system_user === true,
    isVerified: (state) => state.user?.email_verified === true,
    
    // Entity memberships
    entities: (state) => state.user?.entities || [],
    currentPlatform: (state) => state.user?.platform_id || null,
    
    // Permission checks
    hasPermission: (state) => (permission: string) => {
      return state.permissions.includes(permission)
    },
  },

  actions: {
    setUser(userData: Partial<User>) {
      // Merge with defaults to handle missing fields from API
      this.user = {
        id: userData.id || '',
        email: userData.email || '',
        profile: userData.profile || { first_name: '', last_name: '' },
        is_active: userData.is_active ?? true,
        is_system_user: userData.is_system_user ?? false,
        is_platform_admin: userData.is_platform_admin ?? false,
        is_superuser: userData.is_superuser ?? false,
        email_verified: userData.email_verified ?? false,
        created_at: userData.created_at || new Date().toISOString(),
        updated_at: userData.updated_at || new Date().toISOString(),
        entities: userData.entities || [],
        ...userData
      } as User;
      
      // Extract permissions from all roles across all entities
      this.permissions = this.extractPermissions(this.user);
    },

    // Extract all permissions from user's roles
    extractPermissions(user: User): string[] {
      const permissions = new Set<string>();
      
      // Add permissions from entity memberships
      user.entities?.forEach(membership => {
        membership.roles?.forEach(role => {
          // Note: We'd need to fetch role details to get actual permissions
          // For now, we'll just store role names
          permissions.add(`role:${role.name}`);
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
