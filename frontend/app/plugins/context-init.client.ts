export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore();
  const contextStore = useContextStore();

  // Load persisted organization first
  contextStore.loadPersistedOrganization();

  // Only initialize context if user is authenticated
  if (authStore.isAuthenticated) {
    try {
      // Fetch available organizations
      await contextStore.fetchOrganizations();

      console.log("Context initialized:", {
        selectedOrg: contextStore.selectedOrganization?.name,
        availableOrgs: contextStore.availableOrganizations.map((org) => org.name),
        isSystemContext: contextStore.isSystemContext,
        persistedFromStorage: !!contextStore.selectedOrganization,
      });
    } catch (error) {
      console.error("Failed to initialize context:", error);
    }
  }
});
