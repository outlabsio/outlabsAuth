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
            });

            if (response.ok) {
              const userData = await response.json();
              set({ user: userData });
            }
          } catch (error) {
            console.error("Failed to fetch user data:", error);
          }
        }
      },

      // Logout action
      logout: () => {
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

        // Optionally call logout endpoint to invalidate tokens on server
        if (currentTokens?.refresh_token) {
          fetch(apiUrl("/auth/logout"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${currentTokens.access_token}`,
            },
            body: JSON.stringify({
              refresh_token: currentTokens.refresh_token,
            }),
          }).catch(() => {
            // Ignore errors from logout endpoint
          });
        }

        // Redirect to login
        window.location.href = "/login";
      },

      // Refresh tokens action
      refreshTokens: async () => {
        const { tokens, isRefreshing } = get();

        // Prevent multiple simultaneous refresh attempts
        if (isRefreshing) {
          throw new Error("Token refresh already in progress");
        }

        if (!tokens?.refresh_token) {
          throw new Error("No refresh token available");
        }

        set({ isRefreshing: true });

        try {
          const response = await fetch(apiUrl("/auth/refresh"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              refresh_token: tokens.refresh_token,
            }),
          });

          if (response.ok) {
            const newTokens: AuthTokens = await response.json();
            set({
              tokens: newTokens,
              isAuthenticated: true,
              isRefreshing: false,
            });
          } else {
            // Refresh failed, logout
            set({ isRefreshing: false });
            get().logout();
            throw new Error("Token refresh failed");
          }
        } catch (error) {
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
      },

      // Get access token
      getAccessToken: () => {
        const tokens = get().tokens;
        return tokens?.access_token || null;
      },

      // Get refresh token
      getRefreshToken: () => {
        const tokens = get().tokens;
        return tokens?.refresh_token || null;
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
