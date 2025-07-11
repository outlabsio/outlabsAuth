export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore();
  const contextStore = useContextStore();

  // Only initialize context if user is authenticated
  if (authStore.isAuthenticated) {
    try {
      // Fetch available organizations
      await contextStore.fetchOrganizations();

      console.log("Context initialized:", {
        selectedOrg: contextStore.selectedOrganization?.name,
        availableOrgs: contextStore.availableOrganizations.map((org) => org.name),
        isSystemContext: contextStore.isSystemContext,
      });
    } catch (error) {
      console.error("Failed to initialize context:", error);
    }
  }
});
