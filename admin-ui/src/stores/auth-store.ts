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
  refresh_token?: string; // Optional - not used in web flow (HTTP-only cookie)
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

      // Login action (HTTP-only cookie based)
      login: async (tokens: AuthTokens, user?: User) => {
        console.log("[AUTH] Login successful");

        set({
          tokens,
          isAuthenticated: true,
          isRefreshing: false, // Reset refresh state on login
        });

        // If user is provided, set it, otherwise fetch it
        if (user) {
          set({ user });
        } else {
          try {
            const response = await fetch(apiUrl("/auth/me"), {
              headers: {
                Authorization: `Bearer ${tokens.access_token}`,
              },
              credentials: "include", // Include cookies
            });

            if (response.ok) {
              const userData = await response.json();
              set({ user: userData });
            } else {
              console.error("[AUTH] Failed to fetch user data:", response.status);
            }
          } catch (error) {
            console.error("[AUTH] Error fetching user data:", error);
          }
        }
      },

      // Logout action
      logout: () => {
        console.log("[AUTH] Logout initiated");
        const debugMode = isDebugMode();

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

        // Clear organization context
        useContextStore.getState().clearContext();

        // Call logout endpoint to invalidate refresh token cookie on server
        fetch(apiUrl("/auth/logout"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${currentTokens?.access_token || ""}`,
          },
          credentials: "include", // Include HTTP-only cookie
        })
          .then((response) => {
            if (!response.ok) {
              console.log("[AUTH] Server logout response:", response.status);
            }
          })
          .catch((error) => {
            console.log("[AUTH] Server logout error (ignored):", error);
          });

        // Only redirect if not in debug mode
        if (debugMode) {
          console.log("[AUTH] Debug mode enabled - preventing redirect");
        } else {
          window.location.href = "/login";
        }
      },

      // Refresh tokens action (HTTP-only cookie based)
      refreshTokens: async () => {
        const { isRefreshing } = get();

        // Prevent multiple simultaneous refresh attempts
        if (isRefreshing) {
          throw new Error("Token refresh already in progress");
        }

        set({ isRefreshing: true });

        try {
          // Add timeout to prevent hanging requests
          const controller = new AbortController();
          const timeoutId = setTimeout(() => {
            controller.abort();
          }, 10000); // 10 second timeout

          const response = await fetch(apiUrl("/auth/refresh"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            credentials: "include", // Important: Include cookies
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          if (response.ok) {
            const newTokens: AuthTokens = await response.json();

            // Only store access token (refresh token is now HTTP-only cookie)
            set({
              tokens: {
                access_token: newTokens.access_token,
                token_type: newTokens.token_type,
              },
              isAuthenticated: true,
              isRefreshing: false,
            });

            console.log("[AUTH] Token refresh successful");
          } else {
            let errorData = null;
            let errorText = "";

            try {
              errorText = await response.text();
              errorData = JSON.parse(errorText);
            } catch (e) {
              console.error("[AUTH] Failed to parse refresh error response");
            }

            // Refresh failed, logout
            set({ isRefreshing: false });
            get().logout();
            throw new Error(`Token refresh failed: ${errorData?.detail || response.status}`);
          }
        } catch (error) {
          // More specific error handling
          if (error instanceof Error) {
            if (error.name === "AbortError") {
              console.error("[AUTH] Refresh request timeout");
            } else if (error.message.includes("Failed to fetch")) {
              console.error("[AUTH] Network error during refresh");
            } else {
              console.error("[AUTH] Refresh error:", error.message);
            }
          }

          // Refresh failed, logout
          set({ isRefreshing: false });
          get().logout();
          throw error;
        }
      },

      // Set user data
      setUser: (user: User) => {
        set({ user });
      },

      // Clear auth data (without redirect)
      clearAuth: () => {
        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isRefreshing: false,
        });

        // Clear persisted data but don't redirect
        localStorage.removeItem("auth-storage");
      },

      // Get access token
      getAccessToken: () => {
        const tokens = get().tokens;
        return tokens?.access_token || null;
      },

      // Get refresh token (no longer accessible - HTTP-only cookie)
      getRefreshToken: () => {
        return null; // Always null since refresh tokens are HTTP-only cookies
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        tokens: state.tokens, // Only contains access_token now (refresh token is HTTP-only cookie)
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        // Don't persist isRefreshing state
      }),
    }
  )
);
