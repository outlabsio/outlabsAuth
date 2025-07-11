export interface Permission {
  _id?: string;
  name: string;
  description: string;
  resource?: string;
  action?: string;
}

export interface PermissionGroup {
  resource: string;
  permissions: Permission[];
}

interface UserWithPermission {
  _id: string;
  name: string;
  permissions?: string[];
}

interface PaginationState {
  pageIndex: number;
  pageSize: number;
}

export const usePermissionsStore = defineStore("permissions", () => {
  const permissions = ref<Permission[]>([]);
  const totalPermissions = ref(0);
  const currentPage = ref(1);
  const searchQuery = ref("");
  const sortColumn = ref("");
  const sortDirection = ref<"asc" | "desc">("asc");
  const isLoading = ref(false);

  // Add specific loading states for different actions
  const isCreating = ref(false);
  const isUpdating = ref(false);
  const isDeleting = ref(false);
  const isLoadingUsers = ref(false);

  const pagination = ref<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  });

  // Standard CRUD actions for permissions
  const standardActions = ["create", "read", "update", "delete", "all"] as const;

  const parsePermissionName = (permission: Permission): Permission => {
    const result = { ...permission };
    if (permission.name && permission.name.includes(":")) {
      const [resource, action] = permission.name.split(":");
      result.resource = resource;
      result.action = action;
    }
    return result;
  };

  const uniqueResources = computed(() => {
    const resources = new Set<string>();
    permissions.value.forEach((permission) => {
      if (permission.resource) {
        resources.add(permission.resource);
      }
    });
    return Array.from(resources).sort();
  });

  const isResourceSet = (group: PermissionGroup) => {
    return group.permissions.some((p) => {
      if (!p.name) return false;
      const parts = p.name.split(":");
      return parts.length > 1 && standardActions.includes(parts[1] as (typeof standardActions)[number]);
    });
  };

  const getResourceSetDescription = (group: PermissionGroup) => {
    // Try to get the description from the "all" permission
    const allPerm = group.permissions.find((p) => p.name?.includes(":all"));
    if (allPerm?.description) {
      return allPerm.description;
    }

    // Fall back to the first permission description
    const firstPerm = group.permissions[0];
    if (firstPerm?.description) {
      return firstPerm.description;
    }

    return `${group.resource} permissions`;
  };

  const resourceSets = computed(() => {
    return permissionsByResource.value.filter(isResourceSet);
  });

  const getCustomPermissions = (permissions: Permission[]) => {
    return permissions.filter((p) => {
      if (!p.name) return true;
      const parts = p.name.split(":");
      return !(parts.length > 1 && standardActions.includes(parts[1] as (typeof standardActions)[number]));
    });
  };

  const customPermissions = computed(() => {
    const result: Permission[] = [];

    permissionsByResource.value.forEach((group) => {
      // If the group has any standard permissions, consider only non-standard ones from it
      if (isResourceSet(group)) {
        const customPerms = getCustomPermissions(group.permissions);
        result.push(...customPerms);
      } else {
        // If the group has no standard permissions, all of its permissions are custom
        result.push(...group.permissions);
      }
    });

    return result;
  });

  const resourceSetsCount = computed(() => resourceSets.value.length);
  const customPermissionsCount = computed(() => customPermissions.value.length);

  const permissionsByResource = computed(() => {
    const groups: PermissionGroup[] = [];

    uniqueResources.value.forEach((resource) => {
      const resourcePermissions = permissions.value
        .filter((p) => p.resource === resource)
        .sort((a, b) => {
          if (a.action === "all") return -1;
          if (b.action === "all") return 1;
          return (a.action || "").localeCompare(b.action || "");
        });

      groups.push({
        resource,
        permissions: resourcePermissions,
      });
    });

    const otherPermissions = permissions.value.filter((p) => !p.resource);
    if (otherPermissions.length > 0) {
      groups.push({
        resource: "Other",
        permissions: otherPermissions,
      });
    }

    return groups;
  });

  // User-related functions
  const getUsersWithPermission = async (permissionName: string): Promise<UserWithPermission[]> => {
    try {
      isLoadingUsers.value = true;
      const authStore = useAuthStore();
      const users = await authStore.apiCall<UserWithPermission[]>(`/permissions/${permissionName}/users`);
      return users;
    } catch (error) {
      console.error("Error fetching users with permission:", error);
      return [];
    } finally {
      isLoadingUsers.value = false;
    }
  };

  const getUsersForPermissionSet = async (group: PermissionGroup): Promise<UserWithPermission[]> => {
    try {
      isLoadingUsers.value = true;
      // Get all permission names in this set
      const permissionNames = group.permissions.map((p) => p.name);
      const usersByPermission: Record<string, UserWithPermission> = {};

      // Get users for each permission in the set
      for (const permName of permissionNames) {
        if (!permName) continue;
        try {
          const users = await getUsersWithPermission(permName);

          // Merge users into the collection
          for (const user of users) {
            const userId = user._id;
            if (!usersByPermission[userId]) {
              usersByPermission[userId] = {
                _id: userId,
                name: user.name,
                permissions: [],
              };
            }
            if (permName && usersByPermission[userId].permissions) {
              usersByPermission[userId].permissions?.push(permName);
            }
          }
        } catch (err) {
          console.error(`Error fetching users for permission ${permName}:`, err);
        }
      }

      return Object.values(usersByPermission);
    } catch (error) {
      console.error("Error fetching users with permission set:", error);
      return [];
    } finally {
      isLoadingUsers.value = false;
    }
  };

  const createResourceSet = async (resourceName: string, description: string = "") => {
    isCreating.value = true;
    try {
      const permissionsToCreate = [];
      const baseDescription = description.trim();

      // Add all permission first
      permissionsToCreate.push({
        name: `${resourceName}:all`,
        description: baseDescription ? `Full access to all ${resourceName} operations (${baseDescription})` : `Full access to all ${resourceName} operations`,
      });

      // Add CRUD permissions
      [
        { action: "create", desc: `Create ${resourceName} resources` },
        { action: "read", desc: `View ${resourceName} resources` },
        { action: "update", desc: `Update ${resourceName} resources` },
        { action: "delete", desc: `Delete ${resourceName} resources` },
      ].forEach((item) => {
        permissionsToCreate.push({
          name: `${resourceName}:${item.action}`,
          description: baseDescription ? `${item.desc} (${baseDescription})` : item.desc,
        });
      });

      let createdCount = 0;
      const errors: string[] = [];

      for (const perm of permissionsToCreate) {
        try {
          await createPermission({
            name: perm.name,
            description: perm.description,
          });
          createdCount++;
        } catch (error: any) {
          errors.push(`${perm.name}: ${error.message || "Unknown error"}`);
          console.error(`Error creating permission ${perm.name}:`, error);
        }
      }

      return { createdCount, total: permissionsToCreate.length, errors };
    } finally {
      isCreating.value = false;
    }
  };

  const deleteResourceSet = async (group: PermissionGroup) => {
    isDeleting.value = true;
    try {
      const errors: string[] = [];
      let deletedCount = 0;

      for (const permission of group.permissions) {
        if (permission._id) {
          try {
            await deletePermission(permission._id);
            deletedCount++;
          } catch (error: any) {
            errors.push(`${permission.name}: ${error.message || "Unknown error"}`);
          }
        }
      }

      return { deletedCount, total: group.permissions.length, errors };
    } finally {
      isDeleting.value = false;
    }
  };

  // Pagination and data fetching
  const fetchPermissions = async (skip?: number, limit?: number) => {
    console.log("fetchPermissions called with skip:", skip, "limit:", limit);
    isLoading.value = true;
    try {
      const authStore = useAuthStore();
      const skipValue = skip ?? pagination.value.pageIndex * pagination.value.pageSize;
      const limitValue = limit ?? pagination.value.pageSize;

      console.log("Calling API with params:", {
        skip: skipValue,
        limit: limitValue,
        search: searchQuery.value,
        sort_column: sortColumn.value,
        sort_direction: sortDirection.value,
      });

      // API returns a direct array of permissions
      const data = await authStore.apiCall<Permission[]>("/permissions", {
        params: {
          skip: skipValue,
          limit: limitValue,
          search: searchQuery.value,
          sort_column: sortColumn.value,
          sort_direction: sortDirection.value,
        },
      });

      console.log("API returned data:", data);
      console.log("Data is array:", Array.isArray(data));
      console.log("Data length:", data?.length);

      // Assign permissions directly from the array
      permissions.value = data.map(parsePermissionName);
      console.log("After mapping:", permissions.value.length, "permissions");

      // Set total based on the length of the returned array
      totalPermissions.value = data.length;
      console.log("Set totalPermissions to:", totalPermissions.value);

      // Debug computed values
      console.log("uniqueResources:", uniqueResources.value);
      console.log("permissionsByResource count:", permissionsByResource.value.length);
      console.log("resourceSets count:", resourceSets.value.length);
      console.log("customPermissions count:", customPermissions.value.length);
    } catch (error) {
      console.error("Error fetching permissions:", error);
      permissions.value = [];
      totalPermissions.value = 0;
    } finally {
      isLoading.value = false;
    }
  };

  const setPagination = (newPagination: Partial<PaginationState>) => {
    pagination.value = { ...pagination.value, ...newPagination };
    fetchPermissions();
  };

  const setSearchQuery = (query: string) => {
    searchQuery.value = query;
    currentPage.value = 1;
    fetchPermissions();
  };

  const setCurrentPage = (page: number) => {
    currentPage.value = page;
    fetchPermissions();
  };

  const sortPermissions = (column: string, direction: "asc" | "desc") => {
    sortColumn.value = column;
    sortDirection.value = direction;
    fetchPermissions();
  };

  // Basic CRUD operations
  const createPermission = async (permission: Omit<Permission, "_id">) => {
    try {
      isCreating.value = true;
      const authStore = useAuthStore();
      const data = await authStore.apiCall<Permission>("/permissions", {
        method: "POST",
        body: permission,
      });
      permissions.value.push(data);
      totalPermissions.value++;
    } catch (error) {
      console.error("Error creating permission:", error);
      throw error;
    } finally {
      isCreating.value = false;
    }
  };

  const updatePermission = async (permission: Permission) => {
    try {
      isUpdating.value = true;
      if (!permission._id) {
        throw new Error("Cannot update permission without an _id");
      }
      const authStore = useAuthStore();
      const data = await authStore.apiCall<Permission>(`/permissions/${permission._id}`, {
        method: "PUT",
        body: permission,
      });
      const index = permissions.value.findIndex((p) => p._id === permission._id);
      if (index !== -1) {
        permissions.value[index] = data;
      }
    } catch (error) {
      console.error("Error updating permission:", error);
      throw error;
    } finally {
      isUpdating.value = false;
    }
  };

  const deletePermission = async (_id: string) => {
    try {
      isDeleting.value = true;
      const authStore = useAuthStore();
      await authStore.apiCall(`/permissions/${_id}`, {
        method: "DELETE",
      });
      permissions.value = permissions.value.filter((p) => p._id !== _id);
      totalPermissions.value--;
    } catch (error) {
      console.error("Error deleting permission:", error);
      throw error;
    } finally {
      isDeleting.value = false;
    }
  };

  return {
    // State
    permissions,
    totalPermissions,
    currentPage,
    searchQuery,
    sortColumn,
    sortDirection,
    isLoading,
    pagination,
    // Loading states
    isCreating,
    isUpdating,
    isDeleting,
    isLoadingUsers,

    // Computed
    uniqueResources,
    permissionsByResource,
    resourceSets,
    customPermissions,
    resourceSetsCount,
    customPermissionsCount,

    // Methods
    getResourceSetDescription,
    createResourceSet,
    deleteResourceSet,
    getUsersWithPermission,
    getUsersForPermissionSet,
    fetchPermissions,
    createPermission,
    updatePermission,
    deletePermission,
    setPagination,
    setSearchQuery,
    setCurrentPage,
    sortPermissions,
  };
});
