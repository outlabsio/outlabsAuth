import type { 
  User, 
  UserListResponse, 
  UserCreateRequest, 
  UserUpdateRequest, 
  UserInviteRequest, 
  UserInviteResponse,
  UserMembershipListResponse,
  UserBulkActionRequest,
  UserBulkActionResponse,
  UserStatsResponse
} from "~/types/auth.types";

interface UsersState {
  users: User[];
  selectedUser: User | null;
  isLoading: boolean;
  error: string | null;
  // Pagination
  currentPage: number;
  pageSize: number;
  totalUsers: number;
  totalPages: number;
  // Filters
  filters: {
    search: string;
    entity_id: string | null;
    status: string | null;
  };
  // Stats
  stats: UserStatsResponse | null;
  // UI State
  ui: {
    drawerOpen: boolean;
    drawerMode: "view" | "create" | "edit";
  };
}

export const useUsersStore = defineStore("users", () => {
  // State
  const state = reactive<UsersState>({
    users: [],
    selectedUser: null,
    isLoading: false,
    error: null,
    currentPage: 1,
    pageSize: 20,
    totalUsers: 0,
    totalPages: 0,
    filters: {
      search: "",
      entity_id: null,
      status: null,
    },
    stats: null,
    ui: {
      drawerOpen: false,
      drawerMode: "view",
    },
  });

  // Use auth and context stores
  const authStore = useAuthStore();
  const contextStore = useContextStore();
  const toast = useToast();

  // Actions
  const fetchUsers = async () => {
    state.isLoading = true;
    state.error = null;

    try {
      // Build query params
      const params = new URLSearchParams();
      
      if (state.filters.search) {
        params.append("query", state.filters.search);
      }
      
      if (state.filters.entity_id) {
        params.append("entity_id", state.filters.entity_id);
      }
      
      if (state.filters.status) {
        params.append("status", state.filters.status);
      }
      
      params.append("page", state.currentPage.toString());
      params.append("page_size", state.pageSize.toString());

      const response = await authStore.apiCall<UserListResponse>(`/v1/users/?${params.toString()}`);

      // Ensure each user has entities array initialized
      state.users = response.items.map(user => ({
        ...user,
        entities: user.entities || []
      }));
      state.totalUsers = response.total;
      state.totalPages = response.total_pages;
    } catch (error: any) {
      console.error("Failed to fetch users:", error);
      state.error = error.message || "Failed to fetch users";
      state.users = [];
    } finally {
      state.isLoading = false;
    }
  };

  const fetchUser = async (userId: string) => {
    try {
      const user = await authStore.apiCall<User>(`/v1/users/${userId}`);
      state.selectedUser = user;
      return user;
    } catch (error: any) {
      console.error("Failed to fetch user:", error);
      state.error = error.message || "Failed to fetch user";
      throw error;
    }
  };

  const createUser = async (data: UserCreateRequest) => {
    try {
      const user = await authStore.apiCall<User>("/v1/users/", {
        method: "POST",
        body: data,
      });

      toast.add({
        title: "User Created",
        description: `User ${user.email} has been created successfully`,
        color: "success",
      });

      // Refresh the list
      await fetchUsers();

      return user;
    } catch (error: any) {
      console.error("Failed to create user:", error);
      toast.add({
        title: "Error",
        description: error.message || "Failed to create user",
        color: "error",
      });
      throw error;
    }
  };

  const updateUser = async (userId: string, data: UserUpdateRequest) => {
    try {
      const user = await authStore.apiCall<User>(`/v1/users/${userId}`, {
        method: "PUT",
        body: data,
      });

      // Update in local state
      const index = state.users.findIndex((u) => u.id === userId);
      if (index !== -1) {
        state.users[index] = user;
      }

      if (state.selectedUser?.id === userId) {
        state.selectedUser = user;
      }

      toast.add({
        title: "User Updated",
        description: "User has been updated successfully",
        color: "success",
      });

      return user;
    } catch (error: any) {
      console.error("Failed to update user:", error);
      toast.add({
        title: "Error",
        description: error.message || "Failed to update user",
        color: "error",
      });
      throw error;
    }
  };

  const deleteUser = async (userId: string, hardDelete = false) => {
    try {
      await authStore.apiCall(`/v1/users/${userId}?hard_delete=${hardDelete}`, {
        method: "DELETE",
      });

      // Remove from local state
      state.users = state.users.filter((u) => u.id !== userId);

      if (state.selectedUser?.id === userId) {
        state.selectedUser = null;
      }

      toast.add({
        title: hardDelete ? "User Deleted" : "User Deactivated",
        description: hardDelete 
          ? "User has been permanently deleted" 
          : "User has been deactivated",
        color: "success",
      });
    } catch (error: any) {
      console.error("Failed to delete user:", error);
      toast.add({
        title: "Error",
        description: error.message || "Failed to delete user",
        color: "error",
      });
      throw error;
    }
  };

  const updateUserStatus = async (userId: string, status: "active" | "inactive" | "locked") => {
    try {
      const user = await authStore.apiCall<User>(`/v1/users/${userId}/status`, {
        method: "POST",
        body: { status },
      });

      // Update in local state
      const index = state.users.findIndex((u) => u.id === userId);
      if (index !== -1) {
        state.users[index] = user;
      }

      if (state.selectedUser?.id === userId) {
        state.selectedUser = user;
      }

      toast.add({
        title: "Status Updated",
        description: `User status changed to ${status}`,
        color: "success",
      });

      return user;
    } catch (error: any) {
      console.error("Failed to update user status:", error);
      toast.add({
        title: "Error",
        description: error.message || "Failed to update user status",
        color: "error",
      });
      throw error;
    }
  };

  const inviteUser = async (data: UserInviteRequest) => {
    try {
      const response = await authStore.apiCall<UserInviteResponse>("/v1/users/invite", {
        method: "POST",
        body: data,
      });

      toast.add({
        title: "User Invited",
        description: response.message,
        color: "success",
      });

      // Refresh the list
      await fetchUsers();

      return response;
    } catch (error: any) {
      console.error("Failed to invite user:", error);
      toast.add({
        title: "Error",
        description: error.message || "Failed to invite user",
        color: "error",
      });
      throw error;
    }
  };

  const resetUserPassword = async (userId: string, sendEmail = true) => {
    try {
      const response = await authStore.apiCall<{
        message: string;
        temporary_password?: string;
        email_sent: boolean;
      }>(`/v1/users/${userId}/reset-password`, {
        method: "POST",
        body: { send_email: sendEmail },
      });

      toast.add({
        title: "Password Reset",
        description: response.message,
        color: "success",
      });

      return response;
    } catch (error: any) {
      console.error("Failed to reset password:", error);
      toast.add({
        title: "Error",
        description: error.message || "Failed to reset password",
        color: "error",
      });
      throw error;
    }
  };

  const fetchUserMemberships = async (userId: string, includeInactive = false) => {
    try {
      const params = new URLSearchParams();
      if (includeInactive) {
        params.append("include_inactive", "true");
      }

      const response = await authStore.apiCall<UserMembershipListResponse>(
        `/v1/users/${userId}/memberships?${params.toString()}`
      );

      return response;
    } catch (error: any) {
      console.error("Failed to fetch user memberships:", error);
      throw error;
    }
  };

  const fetchUserStats = async () => {
    try {
      const stats = await authStore.apiCall<UserStatsResponse>("/v1/users/stats/overview");
      state.stats = stats;
      return stats;
    } catch (error: any) {
      console.error("Failed to fetch user stats:", error);
      // Don't throw error for stats, just use default values
      state.stats = {
        total_users: 0,
        active_users: 0,
        recent_logins: 0,
        locked_users: 0
      };
      return state.stats;
    }
  };

  const bulkAction = async (data: UserBulkActionRequest) => {
    try {
      const response = await authStore.apiCall<UserBulkActionResponse>("/v1/users/bulk-action", {
        method: "POST",
        body: data,
      });

      toast.add({
        title: "Bulk Action Completed",
        description: `${response.total_successful} successful, ${response.total_failed} failed`,
        color: response.total_failed > 0 ? "warning" : "success",
      });

      // Refresh the list
      await fetchUsers();

      return response;
    } catch (error: any) {
      console.error("Failed to perform bulk action:", error);
      toast.add({
        title: "Error",
        description: error.message || "Failed to perform bulk action",
        color: "error",
      });
      throw error;
    }
  };

  // UI Actions
  const openDrawer = (mode: "view" | "create" | "edit" = "view", user: User | null = null) => {
    state.ui.drawerMode = mode;
    state.selectedUser = user;
    state.ui.drawerOpen = true;
  };

  const closeDrawer = () => {
    state.ui.drawerOpen = false;
    // Reset selected user after animation
    setTimeout(() => {
      state.selectedUser = null;
    }, 300);
  };

  const setDrawerMode = (mode: "view" | "create" | "edit") => {
    state.ui.drawerMode = mode;
  };

  const setFilters = (filters: Partial<UsersState["filters"]>) => {
    state.filters = { ...state.filters, ...filters };
    state.currentPage = 1; // Reset to first page when filters change
  };

  const resetFilters = () => {
    state.filters = {
      search: "",
      entity_id: null,
      status: null,
    };
    state.currentPage = 1;
  };

  const setPage = (page: number) => {
    state.currentPage = page;
    fetchUsers();
  };

  const setPageSize = (pageSize: number) => {
    state.pageSize = pageSize;
    state.currentPage = 1;
    fetchUsers();
  };

  // Computed
  const hasActiveFilters = computed(() => {
    return (
      state.filters.search || 
      state.filters.entity_id || 
      state.filters.status
    );
  });

  const getUserDisplayName = (user: User) => {
    if (user.profile.full_name) {
      return user.profile.full_name;
    }
    const parts = [user.profile.first_name, user.profile.last_name].filter(Boolean);
    return parts.length > 0 ? parts.join(" ") : user.email;
  };

  const getUserStatus = (user: User) => {
    if (user.locked_until && new Date(user.locked_until) > new Date()) {
      return "locked";
    }
    return user.is_active ? "active" : "inactive";
  };

  const getUserStatusColor = (user: User) => {
    const status = getUserStatus(user);
    switch (status) {
      case "active":
        return "success";
      case "locked":
        return "error";
      default:
        return "neutral";
    }
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "Never";
    try {
      return new Date(dateString).toLocaleString();
    } catch (e) {
      return "Invalid Date";
    }
  };

  return {
    // State (as computed for reactivity)
    users: computed(() => state.users),
    selectedUser: computed(() => state.selectedUser),
    isLoading: computed(() => state.isLoading),
    error: computed(() => state.error),
    currentPage: computed(() => state.currentPage),
    pageSize: computed(() => state.pageSize),
    totalUsers: computed(() => state.totalUsers),
    totalPages: computed(() => state.totalPages),
    filters: computed(() => state.filters),
    stats: computed(() => state.stats),
    ui: state.ui, // Return reactive reference directly

    // Computed
    hasActiveFilters,

    // Actions
    fetchUsers,
    fetchUser,
    createUser,
    updateUser,
    deleteUser,
    updateUserStatus,
    inviteUser,
    resetUserPassword,
    fetchUserMemberships,
    fetchUserStats,
    bulkAction,

    // UI Actions
    openDrawer,
    closeDrawer,
    setDrawerMode,
    setFilters,
    resetFilters,
    setPage,
    setPageSize,

    // Helpers
    getUserDisplayName,
    getUserStatus,
    getUserStatusColor,
    formatDate,
  };
});