import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface OrganizationContext {
  id: string;
  name: string;
  slug: string;
  entity_type: string;
  is_system?: boolean;
}

interface ContextState {
  // State
  selectedOrganization: OrganizationContext | null;
  availableOrganizations: OrganizationContext[];
  
  // Actions
  setSelectedOrganization: (org: OrganizationContext | null) => void;
  setAvailableOrganizations: (orgs: OrganizationContext[]) => void;
  clearContext: () => void;
  
  // Helpers
  isSystemContext: () => boolean;
  getContextHeaders: () => Record<string, string>;
}

// System context represents platform-level administration
const SYSTEM_CONTEXT: OrganizationContext = {
  id: 'system',
  name: 'System Administration',
  slug: 'system',
  entity_type: 'SYSTEM',
  is_system: true,
};

export const useContextStore = create<ContextState>()(
  persist(
    (set, get) => ({
      // Initial state
      selectedOrganization: null,
      availableOrganizations: [],
      
      // Set selected organization
      setSelectedOrganization: (org: OrganizationContext | null) => {
        set({ selectedOrganization: org });
      },
      
      // Set available organizations
      setAvailableOrganizations: (orgs: OrganizationContext[]) => {
        // Always include system context for platform admins
        const withSystem = [SYSTEM_CONTEXT, ...orgs];
        set({ availableOrganizations: withSystem });
        
        // If no organization is selected, select the first one
        const current = get().selectedOrganization;
        if (!current && withSystem.length > 0) {
          set({ selectedOrganization: withSystem[0] });
        }
      },
      
      // Clear context (on logout)
      clearContext: () => {
        set({ 
          selectedOrganization: null,
          availableOrganizations: [] 
        });
      },
      
      // Check if system context is selected
      isSystemContext: () => {
        const selected = get().selectedOrganization;
        return selected?.is_system === true;
      },
      
      // Get headers for API requests
      getContextHeaders: () => {
        const selected = get().selectedOrganization;
        if (!selected || selected.is_system) {
          return {};
        }
        return {
          'X-Organization-Context': selected.id,
        };
      },
    }),
    {
      name: 'context-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ 
        selectedOrganization: state.selectedOrganization,
      }),
    }
  )
);

// Export system context for easy access
export { SYSTEM_CONTEXT };