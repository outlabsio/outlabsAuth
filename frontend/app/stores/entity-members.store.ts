import type { 
  EntityMember, 
  User, 
  Role,
  EntityMemberCreateRequest,
  EntityMemberUpdateRequest
} from "~/types/auth.types";

interface MembersState {
  members: EntityMember[];
  selectedMember: EntityMember | null;
  isLoading: boolean;
  error: string | null;
  // Current entity context
  entityId: string | null;
  entityName: string | null;
  // Pagination
  currentPage: number;
  pageSize: number;
  totalMembers: number;
  totalPages: number;
  // Available users and roles for dropdowns
  availableUsers: Array<{ value: string; label: string; email: string }>;
  availableRoles: Array<{ value: string; label: string; description: string }>;
  isLoadingUsers: boolean;
  isLoadingRoles: boolean;
  // UI State
  ui: {
    drawerOpen: boolean;
    drawerMode: "create" | "edit";
  };
}

export const useEntityMembersStore = defineStore("entity-members", () => {
  // State
  const state = reactive<MembersState>({
    members: [],
    selectedMember: null,
    isLoading: false,
    error: null,
    entityId: null,
    entityName: null,
    currentPage: 1,
    pageSize: 20,
    totalMembers: 0,
    totalPages: 0,
    availableUsers: [],
    availableRoles: [],
    isLoadingUsers: false,
    isLoadingRoles: false,
    ui: {
      drawerOpen: false,
      drawerMode: "create",
    },
  });

  // Use auth and context stores
  const authStore = useAuthStore();
  const contextStore = useContextStore();
  const toast = useToast();

  // Actions
  const setEntity = (entityId: string, entityName: string) => {
    state.entityId = entityId;
    state.entityName = entityName;
  };

  const fetchMembers = async () => {
    if (!state.entityId) return;

    state.isLoading = true;
    state.error = null;

    try {
      const params = new URLSearchParams({
        page: state.currentPage.toString(),
        page_size: state.pageSize.toString()
      });

      const response = await authStore.apiCall<{
        items: EntityMember[];
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
      }>(`/v1/entities/${state.entityId}/members?${params}`, {
        headers: contextStore.getContextHeaders
      });

      state.members = response.items || [];
      state.totalMembers = response.total || 0;
      state.totalPages = response.total_pages || 1;
    } catch (err: any) {
      state.error = err.message || 'Failed to fetch members';
      console.error('[MembersStore] Failed to fetch members:', err);
    } finally {
      state.isLoading = false;
    }
  };

  const searchUsers = async (query: string) => {
    if (!query || query.length < 2) {
      state.availableUsers = [];
      return;
    }

    state.isLoadingUsers = true;
    try {
      const response = await authStore.apiCall<{ items: User[] }>(
        `/v1/users?search=${encodeURIComponent(query)}&page_size=20`,
        { headers: contextStore.getContextHeaders }
      );

      state.availableUsers = response.items.map(user => ({
        value: user.id,
        label: user.profile?.first_name && user.profile?.last_name 
          ? `${user.profile.first_name} ${user.profile.last_name}`
          : user.email,
        email: user.email
      }));
    } catch (error) {
      console.error('Failed to search users:', error);
      state.availableUsers = [];
    } finally {
      state.isLoadingUsers = false;
    }
  };

  const fetchRoles = async () => {
    if (!state.entityId) return;

    state.isLoadingRoles = true;
    try {
      const response = await authStore.apiCall<{ items: Role[] }>(
        `/v1/entities/${state.entityId}/roles`,
        { headers: contextStore.getContextHeaders }
      );

      state.availableRoles = response.items.map(role => ({
        value: role.id,
        label: role.display_name || role.name,
        description: role.description || 'No description'
      }));
    } catch (error) {
      console.error('Failed to fetch roles:', error);
      state.availableRoles = [];
      toast.add({
        title: 'Error',
        description: 'Failed to load roles. Please ensure roles are configured for this entity.',
        color: 'error'
      });
    } finally {
      state.isLoadingRoles = false;
    }
  };

  const createMember = async (data: { user_id: string; role_ids: string[]; is_active?: boolean; valid_from?: string; valid_until?: string }) => {
    if (!state.entityId) throw new Error('No entity selected');
    
    // Validate we have at least one role
    if (!data.role_ids || data.role_ids.length === 0) {
      throw new Error('At least one role is required');
    }

    // For each role, create a member entry
    const promises = data.role_ids.map(async (roleId) => {
      const memberData: EntityMemberCreateRequest = {
        user_id: data.user_id,
        role_id: roleId,
        is_active: data.is_active !== false
      };
      
      // Only add dates if they have values
      if (data.valid_from && data.valid_from !== null) {
        memberData.valid_from = data.valid_from;
      }
      if (data.valid_until && data.valid_until !== null) {
        memberData.valid_until = data.valid_until;
      }

      return authStore.apiCall(`/v1/entities/${state.entityId}/members`, {
        method: 'POST',
        body: memberData,
        headers: contextStore.getContextHeaders
      });
    });

    await Promise.all(promises);

    toast.add({
      title: 'Member added',
      description: `User has been added with ${data.role_ids.length} role${data.role_ids.length > 1 ? 's' : ''}`,
      color: 'success'
    });

    // Refresh members list
    await fetchMembers();
  };

  const updateMember = async (userId: string, data: { role_ids?: string[]; status?: string; is_active?: boolean; valid_from?: string | null; valid_until?: string | null }) => {
    if (!state.entityId) throw new Error('No entity selected');

    const member = state.members.find(m => m.user_id === userId);
    if (!member) throw new Error('Member not found');

    // Check if roles have changed
    const currentRoleIds = member.roles?.map(r => r.id) || [];
    const rolesChanged = data.role_ids && !arraysEqual(currentRoleIds, data.role_ids);

    if (rolesChanged && data.role_ids) {
      // First, remove the user from the entity completely
      await authStore.apiCall(`/v1/entities/${state.entityId}/members/${userId}`, {
        method: 'DELETE',
        headers: contextStore.getContextHeaders
      });
      
      // Then add them back with the new roles
      const promises = data.role_ids.map(async (roleId) => {
        const memberData: EntityMemberCreateRequest = {
          user_id: userId,
          role_id: roleId,
          is_active: data.is_active !== undefined ? data.is_active : true,
          valid_from: data.valid_from || undefined,
          valid_until: data.valid_until || undefined
        };

        return authStore.apiCall(`/v1/entities/${state.entityId}/members`, {
          method: 'POST',
          body: memberData,
          headers: contextStore.getContextHeaders
        });
      });

      await Promise.all(promises);

      toast.add({
        title: 'Member updated',
        description: `User roles updated to ${data.role_ids.length} role${data.role_ids.length > 1 ? 's' : ''}`,
        color: 'success'
      });
    } else {
      // If only status or dates changed, update normally
      const updateData: EntityMemberUpdateRequest = {};

      if (data.is_active !== undefined) updateData.is_active = data.is_active;
      if (data.valid_from !== undefined) updateData.valid_from = data.valid_from;
      if (data.valid_until !== undefined) updateData.valid_until = data.valid_until;

      if (Object.keys(updateData).length > 0) {
        await authStore.apiCall(`/v1/entities/${state.entityId}/members/${userId}`, {
          method: 'PUT',
          body: updateData,
          headers: contextStore.getContextHeaders
        });

        toast.add({
          title: 'Member updated',
          description: 'Member details have been updated',
          color: 'success'
        });
      }
    }

    // Refresh members list
    await fetchMembers();
  };

  const removeMember = async (userId: string) => {
    if (!state.entityId) throw new Error('No entity selected');

    await authStore.apiCall(`/v1/entities/${state.entityId}/members/${userId}`, {
      method: 'DELETE',
      headers: contextStore.getContextHeaders
    });

    toast.add({
      title: 'Member removed',
      description: 'Member has been removed from this entity',
      color: 'success'
    });

    // Refresh members list
    await fetchMembers();
  };

  // UI Actions
  const openCreateDrawer = () => {
    state.selectedMember = null;
    state.ui.drawerMode = "create";
    state.ui.drawerOpen = true;
    // Clear any stale role data and fetch fresh roles
    state.availableRoles = [];
    fetchRoles();
  };

  const openEditDrawer = (member: EntityMember) => {
    state.selectedMember = member;
    state.ui.drawerMode = "edit";
    state.ui.drawerOpen = true;
    // Clear any stale role data and fetch fresh roles
    state.availableRoles = [];
    fetchRoles();
  };

  const closeDrawer = () => {
    state.ui.drawerOpen = false;
    state.selectedMember = null;
    state.availableUsers = [];
  };

  const clearAvailableUsers = () => {
    state.availableUsers = [];
  };

  // Utility functions
  const getMemberDisplayName = (member: EntityMember) => {
    return member.user_name || member.user_email || 'Unknown User';
  };

  // Helper function to compare arrays
  const arraysEqual = (a: string[], b: string[]) => {
    if (a.length !== b.length) return false;
    const sortedA = [...a].sort();
    const sortedB = [...b].sort();
    return sortedA.every((val, index) => val === sortedB[index]);
  };

  // Computed
  const members = computed(() => state.members);
  const selectedMember = computed(() => state.selectedMember);
  const isLoading = computed(() => state.isLoading);
  const error = computed(() => state.error);
  const totalPages = computed(() => state.totalPages);
  const currentPage = computed(() => state.currentPage);
  const pageSize = computed(() => state.pageSize);
  const availableUsers = computed(() => state.availableUsers);
  const availableRoles = computed(() => state.availableRoles);
  const isLoadingUsers = computed(() => state.isLoadingUsers);
  const isLoadingRoles = computed(() => state.isLoadingRoles);
  const ui = computed(() => state.ui);
  const entityName = computed(() => state.entityName);

  // Setters
  const setCurrentPage = (page: number) => {
    state.currentPage = page;
    fetchMembers();
  };

  return {
    // State
    members,
    selectedMember,
    isLoading,
    error,
    totalPages,
    currentPage,
    pageSize,
    availableUsers,
    availableRoles,
    isLoadingUsers,
    isLoadingRoles,
    ui,
    entityName,
    // Actions
    setEntity,
    fetchMembers,
    searchUsers,
    fetchRoles,
    createMember,
    updateMember,
    removeMember,
    openCreateDrawer,
    openEditDrawer,
    closeDrawer,
    clearAvailableUsers,
    setCurrentPage,
    getMemberDisplayName
  };
});