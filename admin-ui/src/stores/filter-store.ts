import { create } from "zustand";
import { persist } from "zustand/middleware";

// Common filter types that can be reused across pages
export interface FilterState {
  // Entity filters
  entityFilters: {
    search: string;
    entityClass: string;
    entityType: string;
    status: string;
    parentId?: string;
  };
  
  // User filters
  userFilters: {
    search: string;
    status: string;
    entityId?: string;
    roleId?: string;
    hasRole?: boolean;
    sortBy?: string;
    sortOrder?: "asc" | "desc";
  };
  
  // Role filters
  roleFilters: {
    search: string;
    entityId?: string;
    includeInherited?: boolean;
  };
  
  // Permission filters
  permissionFilters: {
    search: string;
    resource?: string;
    action?: string;
    scope?: string;
  };
  
  // Platform filters
  platformFilters: {
    search: string;
    status?: string;
  };
  
  // Generic table filters
  tableFilters: Record<string, {
    pageSize: number;
    page: number;
    sortBy?: string;
    sortOrder?: "asc" | "desc";
  }>;
}

export interface FilterActions {
  // Entity filter actions
  setEntitySearch: (search: string) => void;
  setEntityClass: (entityClass: string) => void;
  setEntityType: (entityType: string) => void;
  setEntityStatus: (status: string) => void;
  setEntityParentId: (parentId?: string) => void;
  resetEntityFilters: () => void;
  
  // User filter actions
  setUserSearch: (search: string) => void;
  setUserStatus: (status: string) => void;
  setUserEntityId: (entityId?: string) => void;
  setUserRoleId: (roleId?: string) => void;
  setUserHasRole: (hasRole?: boolean) => void;
  setUserSort: (sortBy?: string, sortOrder?: "asc" | "desc") => void;
  resetUserFilters: () => void;
  
  // Role filter actions
  setRoleSearch: (search: string) => void;
  setRoleEntityId: (entityId?: string) => void;
  setRoleIncludeInherited: (includeInherited?: boolean) => void;
  resetRoleFilters: () => void;
  
  // Permission filter actions
  setPermissionSearch: (search: string) => void;
  setPermissionResource: (resource?: string) => void;
  setPermissionAction: (action?: string) => void;
  setPermissionScope: (scope?: string) => void;
  resetPermissionFilters: () => void;
  
  // Platform filter actions
  setPlatformSearch: (search: string) => void;
  setPlatformStatus: (status?: string) => void;
  resetPlatformFilters: () => void;
  
  // Table filter actions
  setTablePageSize: (tableId: string, pageSize: number) => void;
  setTablePage: (tableId: string, page: number) => void;
  setTableSort: (tableId: string, sortBy?: string, sortOrder?: "asc" | "desc") => void;
  resetTableFilters: (tableId: string) => void;
  
  // Global actions
  resetAllFilters: () => void;
}

const defaultEntityFilters: FilterState["entityFilters"] = {
  search: "",
  entityClass: "all",
  entityType: "all",
  status: "active",
};

const defaultUserFilters: FilterState["userFilters"] = {
  search: "",
  status: "all",
};

const defaultRoleFilters: FilterState["roleFilters"] = {
  search: "",
  includeInherited: true,
};

const defaultPermissionFilters: FilterState["permissionFilters"] = {
  search: "",
};

const defaultPlatformFilters: FilterState["platformFilters"] = {
  search: "",
};

const defaultTableFilters = {
  pageSize: 10,
  page: 1,
};

export const useFilterStore = create<FilterState & FilterActions>()(
  persist(
    (set, get) => ({
      // State
      entityFilters: defaultEntityFilters,
      userFilters: defaultUserFilters,
      roleFilters: defaultRoleFilters,
      permissionFilters: defaultPermissionFilters,
      platformFilters: defaultPlatformFilters,
      tableFilters: {},
      
      // Entity filter actions
      setEntitySearch: (search) => set((state) => ({
        entityFilters: { ...state.entityFilters, search }
      })),
      setEntityClass: (entityClass) => set((state) => ({
        entityFilters: { ...state.entityFilters, entityClass }
      })),
      setEntityType: (entityType) => set((state) => ({
        entityFilters: { ...state.entityFilters, entityType }
      })),
      setEntityStatus: (status) => set((state) => ({
        entityFilters: { ...state.entityFilters, status }
      })),
      setEntityParentId: (parentId) => set((state) => ({
        entityFilters: { ...state.entityFilters, parentId }
      })),
      resetEntityFilters: () => set({ entityFilters: defaultEntityFilters }),
      
      // User filter actions
      setUserSearch: (search) => set((state) => ({
        userFilters: { ...state.userFilters, search }
      })),
      setUserStatus: (status) => set((state) => ({
        userFilters: { ...state.userFilters, status }
      })),
      setUserEntityId: (entityId) => set((state) => ({
        userFilters: { ...state.userFilters, entityId }
      })),
      setUserRoleId: (roleId) => set((state) => ({
        userFilters: { ...state.userFilters, roleId }
      })),
      setUserHasRole: (hasRole) => set((state) => ({
        userFilters: { ...state.userFilters, hasRole }
      })),
      setUserSort: (sortBy, sortOrder) => set((state) => ({
        userFilters: { ...state.userFilters, sortBy, sortOrder }
      })),
      resetUserFilters: () => set({ userFilters: defaultUserFilters }),
      
      // Role filter actions
      setRoleSearch: (search) => set((state) => ({
        roleFilters: { ...state.roleFilters, search }
      })),
      setRoleEntityId: (entityId) => set((state) => ({
        roleFilters: { ...state.roleFilters, entityId }
      })),
      setRoleIncludeInherited: (includeInherited) => set((state) => ({
        roleFilters: { ...state.roleFilters, includeInherited }
      })),
      resetRoleFilters: () => set({ roleFilters: defaultRoleFilters }),
      
      // Permission filter actions
      setPermissionSearch: (search) => set((state) => ({
        permissionFilters: { ...state.permissionFilters, search }
      })),
      setPermissionResource: (resource) => set((state) => ({
        permissionFilters: { ...state.permissionFilters, resource }
      })),
      setPermissionAction: (action) => set((state) => ({
        permissionFilters: { ...state.permissionFilters, action }
      })),
      setPermissionScope: (scope) => set((state) => ({
        permissionFilters: { ...state.permissionFilters, scope }
      })),
      resetPermissionFilters: () => set({ permissionFilters: defaultPermissionFilters }),
      
      // Platform filter actions
      setPlatformSearch: (search) => set((state) => ({
        platformFilters: { ...state.platformFilters, search }
      })),
      setPlatformStatus: (status) => set((state) => ({
        platformFilters: { ...state.platformFilters, status }
      })),
      resetPlatformFilters: () => set({ platformFilters: defaultPlatformFilters }),
      
      // Table filter actions
      setTablePageSize: (tableId, pageSize) => set((state) => ({
        tableFilters: {
          ...state.tableFilters,
          [tableId]: {
            ...state.tableFilters[tableId] || defaultTableFilters,
            pageSize,
            page: 1, // Reset to first page when changing page size
          }
        }
      })),
      setTablePage: (tableId, page) => set((state) => ({
        tableFilters: {
          ...state.tableFilters,
          [tableId]: {
            ...state.tableFilters[tableId] || defaultTableFilters,
            page,
          }
        }
      })),
      setTableSort: (tableId, sortBy, sortOrder) => set((state) => ({
        tableFilters: {
          ...state.tableFilters,
          [tableId]: {
            ...state.tableFilters[tableId] || defaultTableFilters,
            sortBy,
            sortOrder,
          }
        }
      })),
      resetTableFilters: (tableId) => set((state) => ({
        tableFilters: {
          ...state.tableFilters,
          [tableId]: defaultTableFilters,
        }
      })),
      
      // Global actions
      resetAllFilters: () => set({
        entityFilters: defaultEntityFilters,
        userFilters: defaultUserFilters,
        roleFilters: defaultRoleFilters,
        permissionFilters: defaultPermissionFilters,
        platformFilters: defaultPlatformFilters,
        tableFilters: {},
      }),
    }),
    {
      name: "filter-storage",
      partialize: (state) => ({
        // Only persist specific filters that make sense to remember
        tableFilters: state.tableFilters,
        userFilters: {
          ...state.userFilters,
          search: "", // Don't persist search terms
        },
        roleFilters: {
          ...state.roleFilters,
          search: "",
        },
        entityFilters: {
          ...state.entityFilters,
          search: "",
        },
      }),
    }
  )
);

// Helper hooks for specific filter sets
export const useEntityFilters = () => {
  const { entityFilters, setEntitySearch, setEntityClass, setEntityType, setEntityStatus, setEntityParentId, resetEntityFilters } = useFilterStore();
  return { filters: entityFilters, setSearch: setEntitySearch, setClass: setEntityClass, setType: setEntityType, setStatus: setEntityStatus, setParentId: setEntityParentId, reset: resetEntityFilters };
};

export const useUserFilters = () => {
  const { userFilters, setUserSearch, setUserStatus, setUserEntityId, setUserRoleId, setUserHasRole, setUserSort, resetUserFilters } = useFilterStore();
  return { filters: userFilters, setSearch: setUserSearch, setStatus: setUserStatus, setEntityId: setUserEntityId, setRoleId: setUserRoleId, setHasRole: setUserHasRole, setSort: setUserSort, reset: resetUserFilters };
};

export const useRoleFilters = () => {
  const { roleFilters, setRoleSearch, setRoleEntityId, setRoleIncludeInherited, resetRoleFilters } = useFilterStore();
  return { filters: roleFilters, setSearch: setRoleSearch, setEntityId: setRoleEntityId, setIncludeInherited: setRoleIncludeInherited, reset: resetRoleFilters };
};

export const usePermissionFilters = () => {
  const { permissionFilters, setPermissionSearch, setPermissionResource, setPermissionAction, setPermissionScope, resetPermissionFilters } = useFilterStore();
  return { filters: permissionFilters, setSearch: setPermissionSearch, setResource: setPermissionResource, setAction: setPermissionAction, setScope: setPermissionScope, reset: resetPermissionFilters };
};

export const usePlatformFilters = () => {
  const { platformFilters, setPlatformSearch, setPlatformStatus, resetPlatformFilters } = useFilterStore();
  return { filters: platformFilters, setSearch: setPlatformSearch, setStatus: setPlatformStatus, reset: resetPlatformFilters };
};

export const useTableFilters = (tableId: string) => {
  const { tableFilters, setTablePageSize, setTablePage, setTableSort, resetTableFilters } = useFilterStore();
  const filters = tableFilters[tableId] || defaultTableFilters;
  
  return {
    filters,
    setPageSize: (pageSize: number) => setTablePageSize(tableId, pageSize),
    setPage: (page: number) => setTablePage(tableId, page),
    setSort: (sortBy?: string, sortOrder?: "asc" | "desc") => setTableSort(tableId, sortBy, sortOrder),
    reset: () => resetTableFilters(tableId),
  };
};