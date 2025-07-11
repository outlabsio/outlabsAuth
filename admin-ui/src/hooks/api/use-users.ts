import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/simple-fetch";
import { type User, type PaginatedResponse } from "@/lib/api/types";

interface UserFilters {
  entityId?: string;
  platformId?: string;
  status?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}

function buildUserUrl(filters?: UserFilters): string {
  const params = new URLSearchParams();
  
  if (filters?.entityId) {
    params.append("entity_id", filters.entityId);
  }
  if (filters?.platformId) {
    params.append("platform_id", filters.platformId);
  }
  if (filters?.status) {
    params.append("status", filters.status);
  }
  if (filters?.search) {
    params.append("search", filters.search);
  }
  if (filters?.page) {
    params.append("page", filters.page.toString());
  }
  if (filters?.pageSize) {
    params.append("page_size", filters.pageSize.toString());
  }
  
  const queryString = params.toString();
  return `/v1/users/${queryString ? `?${queryString}` : ""}`;
}

// Get users list
export function useUsers(filters?: UserFilters) {
  return useQuery({
    queryKey: ["users", filters],
    queryFn: () => api.get<PaginatedResponse<User>>(buildUserUrl(filters)),
  });
}

// Get single user
export function useUser(userId: string | null) {
  return useQuery({
    queryKey: ["user", userId],
    queryFn: () => api.get<User>(`/v1/users/${userId}`),
    enabled: !!userId,
  });
}

// Get current user
export function useCurrentUser() {
  return useQuery({
    queryKey: ["current-user"],
    queryFn: () => api.get<User>("/v1/users/me"),
  });
}

// Create user mutation
export function useCreateUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: {
      username: string;
      email: string;
      password: string;
      full_name?: string;
      is_active?: boolean;
    }) => api.post<User>("/v1/users/", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

// Update user mutation
export function useUpdateUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Partial<User>) => 
      api.patch<User>(`/v1/users/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["user", variables.id] });
    },
  });
}

// Delete user mutation
export function useDeleteUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => 
      api.delete(`/v1/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

// Resend invitation
export function useResendInvitation() {
  return useMutation({
    mutationFn: (userId: string) => 
      api.post(`/v1/users/${userId}/resend-invitation`, {}),
  });
}