import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { apiUrl } from "@/config";
import { useContextStore } from "./context-store";

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  roles: any[];
  permissions?: string[];
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface AuthState {
  // State
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isRefreshing: boolean;

  // Actions
  login: (tokens: AuthTokens, user?: User) => Promise<void>;
  logout: () => void;
  refreshTokens: () => Promise<void>;
  setUser: (user: User) => void;
  clearAuth: () => void;

  // Computed
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
}

// Check if debug mode is enabled
const isDebugMode = () => {
  try {
    return localStorage.getItem("auth-debug-mode") === "true";
  } catch {
    return false;
  }
};

// Create the store with persistence
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      tokens: null,
      isAuthenticated: false,
      isRefreshing: false,

      // Login action
      login: async (tokens: AuthTokens, user?: User) => {
        console.log("[AUTH STORE] AUTH STORE: Login called with tokens:", !!tokens.access_token, !!tokens.refresh_token);

        set({
          tokens,
          isAuthenticated: true,
          isRefreshing: false, // Reset refresh state on login
        });

        // If user is provided, set it, otherwise fetch it
        if (user) {
          console.log("[AUTH STORE] AUTH STORE: Setting user from login data:", user.email);
          set({ user });
        } else {
          console.log("[AUTH STORE] AUTH STORE: Fetching user data from /auth/me");
          try {
            const response = await fetch(apiUrl("/auth/me"), {
              headers: {
                Authorization: `Bearer ${tokens.access_token}`,
              },
            });

            if (response.ok) {
              const userData = await response.json();
              console.log("[AUTH STORE] AUTH STORE: User data fetched successfully:", userData.email);
              set({ user: userData });
            } else {
              console.error("[AUTH STORE] AUTH STORE: Failed to fetch user data:", response.status, response.statusText);
            }
          } catch (error) {
            console.error("[AUTH STORE] AUTH STORE: Error fetching user data:", error);
          }
        }
      },

      // Logout action
      logout: () => {
        console.log("[AUTH STORE] AUTH STORE: Logout called");
        const debugMode = isDebugMode();
        console.log("[AUTH STORE] AUTH STORE: Debug mode status:", debugMode);

        const currentTokens = get().tokens;

        // Clear state first
        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isRefreshing: false,
        });

        // Clear persisted data
        localStorage.removeItem("auth-storage");
        console.log("[AUTH STORE] AUTH STORE: Cleared localStorage");

        // Clear organization context
        useContextStore.getState().clearContext();
        console.log("[AUTH STORE] AUTH STORE: Cleared context");

        // Optionally call logout endpoint to invalidate tokens on server
        if (currentTokens?.refresh_token) {
          console.log("[AUTH STORE] AUTH STORE: Calling server logout endpoint");
          fetch(apiUrl("/auth/logout"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${currentTokens.access_token}`,
            },
            body: JSON.stringify({
              refresh_token: currentTokens.refresh_token,
            }),
          })
            .then((response) => {
              console.log("[AUTH STORE] AUTH STORE: Server logout response:", response.status);
            })
            .catch((error) => {
              console.log("[AUTH STORE] AUTH STORE: Server logout error (ignored):", error);
            });
        }

        // Only redirect if not in debug mode
        if (debugMode) {
          console.log("[AUTH STORE] AUTH STORE: Debug mode enabled - NOT redirecting to login");
        } else {
          console.log("[AUTH STORE] AUTH STORE: Redirecting to login");
          window.location.href = "/login";
        }
      },

      // Refresh tokens action
      refreshTokens: async () => {
        const { tokens, isRefreshing } = get();

        console.log("[REFRESH] AUTH STORE: refreshTokens called");
        console.log("[REFRESH] AUTH STORE: Current refresh state:", isRefreshing);
        console.log("[REFRESH] AUTH STORE: Has refresh token:", !!tokens?.refresh_token);

        // Prevent multiple simultaneous refresh attempts
        if (isRefreshing) {
          console.log("[REFRESH] AUTH STORE: Already refreshing, throwing error");
          throw new Error("Token refresh already in progress");
        }

        if (!tokens?.refresh_token) {
          console.log("[REFRESH] AUTH STORE: No refresh token available, throwing error");
          throw new Error("No refresh token available");
        }

        console.log("[REFRESH] AUTH STORE: Setting isRefreshing to true");
        set({ isRefreshing: true });

        try {
          console.log("[REFRESH] AUTH STORE: Making refresh request to /auth/refresh");
          console.log("[REFRESH] AUTH STORE: Refresh token (first 20 chars):", tokens.refresh_token.substring(0, 20));
          console.log("[REFRESH] AUTH STORE: Request URL:", apiUrl("/auth/refresh"));

          // Add timeout to prevent hanging requests
          const controller = new AbortController();
          const timeoutId = setTimeout(() => {
            console.log("[REFRESH] AUTH STORE: Request timeout, aborting");
            controller.abort();
          }, 10000); // 10 second timeout

          const response = await fetch(apiUrl("/auth/refresh"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              refresh_token: tokens.refresh_token,
            }),
            signal: controller.signal,
          });

          clearTimeout(timeoutId);
          console.log("[REFRESH] AUTH STORE: Refresh response status:", response.status);

          if (response.ok) {
            const newTokens: AuthTokens = await response.json();
            console.log("[REFRESH] AUTH STORE: New tokens received:", !!newTokens.access_token, !!newTokens.refresh_token);

            set({
              tokens: newTokens,
              isAuthenticated: true,
              isRefreshing: false,
            });

            console.log("[REFRESH] AUTH STORE: Tokens updated successfully");
          } else {
            console.error("[REFRESH] AUTH STORE: Refresh failed with status:", response.status);
            console.error("[REFRESH] AUTH STORE: Response headers:", Object.fromEntries(response.headers.entries()));

            let errorData = null;
            let errorText = "";

            try {
              errorText = await response.text();
              errorData = JSON.parse(errorText);
            } catch (e) {
              console.error("[REFRESH] AUTH STORE: Failed to parse error response:", e);
              console.error("[REFRESH] AUTH STORE: Raw error response:", errorText);
            }

            console.error("[REFRESH] AUTH STORE: Refresh error data:", errorData);

            // Refresh failed, logout
            set({ isRefreshing: false });
            console.log("[REFRESH] AUTH STORE: Calling logout due to refresh failure");
            get().logout();
            throw new Error(`Token refresh failed: ${errorData?.detail || response.status}`);
          }
        } catch (error) {
          console.error("[REFRESH] AUTH STORE: Refresh error:", error);

          // More specific error handling
          if (error instanceof Error) {
            if (error.name === "AbortError") {
              console.error("[REFRESH] AUTH STORE: Request was aborted (timeout)");
            } else if (error.message.includes("Failed to fetch")) {
              console.error("[REFRESH] AUTH STORE: Network error or API unreachable");
            } else {
              console.error("[REFRESH] AUTH STORE: Unexpected error:", error.message);
            }
          }

          // Refresh failed, logout
          set({ isRefreshing: false });
          console.log("[REFRESH] AUTH STORE: Calling logout due to refresh error");
          get().logout();
          throw error;
        }
      },

      // Set user data
      setUser: (user: User) => {
        console.log("[AUTH STORE] AUTH STORE: setUser called:", user.email);
        set({ user });
      },

      // Clear auth data (without redirect)
      clearAuth: () => {
        console.log("[AUTH STORE] AUTH STORE: clearAuth called");
        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isRefreshing: false,
        });

        // Clear persisted data but don't redirect
        localStorage.removeItem("auth-storage");
        console.log("[AUTH STORE] AUTH STORE: Cleared localStorage (no redirect)");
      },

      // Get access token
      getAccessToken: () => {
        const tokens = get().tokens;
        const token = tokens?.access_token || null;
        console.log("[AUTH STORE] AUTH STORE: getAccessToken called, has token:", !!token);
        return token;
      },

      // Get refresh token
      getRefreshToken: () => {
        const tokens = get().tokens;
        const token = tokens?.refresh_token || null;
        console.log("[AUTH STORE] AUTH STORE: getRefreshToken called, has token:", !!token);
        return token;
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        tokens: state.tokens,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        // Don't persist isRefreshing state
      }),
    }
  )
);
