import type { LoginResponse, TokenResponse } from "~/types/auth.types";
// Remove UserAdminUpdate import if not defined yet or needed immediately
// import type { UserAdminUpdate } from "~/schemas/user_schema";

export interface User {
  id: string; // Ensure this is always populated, either from _id or id
  _id?: string; // Keep _id if backend sends it
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  name: string | null; // Allow null for name
  is_team_member: boolean;
  last_login: string | null; // Allow null
  created_at: string;
  updated_at?: string | null; // Add updated_at
  permissions: string[];
  locale?: string; // Add locale
}

// Frontend type mirroring UserAdminUpdate Pydantic schema
// Define based on fields allowed for PATCH /users/{user_id}
export interface UserAdminUpdatePayload {
  name?: string | null;
  is_active?: boolean;
  is_superuser?: boolean; // Be cautious allowing this from frontend
  is_team_member?: boolean;
  permissions?: string[]; // Permissions might be handled separately
  locale?: string;
}

export const useUsersStore = defineStore("users", () => {
  const users = ref<User[]>([]);
  const totalUsers = ref(0); // Consider how to get total count from API
  const currentPage = ref(1);
  const searchQuery = ref("");
  const sortColumn = ref("");
  const sortDirection = ref<"asc" | "desc">("asc");
  const loading = ref(false); // Add loading state
  const error = ref<string | null>(null); // Add error state

  const columns = ref([
    { key: "id", label: "ID", visible: false }, // Hide ID by default
    { key: "name", label: "Name", visible: true, sortable: true },
    { key: "email", label: "Email", visible: true, sortable: true },
    { key: "userType", label: "Role", visible: true }, // Changed label
    { key: "is_active", label: "Status", visible: true },
    { key: "is_verified", label: "Verified", visible: true },
    { key: "created_at", label: "Created At", visible: true, sortable: true },
    // { key: "last_login", label: "Last Login", visible: true }, // Often not needed
    { key: "actions", label: "Actions", visible: true },
  ]);

  // Use role parameter instead of is_team_member boolean
  const fetchUsers = async (skip = 0, limit = 10, roleFilter: "team_member" | "admin" | "superuser" | null = null) => {
    loading.value = true;
    error.value = null;
    console.log(`Fetching users: skip=${skip}, limit=${limit}, role=${roleFilter}, search=${searchQuery.value}`);
    try {
      const authStore = useAuthStore();
      const params: Record<string, any> = {
        // FastAPI pagination uses skip/limit convention typically
        skip: skip,
        limit: limit,
        // Assuming backend handles search and sorting via query params
        search: searchQuery.value || undefined, // Send undefined if empty
        sort_column: sortColumn.value || undefined,
        sort_direction: sortDirection.value || undefined,
      };

      // Add role filter if provided
      if (roleFilter) {
        params["role"] = roleFilter;
      }

      // Fetch using UserAdminRead compatible type if backend sends more fields
      // Use the correct endpoint from the docs
      const data = await authStore.apiCall<User[]>("/users/all", {
        method: "GET", // Explicitly GET
        params: params,
      });

      // Map response, ensuring 'id' exists, defaulting permissions
      users.value = data
        .map((user) => {
          const id = user._id || user.id; // Prefer _id if present from backend
          if (!id) {
            console.error("User object missing ID:", user);
            return null; // Skip user if ID is missing
          }
          return {
            ...user,
            id: id, // Ensure 'id' field is populated for frontend use
            _id: id, // Also keep _id if needed elsewhere
            permissions: user.permissions || [],
            name: user.name || null, // Handle potentially missing name
            last_login: user.last_login || null,
          };
        })
        .filter((user) => user !== null) as User[]; // Filter out any null entries

      // TODO: Get total count from API response (e.g., headers or body)
      // For now, using fetched length which is incorrect for pagination
      totalUsers.value = data.length; // Placeholder - Needs proper total count
    } catch (err: any) {
      console.error("Error fetching users:", err);
      const detail = err?.data?.detail || err.message || "Failed to fetch users";
      error.value = `Error fetching users: ${detail}`;
      users.value = []; // Clear users on error
      totalUsers.value = 0;
    } finally {
      loading.value = false;
    }
  };

  const sortUsers = (columnKey: string) => {
    if (sortColumn.value === columnKey) {
      sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    } else {
      sortColumn.value = columnKey;
      sortDirection.value = "asc";
    }
    // Refetch users with new sort parameters - need to know current filter
    // Assuming fetchUsers is called elsewhere after sort update (e.g., in component watcher)
    console.log(`Sorting by ${sortColumn.value} ${sortDirection.value}`);
    // Trigger refetch (e.g., fetchUsers(0, 10, currentFilter)) - needs state for currentFilter
  };

  const setSearchQuery = (query: string) => {
    searchQuery.value = query;
    currentPage.value = 1; // Reset page on new search
    // Debounce this call in the component or add debounce here
    // Trigger refetch (e.g., fetchUsers(0, 10, currentFilter)) - needs state for currentFilter
    console.log(`Search query set to: ${query}`);
  };

  const setCurrentPage = (page: number) => {
    currentPage.value = page;
    const limit = 10; // Define limit or get from state
    const skip = (page - 1) * limit;
    // Trigger refetch for the specific page (e.g., fetchUsers(skip, limit, currentFilter)) - needs state for currentFilter
    console.log(`Setting current page to: ${page}`);
  };

  const inviteUser = async (userData: { email: string; name?: string }) => {
    // Endpoint needs confirmation - is it /users/invite or different?
    loading.value = true;
    error.value = null;
    try {
      const authStore = useAuthStore();
      const newUser = await authStore.apiCall<User>("/users/invite", {
        // Verify this endpoint
        method: "POST",
        body: userData,
      });
      // Add to local state or refetch? Refetching might be safer for consistency.
      // await fetchUsers(0, 10, 'admin'); // Example: Refetch admins after invite
      // Or add locally:
      users.value.push({
        ...newUser,
        id: newUser._id || newUser.id,
        _id: newUser._id || newUser.id,
        permissions: newUser.permissions || [],
      });
      totalUsers.value++; // Increment if adding locally AND total isn't from API
      return newUser; // Return the created user
    } catch (err: any) {
      console.error("Error inviting user:", err);
      const detail = err?.data?.detail || err.message || "Failed to invite user";
      error.value = `Error inviting user: ${detail}`;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // Update user using PATCH and specific payload
  const updateUser = async (userId: string, updateData: UserAdminUpdatePayload) => {
    loading.value = true;
    error.value = null;
    console.log(`Updating user ${userId} with data:`, updateData);
    try {
      const authStore = useAuthStore();
      // Use PATCH method and send only the allowed fields
      const updatedUserFromApi = await authStore.apiCall<User>(`/users/${userId}`, {
        method: "PATCH",
        body: updateData,
      });
      const index = users.value.findIndex((u) => u.id === userId);

      if (index !== -1) {
        const currentUser = users.value[index]; // Get user at the found index
        // Double-check if the user still exists at that index (although findIndex implies it should)
        if (currentUser) {
          // Merge updates: Take existing user and overwrite with API response fields
          users.value[index] = {
            ...currentUser, // Keep existing fields
            ...updatedUserFromApi, // Overwrite with response
            id: userId, // Ensure ID remains correct
            _id: userId, // Ensure _id also remains correct
          };
          console.log(`User ${userId} updated locally.`);
        } else {
          console.warn(`User ${userId} was found at index ${index} but is now undefined.`);
          // Consider refetching the list here
        }
      } else {
        console.warn(`User ${userId} not found locally for update.`);
        // Optionally refetch the list here if user wasn't found
      }
      return users.value[index]; // Return the updated user from local state
    } catch (err: any) {
      console.error("Error updating user:", err);
      const detail = err?.data?.detail || err.message || "Failed to update user";
      error.value = `Error updating user ${userId}: ${detail}`;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // Add delete user function
  const deleteUser = async (userId: string) => {
    loading.value = true;
    error.value = null;
    console.log(`Attempting to delete user ${userId}`);
    try {
      const authStore = useAuthStore();
      // API returns 204 No Content on success, so response might be null/empty
      await authStore.apiCall(`/users/${userId}`, {
        method: "DELETE",
      });
      console.log(`User ${userId} deleted via API.`);
      // Remove user from local state
      const initialLength = users.value.length;
      users.value = users.value.filter((u) => u.id !== userId);
      if (users.value.length < initialLength) {
        console.log(`User ${userId} removed locally.`);
        totalUsers.value--; // Decrement total count ONLY if API doesn't provide total
      } else {
        console.warn(`User ${userId} not found locally for removal.`);
      }
    } catch (err: any) {
      console.error("Error deleting user:", err);
      const detail = err?.data?.detail || err.message || "Failed to delete user";
      error.value = `Error deleting user ${userId}: ${detail}`;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // --- Permission related functions ---
  // Review these carefully based on your actual permission endpoints/logic

  const assignPermissionsToUser = async (userId: string, permissionNames: string[]) => {
    // Verify endpoint and payload
    console.log(`Assigning permissions ${permissionNames} to user ${userId}`);
    try {
      const authStore = useAuthStore();
      // Assuming endpoint is /permissions/assign and returns updated User
      const updatedUser = await authStore.apiCall<User>("/permissions/assign", {
        // Verify endpoint
        method: "POST",
        body: { user_id: userId, permission_names: permissionNames },
      });
      const userIndex = users.value.findIndex((u) => u.id === userId);
      if (userIndex !== -1) {
        users.value[userIndex] = { ...updatedUser, id: userId, _id: userId }; // Ensure ID
        console.log(`Permissions updated locally for ${userId}.`);
      }
    } catch (err: any) {
      console.error("Error assigning permissions:", err);
      // Handle error state
    }
  };

  const removePermissionsFromUser = async (userId: string, permissionNames: string[]) => {
    // Verify endpoint and payload
    console.log(`Removing permissions ${permissionNames} from user ${userId}`);
    try {
      const authStore = useAuthStore();
      // Assuming endpoint is /permissions/remove and returns updated User
      const updatedUser = await authStore.apiCall<User>(`/permissions/remove`, {
        // Verify endpoint
        method: "DELETE", // Or POST/PATCH depending on API design
        body: { user_id: userId, permission_names: permissionNames }, // Verify payload
      });
      const userIndex = users.value.findIndex((u) => u.id === userId);
      if (userIndex !== -1) {
        users.value[userIndex] = { ...updatedUser, id: userId, _id: userId }; // Ensure ID
        console.log(`Permissions removed locally for ${userId}.`);
      }
    } catch (err: any) {
      console.error("Error removing permissions:", err);
      // Handle error state
    }
  };

  const getUserPermissions = async (userId: string): Promise<string[]> => {
    // Verify endpoint
    console.log("Getting permissions for userId:", userId);
    try {
      const authStore = useAuthStore();
      // Assuming /permissions/user?user_id=... endpoint returns string[]
      const permissions = await authStore.apiCall<string[]>(`/permissions/user`, {
        // Verify endpoint
        params: { user_id: userId },
      });
      console.log(`Permissions fetched for ${userId}:`, permissions);
      if (Array.isArray(permissions)) {
        // Optional: Update local state if necessary
        const userIndex = users.value.findIndex((u) => u.id === userId);
        if (userIndex !== -1) {
          const user = users.value[userIndex];
          if (user) {
            user.permissions = [...permissions];
          }
        }
        return permissions;
      }
    } catch (err: any) {
      console.error("Error fetching user permissions:", err);
      // Handle error state
    }
    return []; // Return empty on error
  };

  // --- Helper Functions ---

  // Helper function to determine user type string
  const getUserType = (user: User): string => {
    if (user.is_superuser) return "Super User";
    if (user.is_team_member) return "Team Member";
    return "User";
  };

  // Helper function to format date string
  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleString();
    } catch (e) {
      return "Invalid Date";
    }
  };

  // Helper function for badge color based on user type (using Nuxt UI color names)
  const getUserTypeBadgeColor = (user: User): "blue" | "purple" | "green" => {
    if (user.is_superuser) return "blue";
    if (user.is_team_member) return "purple";
    return "green";
  };

  // --- Combined Update Logic ---
  // Consider simplifying or moving this logic to the component level if it becomes too complex.
  const updateUserWithPermissions = async (editingUserId: string, updates: Partial<User>, newPermissions: string[]) => {
    if (!editingUserId) throw new Error("User ID is required for update");

    const originalUser = users.value.find((u) => u.id === editingUserId);
    if (!originalUser) throw new Error("User not found for update");

    loading.value = true;
    error.value = null;
    console.log(`Updating user ${editingUserId} with details and permissions.`);

    try {
      // 1. Handle User Detail Updates
      const userUpdatePayload: UserAdminUpdatePayload = {};
      const fieldsToUpdate: (keyof UserAdminUpdatePayload)[] = ["name", "is_active", "is_superuser", "is_team_member", "locale"];
      let userDetailsChanged = false;
      fieldsToUpdate.forEach((field) => {
        const updateValue = updates[field];

        // Check if the field exists in 'updates' and is different from original
        if (updateValue !== undefined && updateValue !== originalUser[field]) {
          // Assign carefully based on expected type in UserAdminUpdatePayload
          if (field === "name" || field === "locale") {
            // Convert null to undefined to satisfy TypeScript
            userUpdatePayload[field] = updateValue === null ? undefined : (updateValue as string);
          } else if (field === "is_active" || field === "is_superuser" || field === "is_team_member") {
            userUpdatePayload[field] = updateValue as boolean;
          } else if (field === "permissions") {
            userUpdatePayload[field] = updateValue as string[];
          }
          userDetailsChanged = true;
        }
      });

      if (userDetailsChanged) {
        console.log("Updating User Details:", userUpdatePayload);
        await updateUser(editingUserId, userUpdatePayload); // Call the dedicated update function
      } else {
        console.log("No user detail changes detected.");
      }

      // 2. Handle Permission Changes
      const originalPermissionNames = originalUser.permissions || [];
      const permissionsToAdd = newPermissions.filter((name) => !originalPermissionNames.includes(name));
      const permissionsToRemove = originalPermissionNames.filter((name) => !newPermissions.includes(name));

      // Chain permission updates sequentially
      if (permissionsToRemove.length > 0) {
        console.log("Removing Permissions:", permissionsToRemove);
        await removePermissionsFromUser(editingUserId, permissionsToRemove);
      }
      if (permissionsToAdd.length > 0) {
        console.log("Assigning Permissions:", permissionsToAdd);
        await assignPermissionsToUser(editingUserId, permissionsToAdd);
      }

      console.log(`User ${editingUserId} update process complete.`);
      // Optionally refetch the user or list here if needed
      // await fetchUsers(0, 10, 'admin'); // Example refetch
    } catch (err: any) {
      console.error(`Error in updateUserWithPermissions for ${editingUserId}:`, err);
      const detail = err?.data?.detail || err.message || "Failed to update user and permissions";
      error.value = `Update Error: ${detail}`;
      throw err; // Re-throw error
    } finally {
      loading.value = false;
    }
  };

  return {
    // State
    users,
    totalUsers,
    currentPage,
    searchQuery,
    sortColumn,
    sortDirection,
    loading,
    error,
    columns, // Expose columns definition

    // Actions
    fetchUsers,
    inviteUser,
    updateUser,
    deleteUser,
    assignPermissionsToUser,
    removePermissionsFromUser,
    getUserPermissions,
    sortUsers, // Expose sorting action trigger
    setSearchQuery, // Expose search action trigger
    setCurrentPage, // Expose pagination action trigger

    // Helpers (exposed for use in components)
    getUserType,
    formatDate,
    getUserTypeBadgeColor,
    updateUserWithPermissions, // Expose combined update if used
  };
});
