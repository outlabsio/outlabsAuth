import { useAuthStore } from "@/stores/auth-store";
import { useEffect } from "react";

export const useAuth = () => {
  const store = useAuthStore();

  // Check if user is authenticated
  const isAuthenticated = store.isAuthenticated && !!store.tokens?.access_token;

  // Check if tokens are being refreshed
  const isRefreshing = store.isRefreshing;

  // Get user data
  const user = store.user;

  // Get tokens
  const tokens = store.tokens;

  // Actions
  const login = store.login;
  const logout = store.logout;
  const setUser = store.setUser;

  // Token utilities
  const getAccessToken = () => store.getAccessToken();
  const getRefreshToken = () => store.getRefreshToken();

  // Check if token is expired (basic check - the server will validate properly)
  const isTokenExpired = () => {
    const token = getAccessToken();
    if (!token) {
      return true;
    }

    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const currentTime = Date.now() / 1000;
      const expired = payload.exp < currentTime;
      return expired;
    } catch (error) {
      console.error("[AUTH] Error parsing token:", error);
      return true;
    }
  };

  // Check if token is close to expiring (within 5 minutes)
  const isTokenExpiringSoon = () => {
    const token = getAccessToken();
    if (!token) {
      return true;
    }

    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const currentTime = Date.now() / 1000;
      const timeUntilExpiry = payload.exp - currentTime;
      const expiringSoon = timeUntilExpiry < 300; // 5 minutes
      return expiringSoon;
    } catch (error) {
      console.error("[AUTH] Error checking token expiry:", error);
      return true;
    }
  };

  // Auto-refresh token if it's expiring soon
  useEffect(() => {
    if (!isAuthenticated || isRefreshing) {
      return;
    }

    const checkTokenExpiry = () => {
      const expired = isTokenExpired();
      const expiringSoon = isTokenExpiringSoon();

      if (expired) {
        console.log("[AUTH] Token expired, logging out");
        logout();
        return;
      }

      if (expiringSoon) {
        console.log("[AUTH] Token expiring soon, refreshing...");
        store.refreshTokens().catch((error) => {
          console.error("[AUTH] Proactive refresh failed:", error);
          // If refresh fails, the store will handle logout
        });
      }
    };

    // Check immediately
    checkTokenExpiry();

    // Set up interval to check every minute
    const interval = setInterval(checkTokenExpiry, 60000);

    return () => {
      clearInterval(interval);
    };
  }, [isAuthenticated, isRefreshing, store, logout]);

  return {
    // State
    isAuthenticated,
    isRefreshing,
    user,
    tokens,

    // Actions
    login,
    logout,
    setUser,

    // Utilities
    getAccessToken,
    getRefreshToken,
    isTokenExpired,
    isTokenExpiringSoon,
  };
};
