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
      console.log("🕒 USE AUTH: isTokenExpired - no token");
      return true;
    }

    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const currentTime = Date.now() / 1000;
      const expired = payload.exp < currentTime;
      console.log("🕒 USE AUTH: isTokenExpired - token expires at:", new Date(payload.exp * 1000).toISOString(), "current time:", new Date(currentTime * 1000).toISOString(), "expired:", expired);
      return expired;
    } catch (error) {
      console.error("🕒 USE AUTH: isTokenExpired - error parsing token:", error);
      return true;
    }
  };

  // Check if token is close to expiring (within 5 minutes)
  const isTokenExpiringSoon = () => {
    const token = getAccessToken();
    if (!token) {
      console.log("🕒 USE AUTH: isTokenExpiringSoon - no token");
      return true;
    }

    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const currentTime = Date.now() / 1000;
      const timeUntilExpiry = payload.exp - currentTime;
      const expiringSoon = timeUntilExpiry < 300; // 5 minutes
      console.log("🕒 USE AUTH: isTokenExpiringSoon - time until expiry:", Math.floor(timeUntilExpiry), "seconds, expiring soon:", expiringSoon);
      return expiringSoon;
    } catch (error) {
      console.error("🕒 USE AUTH: isTokenExpiringSoon - error parsing token:", error);
      return true;
    }
  };

  // Auto-refresh token if it's expiring soon
  useEffect(() => {
    console.log("🔄 USE AUTH: Token check effect running, isAuthenticated:", isAuthenticated, "isRefreshing:", isRefreshing);

    if (!isAuthenticated || isRefreshing) {
      console.log("🔄 USE AUTH: Skipping token check - not authenticated or already refreshing");
      return;
    }

    const checkTokenExpiry = () => {
      console.log("🔄 USE AUTH: Checking token expiry");

      const expired = isTokenExpired();
      const expiringSoon = isTokenExpiringSoon();

      console.log("🔄 USE AUTH: Token status - expired:", expired, "expiring soon:", expiringSoon);

      if (expired) {
        console.log("🔄 USE AUTH: Token is expired, logging out");
        logout();
        return;
      }

      if (expiringSoon) {
        console.log("🔄 USE AUTH: Token expiring soon, attempting refresh");
        store.refreshTokens().catch((error) => {
          console.error("🔄 USE AUTH: Proactive refresh failed:", error);
          // If refresh fails, the store will handle logout
        });
      }
    };

    // Check immediately
    console.log("🔄 USE AUTH: Running initial token check");
    checkTokenExpiry();

    // Set up interval to check every minute
    console.log("🔄 USE AUTH: Setting up 1-minute interval for token checks");
    const interval = setInterval(() => {
      console.log("🔄 USE AUTH: Running scheduled token check");
      checkTokenExpiry();
    }, 60000);

    return () => {
      console.log("🔄 USE AUTH: Clearing token check interval");
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
