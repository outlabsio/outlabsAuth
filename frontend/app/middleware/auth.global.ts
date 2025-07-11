export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore();
  const userStore = useUserStore();

  const publicRoutes = ["/login", "/signup", "/verify", "/recovery", "/refresh"];

  const isPublicRoute = publicRoutes.some((route) => {
    return to.path.startsWith(route) || to.path.match(/^\/[a-z]{2}\/recovery\//);
  });

  console.log(`🛣️ Navigating to: ${to.path} (Public: ${isPublicRoute})`);

  // Initialize auth state only on first load or refresh
  if (!isPublicRoute && !authStore.accessToken) {
    const initResult = await authStore.initialize();
    if (!initResult && !isPublicRoute) {
      console.log("🔓 Auth initialization failed, redirecting to login");
      return navigateTo("/login");
    }
  }

  // If we're on a public route and already authenticated, redirect to dashboard
  if (isPublicRoute && authStore.isAuthenticated) {
    console.log("🔒 Already authenticated, redirecting to dashboard");
    return navigateTo("/dashboard");
  }

  // Only check authentication for protected routes
  if (!isPublicRoute && !authStore.isAuthenticated) {
    console.log("🔓 Not authenticated, redirecting to login");
    userStore.$reset();
    return navigateTo("/login");
  }

  // For now, skip entity membership check since /v1/auth/me doesn't return that data
  // TODO: Either update the API to return entity memberships or make a separate call
  // if (!isPublicRoute && authStore.isAuthenticated) {
  //   const isSystemOrAdmin = userStore.isAdmin || userStore.isPlatformAdmin || userStore.isSystemUser;
  //   if (!isSystemOrAdmin && userStore.entities.length === 0) {
  //     console.log("🚫 Regular user has no entity memberships, redirecting to login");
  //     authStore.logout();
  //     return navigateTo("/login");
  //   }
  // }

  console.log(`✅ Proceeding to: ${to.path}`);
});
