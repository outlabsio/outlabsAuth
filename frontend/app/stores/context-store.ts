interface OrganizationContext {
  id: string;
  name: string;
  slug: string;
  entity_type: string;
  entity_class: string;
  description?: string;
  is_system?: boolean;
}

interface ContextState {
  selectedOrganization: OrganizationContext | null;
  availableOrganizations: OrganizationContext[];
}

// System context represents platform-level administration
const SYSTEM_CONTEXT: OrganizationContext = {
  id: "system",
  name: "System Administration",
  slug: "system",
  entity_type: "SYSTEM",
  entity_class: "PLATFORM",
  is_system: true,
};

export const useContextStore = defineStore("context", {
  state: (): ContextState => ({
    selectedOrganization: null,
    availableOrganizations: [],
  }),

  actions: {
    // Set selected organization
    setSelectedOrganization(org: OrganizationContext | null) {
      this.selectedOrganization = org;
    },

    // Set available organizations
    setAvailableOrganizations(orgs: OrganizationContext[]) {
      // Always include system context for platform admins
      const withSystem = [SYSTEM_CONTEXT, ...orgs];
      this.availableOrganizations = withSystem;

      // If no organization is selected, select the first one
      if (!this.selectedOrganization && withSystem.length > 0) {
        this.selectedOrganization = withSystem[0] || null;
      }
    },

    // Clear context (on logout)
    clearContext() {
      this.selectedOrganization = null;
      this.availableOrganizations = [];
    },

    // Fetch top-level organizations from API
    async fetchOrganizations() {
      try {
        const authStore = useAuthStore();
        const response = await authStore.apiCall<OrganizationContext[] | { items: OrganizationContext[] }>("/v1/entities/top-level-organizations");

        // Handle both array response and paginated response
        const organizations = Array.isArray(response) ? response : response.items || [];
        this.setAvailableOrganizations(organizations);

        return organizations;
      } catch (error) {
        console.error("Failed to fetch organizations:", error);
        // Fallback to just system context
        this.setAvailableOrganizations([]);
        return [];
      }
    },
  },

  getters: {
    // Check if system context is selected
    isSystemContext(): boolean {
      return this.selectedOrganization?.is_system === true;
    },

    // Get headers for API requests
    getContextHeaders(): Record<string, string> {
      if (!this.selectedOrganization || this.selectedOrganization.is_system) {
        return {};
      }
      return {
        "X-Organization-Context": this.selectedOrganization.id,
      };
    },

    // Get current organization or system context
    currentOrganization(): OrganizationContext {
      return this.selectedOrganization || SYSTEM_CONTEXT;
    },
  },
});

// Export types and constants
export type { OrganizationContext };
export { SYSTEM_CONTEXT };
