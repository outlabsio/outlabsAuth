/**
 * Global Auth Middleware
 * Handles authentication and route protection for OutlabsAuth
 */

export default defineNuxtRouteMiddleware(async (to) => {
  // Skip middleware on server-side
  if (import.meta.server) {
    return;
  }

  const authStore = useAuthStore();
  const contextStore = useContextStore();
  const permissionsStore = usePermissionsStore();

  // Public routes that don't require authentication
  const publicRoutes = [
    "/login",
    "/signup",
    "/verify",
    "/recovery",
    "/forgot-password",
    "/reset-password",
  ];

  const isPublicRoute = publicRoutes.some((route) => to.path.startsWith(route));

  // Initialize auth state on first load
  if (!authStore.state.isInitialized) {
    await authStore.initialize();
  }

  // If user is authenticated and trying to access public route, redirect to dashboard
  if (isPublicRoute && authStore.isAuthenticated) {
    // Exception: allow access to recovery/verify/forgot-password/reset-password pages even when authenticated
    if (
      to.path.startsWith("/recovery") ||
      to.path.startsWith("/verify") ||
      to.path.startsWith("/forgot-password") ||
      to.path.startsWith("/reset-password")
    ) {
      return;
    }

    return navigateTo("/dashboard");
  }

  // If protected route and not authenticated, redirect to login
  if (!isPublicRoute && !authStore.isAuthenticated) {
    return navigateTo({
      path: "/login",
      query: { redirect: to.fullPath },
    });
  }

  // Initialize context after successful auth (for protected routes)
  if (!isPublicRoute && authStore.isAuthenticated && contextStore) {
    try {
      await contextStore.initialize();

      if (!permissionsStore.userPermissions && !authStore.currentUser?.is_superuser) {
        await permissionsStore.fetchUserPermissions();
      }
    } catch (error) {
      console.error("Context initialization failed:", error);
    }
  }

  if (!isPublicRoute && authStore.isAuthenticated) {
    if (to.path.startsWith("/api-keys") && !authStore.features.api_keys) {
      return navigateTo("/dashboard");
    }

    if (to.path.startsWith("/settings/entity-types")) {
      if (!authStore.isEnterpriseRBAC || !authStore.currentUser?.is_superuser) {
        return navigateTo("/dashboard");
      }
    }

    const routePermissionMap: Array<{ prefix: string; permission: string }> = [
      { prefix: "/users", permission: "user:read" },
      { prefix: "/roles", permission: "role:read" },
      { prefix: "/permissions", permission: "permission:read" },
      { prefix: "/entities", permission: "entity:read" },
    ];

    const matchedPermission = routePermissionMap.find((routeDef) =>
      to.path.startsWith(routeDef.prefix)
    )?.permission;

    if (matchedPermission) {
      const hasAccess =
        authStore.currentUser?.is_superuser || permissionsStore.hasPermission(matchedPermission);

      if (!hasAccess && to.path !== "/dashboard") {
        return navigateTo("/dashboard");
      }
    }
  }
});
