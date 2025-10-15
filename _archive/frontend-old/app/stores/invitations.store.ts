import { defineStore } from "pinia";

interface Invitation {
  id: string;
  email: string;
  code: string;
  created_at: string;
  expires_at: string;
  is_used: boolean;
  is_revoked: boolean;
  invited_by: string;
}

export const useInvitationsStore = defineStore("invitations", () => {
  const invitations = ref<Invitation[]>([]);
  const totalInvitations = ref(0);
  const currentPage = ref(1);
  const searchQuery = ref("");
  const sortColumn = ref("");
  const sortDirection = ref<"asc" | "desc">("asc");

  const fetchInvitations = async (skip = 0, limit = 10) => {
    try {
      const authStore = useAuthStore();
      const response = await authStore.apiCall<Invitation[]>("/invitations", {
        params: {
          skip,
          limit,
          search: searchQuery.value,
          sort_column: sortColumn.value,
          sort_direction: sortDirection.value,
        },
      });
      invitations.value = response;
      totalInvitations.value = response.length;
    } catch (error) {
      console.error("Error fetching invitations:", error);
      throw error;
    }
  };

  const createInvitation = async (email: string) => {
    try {
      const authStore = useAuthStore();
      const response = await authStore.apiCall("/invitations", {
        method: "POST",
        body: { email },
      });
      await fetchInvitations();
      return response;
    } catch (error: any) {
      console.error("Error creating invitation:", error);
      if (error.data?.detail) {
        throw new Error(error.data.detail);
      }
      throw new Error("INVITATION_CREATION_FAILED");
    }
  };

  const resendInvitation = async (id: string) => {
    try {
      const authStore = useAuthStore();
      const response = await authStore.apiCall(`/invitations/${id}/resend`, {
        method: "POST",
      });
      return response;
    } catch (error: any) {
      console.error("Error resending invitation:", error);
      throw new Error(error.data?.message || error.message || "INVITATION_RESEND_FAILED");
    }
  };

  const revokeInvitation = async (id: string) => {
    try {
      const authStore = useAuthStore();
      const response = await authStore.apiCall(`/invitations/${id}`, {
        method: "DELETE",
      });
      await fetchInvitations();
      return response;
    } catch (error: any) {
      console.error("Error revoking invitation:", error);
      throw new Error(error.data?.message || error.message || "INVITATION_REVOKE_FAILED");
    }
  };

  const sortInvitations = (column: string, direction: "asc" | "desc") => {
    sortColumn.value = column;
    sortDirection.value = direction;
    fetchInvitations();
  };

  const setSearchQuery = (query: string) => {
    searchQuery.value = query;
    currentPage.value = 1;
    fetchInvitations();
  };

  const setCurrentPage = (page: number) => {
    currentPage.value = page;
    fetchInvitations();
  };

  return {
    invitations,
    totalInvitations,
    currentPage,
    fetchInvitations,
    createInvitation,
    resendInvitation,
    revokeInvitation,
    sortInvitations,
    setSearchQuery,
    setCurrentPage,
  };
});
