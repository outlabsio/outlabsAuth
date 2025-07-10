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
    if (!token) return true;

    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const currentTime = Date.now() / 1000;
      return payload.exp < currentTime;
    } catch {
      return true;
    }
  };

  // Check if token is close to expiring (within 5 minutes)
  const isTokenExpiringSoon = () => {
    const token = getAccessToken();
    if (!token) return true;

    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const currentTime = Date.now() / 1000;
      const timeUntilExpiry = payload.exp - currentTime;
      return timeUntilExpiry < 300; // 5 minutes
    } catch {
      return true;
    }
  };

  // Auto-refresh token if it's expiring soon
  useEffect(() => {
    if (!isAuthenticated || isRefreshing) return;

    const checkTokenExpiry = () => {
      if (isTokenExpiringSoon() && !isTokenExpired()) {
        store.refreshTokens().catch(() => {
          // If refresh fails, the store will handle logout
        });
      }
    };

    // Check immediately
    checkTokenExpiry();

    // Set up interval to check every minute
    const interval = setInterval(checkTokenExpiry, 60000);

    return () => clearInterval(interval);
  }, [isAuthenticated, isRefreshing, store]);

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
