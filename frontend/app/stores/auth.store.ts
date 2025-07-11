import type { User } from "~/types/auth.types";

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const useAuthStore = defineStore("auth", () => {
  const state = reactive({
    accessToken: null as string | null,
    refreshToken: null as string | null,
    user: null as User | null,
    isAuthenticated: false,
  });

  const config = useRuntimeConfig();
  const router = useRouter();
  const isReady = computed(() => state.accessToken !== null);

  const refreshAccessToken = async () => {
    try {
      // Refresh token is stored as httpOnly cookie, so we just need to include credentials
      const response = await $fetch<AuthTokens>("/v1/auth/refresh", {
        baseURL: config.public.apiBaseUrl,
        method: "POST",
        credentials: "include", // This will send the httpOnly cookie
      });

      if (response.access_token) {
        state.accessToken = response.access_token;
        state.refreshToken = "httponly-cookie"; // Refresh token remains as httpOnly cookie
        state.isAuthenticated = true;
        
        return response.access_token;
      }

      throw new Error("No access token in refresh response");
    } catch (error) {
      console.error("Refresh token error:", error);
      clearAuth();
      throw error;
    }
  };

  const apiCall = async <T>(endpoint: string, options: any = {}): Promise<T> => {
    const userStore = useUserStore();

    const makeRequest = async (token: string | null) => {
      const headers = {
        ...options.headers,
        ...(token && { Authorization: `Bearer ${token}` }),
      };

      // Removed automatic language injection to prevent conflicts with local language selection
      // Individual stores/components should explicitly add lang parameter when needed
      // const queryChar = endpoint.includes("?") ? "&" : "?";
      // const languageQuery = `${queryChar}lang=${userStore.language || "en"}`;
      // const endpointWithLang = endpoint + (options.skipLang ? "" : languageQuery);

      return await $fetch<T>(endpoint, {
        ...options,
        baseURL: config.public.apiBaseUrl,
        headers,
        credentials: "include",
      });
    };

    try {
      return await makeRequest(state.accessToken);
    } catch (error: any) {
      if (error.status === 401 && state.accessToken) {
        try {
          const newToken = await refreshAccessToken();
          return await makeRequest(newToken);
        } catch (refreshError) {
          clearAuth();
          throw refreshError;
        }
      }
      throw error;
    }
  };

  const initialize = async () => {
    try {
      // If we have an access token, try to validate it
      if (state.accessToken) {
        const userStore = useUserStore();
        if (!userStore.id) {
          try {
            const userData = await apiCall<User>("/v1/auth/me");
            userStore.setUser(userData);
            state.isAuthenticated = true;
            return true;
          } catch (error: any) {
            // If 401, token might be expired, try refresh
            if (error.status === 401 && state.refreshToken) {
              await refreshAccessToken();
              const userData = await apiCall<User>("/v1/auth/me");
              userStore.setUser(userData);
              state.isAuthenticated = true;
              return true;
            }
            throw error;
          }
        }
        state.isAuthenticated = true;
        return true;
      }
      
      // No access token, check for refresh token cookie
      // The refresh token is httpOnly, so we can't read it directly
      // Try to refresh and see if it works
      try {
        await refreshAccessToken();
        const userStore = useUserStore();
        const userData = await apiCall<User>("/v1/auth/me");
        userStore.setUser(userData);
        state.isAuthenticated = true;
        return true;
      } catch (error) {
        // No valid session
        console.log("No valid session found");
        return false;
      }
    } catch (error) {
      console.error("Initialization error:", error);
      clearAuth();
      return false;
    }
  };

  const clearAuth = () => {
    state.accessToken = null;
    state.refreshToken = null;
    state.user = null;
    state.isAuthenticated = false;
    // Also clear user store
    const userStore = useUserStore();
    userStore.$reset();
  };

  const login = async (username: string, password: string) => {
    try {
      // Use form data endpoint like the React version
      const response = await $fetch<AuthTokens>("/v1/auth/login", {
        baseURL: config.public.apiBaseUrl,
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          username: username.trim(), // OAuth2 spec uses 'username' field for email
          password: password,
        }),
        credentials: "include", // Important: Allow cookies to be set
      });

      console.log("Login Response:", response);

      state.accessToken = response.access_token;
      // Refresh token is set as httpOnly cookie by backend, we don't get it in response
      state.refreshToken = "httponly-cookie";
      state.isAuthenticated = true;

      // Fetch user data
      const userData = await apiCall<User>("/v1/auth/me");
      console.log("User data fetched:", userData);
      
      state.user = userData;

      const userStore = useUserStore();
      userStore.setUser(userData);

      return true;
    } catch (error) {
      console.error("Login error:", error);
      clearAuth();
      throw error;
    }
  };

  const logout = async () => {
    try {
      if (state.refreshToken) {
        await apiCall("/v1/auth/logout", { 
          method: "POST",
          body: {
            refresh_token: state.refreshToken
          }
        });
      }
    } catch (error) {
      console.warn("Logout endpoint error:", error);
    } finally {
      clearAuth();
      const userStore = useUserStore();
      userStore.$reset();
      
      // Clear cookie
      const tokenCookie = useCookie('auth-token');
      tokenCookie.value = null;
      
      await navigateTo('/login');
      return true;
    }
  };

  const requestVerification = async (email: string) => {
    try {
      const config = useRuntimeConfig();
      await apiCall("/auth/request-verify-token", {
        method: "POST",
        body: { email },
      });
      return true;
    } catch (error: any) {
      console.error("Verification request error:", error);
      throw error;
    }
  };

  const requestPasswordReset = async (email: string) => {
    try {
      await apiCall("/password-reset/request", {
        method: "POST",
        body: { email },
      });
      return true;
    } catch (error: any) {
      console.error("Password reset request error:", error);
      throw error;
    }
  };

  const resetPassword = async (token: string, newPassword: string) => {
    try {
      const config = useRuntimeConfig();
      const response = await $fetch(`${config.public.apiBaseUrl}/password-reset/confirm`, {
        method: "POST",
        body: {
          token,
          new_password: newPassword,
        },
        headers: {
          "Content-Type": "application/json",
        },
      });
      return true;
    } catch (error: any) {
      console.error("Password reset error:", error);
      throw error;
    }
  };

  const resendVerificationEmail = async () => {
    try {
      const userStore = useUserStore();
      await apiCall("/auth/request-verify-token", {
        method: "POST",
        body: {
          email: userStore.email,
        },
      });
      return true;
    } catch (error: any) {
      console.error("Resend verification error:", error);
      throw error;
    }
  };

  const verifyUser = async (token: string) => {
    try {
      const response = await apiCall(`/verify/${token}`, {
        method: "GET",
      });
      return response;
    } catch (error: any) {
      console.error("Verify user error:", error);
      const errorMessage = error.data?.detail || error.message || "Verification failed";
      throw new Error(errorMessage);
    }
  };

  const signup = async (name: string, email: string, password: string, invitation_code: string) => {
    try {
      const response = await apiCall("/register", {
        method: "POST",
        body: {
          name,
          email,
          password,
          invitation_code,
        },
      });
      return { success: true, user: response };
    } catch (error: any) {
      console.error("Signup error:", error);
      throw error;
    }
  };

  return {
    // State (as computed for reactivity)
    isAuthenticated: computed(() => state.isAuthenticated),
    accessToken: computed(() => state.accessToken),
    refreshToken: computed(() => state.refreshToken),
    user: computed(() => state.user),
    isReady,
    
    // Actions
    initialize,
    login,
    logout,
    refreshAccessToken,
    apiCall,
    clearAuth,
    requestVerification,
    requestPasswordReset,
    resetPassword,
    resendVerificationEmail,
    verifyUser,
    signup,
    
    // Debug helper
    getState: () => state,
  };
});
