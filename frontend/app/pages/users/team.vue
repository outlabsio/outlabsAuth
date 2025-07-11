<script setup lang="ts">
// Assuming Member type aligns with the User type from users.store
import type { User, UserAdminUpdatePayload } from "~/stores/users.store";
import type { Member as BaseMember, AvatarProps } from "~/types";
import type { FormError, FormSubmitEvent } from "#ui/types";

// Extend Member type to include ID and superuser status
interface Member extends BaseMember {
  id: string; // Add ID to support edit/delete operations
  is_superuser: boolean; // Add superuser status
  is_active: boolean; // Add active status
}

// Use the Users store with updated methods
const usersStore = useUsersStore();
const { users: storeUsers, loading, error } = storeToRefs(usersStore);

// Get current user from auth store
const authStore = useAuthStore();

// Local state
const q = ref("");
const selectedTeamMember = ref<User | null>(null); // For editing
const editModalOpen = ref(false);
const editFormData = reactive({
  email: "",
  name: "",
  is_active: true,
  is_superuser: false,
  is_team_member: true,
  is_verified: false,
  locale: "en",
});

// Add modal state and data for team member removal
const removeFromTeamModalOpen = ref(false);
const memberToRemove = ref<{ id: string; name: string } | null>(null);

// Add modal state and data for team member deletion
const deleteModalOpen = ref(false);
const memberToDelete = ref<{ id: string; name: string } | null>(null);

// Add state for permissions modal
const permissionsModalOpen = ref(false);
const selectedPermissionsMember = ref<User | null>(null);

// Filtered team members list
const teamMembers = computed<User[]>(() => {
  // Filter for only team members and superusers (admins)
  return storeUsers.value.filter((user) => user.is_team_member || user.is_superuser);
});

// Map User to Member and filter by search query
const filteredTeamMembers = computed<Member[]>(() => {
  if (!teamMembers.value.length) return [];

  // 1. Filter based on search query (name or email)
  const searched = teamMembers.value.filter((user) => {
    const nameMatch = user.name ? user.name.toLowerCase().includes(q.value.toLowerCase()) : false;
    const emailMatch = user.email ? user.email.toLowerCase().includes(q.value.toLowerCase()) : false;
    return nameMatch || emailMatch;
  });

  // 2. Map filtered User[] to Member[]
  return searched.map((user): Member => {
    const username = user.email?.split("@")[0] || ""; // Get first part of email
    const role = user.is_superuser ? "owner" : "member"; // Determine role
    const avatarName = user.name || user.email?.split("@")[0] || "TM"; // Use name or part of email
    const avatarSrc = `https://avatars.dicebear.com/api/initials/${encodeURIComponent(avatarName)}.svg`;
    const avatar: AvatarProps = {
      src: avatarSrc,
      // Add other props as needed
    };

    return {
      id: user.id, // ID for actions
      name: user.name || "Team Member", // Ensure name exists
      username: username,
      role: role,
      avatar: avatar,
      is_superuser: user.is_superuser, // Admin badge
      is_active: user.is_active, // Active status badge
    };
  });
});

// Handler for editing a team member
const handleEditMember = (member: Member) => {
  // Find the original user from users
  const user = storeUsers.value.find((u) => u.id === member.id);
  if (!user) return;

  // Set the selected member and populate form data
  selectedTeamMember.value = user;
  editFormData.email = user.email;
  editFormData.name = user.name || "";
  editFormData.is_active = user.is_active;
  editFormData.is_superuser = user.is_superuser;
  editFormData.is_team_member = user.is_team_member;
  editFormData.is_verified = user.is_verified;
  editFormData.locale = user.locale || "en";

  editModalOpen.value = true;
};

// Save edited member
const saveEditedMember = async () => {
  if (!selectedTeamMember.value) return;

  try {
    const updateData: UserAdminUpdatePayload = {
      name: editFormData.name || null,
      is_active: editFormData.is_active,
      is_superuser: editFormData.is_superuser,
      is_team_member: editFormData.is_team_member,
      locale: editFormData.locale,
    };

    await usersStore.updateUser(selectedTeamMember.value.id, updateData);

    useToast().add({
      title: "Success",
      description: "Team member updated successfully",
      color: "success",
    });
    editModalOpen.value = false;
    selectedTeamMember.value = null;
  } catch (err) {
    useToast().add({
      title: "Error",
      description: "Failed to update team member",
      color: "error",
    });
    console.error("Failed to update team member:", err);
  }
};

// Handler for toggling user active status
const handleToggleActive = async (data: { id: string; active: boolean }) => {
  try {
    const updateData: UserAdminUpdatePayload = {
      is_active: data.active,
    };

    await usersStore.updateUser(data.id, updateData);

    // Show success notification
    const message = data.active ? "User activated successfully" : "User suspended successfully";
    useToast().add({
      title: "Success",
      description: message,
      color: "success",
    });
  } catch (err) {
    // Show error notification
    useToast().add({
      title: "Error",
      description: "Failed to update user status",
      color: "error",
    });
    console.error("Failed to update user status:", err);
  }
};

// Handler for managing user permissions
const handleManagePermissions = (member: Member) => {
  // Find the original user from users
  const user = storeUsers.value.find((u) => u.id === member.id);
  if (!user) return;

  selectedPermissionsMember.value = user;
  permissionsModalOpen.value = true;
};

// Handle permissions saved
const handlePermissionsSaved = (permissions: any) => {
  // In a real app, you might want to refresh user data or update UI
  useToast().add({
    title: "Success",
    description: "Permissions updated successfully",
    color: "success",
  });
  selectedPermissionsMember.value = null;
};

// Handler for removing user from team
const handleToggleTeamMember = async ({ id, isTeamMember }: { id: string; isTeamMember: boolean }) => {
  const member = teamMembers.value.find((m) => m.id === id);
  if (!member) return;

  memberToRemove.value = {
    id,
    name: member.name || member.email,
  };
  removeFromTeamModalOpen.value = true;
};

// Confirm removal from team
const confirmRemoveFromTeam = async () => {
  if (!memberToRemove.value) return;

  try {
    await usersStore.updateUser(memberToRemove.value.id, {
      is_team_member: false,
    });

    useToast().add({
      title: "Success",
      description: "User removed from team successfully",
      color: "success",
    });
    removeFromTeamModalOpen.value = false;
    memberToRemove.value = null;
  } catch (err) {
    useToast().add({
      title: "Error",
      description: "Failed to remove user from team",
      color: "error",
    });
    console.error("Failed to update team member status:", err);
  }
};

// Handler for deleting a team member
const handleDeleteMember = async (memberId: string) => {
  const member = teamMembers.value.find((m) => m.id === memberId);
  if (!member) return;

  memberToDelete.value = {
    id: memberId,
    name: member.name || member.email,
  };
  deleteModalOpen.value = true;
};

// Confirm deletion
const confirmDeleteMember = async () => {
  if (!memberToDelete.value) return;

  try {
    await usersStore.deleteUser(memberToDelete.value.id);

    useToast().add({
      title: "Success",
      description: "Team member removed successfully",
      color: "success",
    });
    deleteModalOpen.value = false;
    memberToDelete.value = null;
  } catch (err) {
    useToast().add({
      title: "Error",
      description: "Failed to remove team member",
      color: "error",
    });
    console.error("Failed to delete team member:", err);
  }
};

// Handle search input changes (with debounce)
const debouncedSearch = useDebounceFn(() => {
  usersStore.setSearchQuery(q.value);
}, 300);

watch(q, () => {
  debouncedSearch();
});

// Fetch team members on mount - using 'admin' role to get both superusers and team members
onMounted(() => {
  usersStore.fetchUsers(0, 100, "admin"); // Get all admin users (superusers + team members)
});

// Form validation
const validate = (state: any): FormError[] => {
  const errors: FormError[] = [];
  if (!state.email) errors.push({ name: "email", message: "Email is required" });
  if (state.locale && !["en", "es"].includes(state.locale)) {
    errors.push({ name: "locale", message: "Invalid locale selection" });
  }
  return errors;
};

// Filter permissions based on search query
const filteredPermissions = computed(() => {
  if (!permissionsSearch.value) return userPermissions.value;

  const search = permissionsSearch.value.toLowerCase();
  return userPermissions.value.filter((perm) => {
    const categoryName = getPermissionCategory(perm.categoryId)?.name || "";
    return perm.name.toLowerCase().includes(search) || perm.description.toLowerCase().includes(search) || categoryName.toLowerCase().includes(search);
  });
});

// Group permissions by category for display
const groupedPermissions = computed(() => {
  const grouped: Record<string, typeof filteredPermissions.value> = {};

  // Initialize empty arrays for each category
  permissionCategories.forEach((cat) => {
    grouped[cat.id] = [];
  });

  // Fill with filtered permissions
  filteredPermissions.value.forEach((perm) => {
    if (grouped[perm.categoryId]) {
      grouped[perm.categoryId].push(perm);
    }
  });

  return grouped;
});

// Helper to get category details
const getPermissionCategory = (categoryId: string) => {
  return permissionCategories.find((cat) => cat.id === categoryId);
};

// Toggle permission status
const togglePermission = (permissionId: string) => {
  const permIndex = userPermissions.value.findIndex((p) => p.id === permissionId);
  if (permIndex !== -1) {
    userPermissions.value[permIndex].granted = !userPermissions.value[permIndex].granted;
  }
};

// Select all permissions in a category
const selectAllInCategory = (categoryId: string) => {
  userPermissions.value = userPermissions.value.map((perm) => {
    if (perm.categoryId === categoryId) {
      return { ...perm, granted: true };
    }
    return perm;
  });
};

// Deselect all permissions in a category
const deselectAllInCategory = (categoryId: string) => {
  userPermissions.value = userPermissions.value.map((perm) => {
    if (perm.categoryId === categoryId) {
      return { ...perm, granted: false };
    }
    return perm;
  });
};

// Handler to save permissions
const savePermissions = async () => {
  try {
    // In a real app, you would send updated permissions to backend
    // await api.updateUserPermissions(selectedPermissionsMember.value.id, userPermissions.value);

    // Mock successful save
    await new Promise((resolve) => setTimeout(resolve, 800));

    useToast().add({
      title: "Success",
      description: "User permissions updated successfully",
      color: "success",
    });

    permissionsModalOpen.value = false;
    selectedPermissionsMember.value = null;
  } catch (err) {
    useToast().add({
      title: "Error",
      description: "Failed to update user permissions",
      color: "error",
    });
    console.error("Failed to update permissions:", err);
  }
};

// No results state when filtering
const hasNoResults = computed(() => {
  if (!permissionsSearch.value) return false;
  return Object.values(groupedPermissions.value).every((arr) => arr.length === 0);
});
</script>

<template>
  <div>
    <UPageCard title="Team" description="Invite and manage team members." variant="naked" orientation="horizontal" class="mb-4">
      <!-- Remove invite button -->
    </UPageCard>

    <UPageCard variant="subtle" :ui="{ container: 'p-0 sm:p-0 gap-y-0', header: 'p-4 mb-0 border-b border-(--ui-border)' }">
      <template #header>
        <UInput v-model="q" icon="i-lucide-search" placeholder="Search team members" autofocus class="w-full" />
      </template>

      <!-- Loading state -->
      <div v-if="loading" class="flex items-center justify-center py-8">
        <ULoading size="lg" />
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="p-4 text-red-500">
        {{ error }}
      </div>

      <!-- Empty state -->
      <div v-else-if="filteredTeamMembers.length === 0" class="p-8 text-center text-gray-500">
        <div class="mb-2 text-3xl">👥</div>
        <p class="text-xl font-medium mb-1">No team members found</p>
        <p v-if="q" class="text-sm">No results matching "{{ q }}". Try a different search term or clear the search.</p>
        <p v-else class="text-sm">You haven't added any team members yet. Click "Invite Team Member" to get started.</p>
      </div>

      <!-- Team members list -->
      <SettingsMembersList
        v-else
        :members="filteredTeamMembers"
        @edit="handleEditMember"
        @delete="handleDeleteMember"
        @toggle-active="handleToggleActive"
        @manage-permissions="handleManagePermissions"
        @toggle-team-member="handleToggleTeamMember"
      />
    </UPageCard>

    <!-- Edit Member Modal -->
    <UModal v-model:open="editModalOpen" size="xl">
      <template #header>
        <div class="flex items-center gap-2">
          <UAvatar v-if="selectedTeamMember" :src="`https://avatars.dicebear.com/api/initials/${encodeURIComponent(selectedTeamMember.name || selectedTeamMember.email)}.svg`" size="sm" />
          <div>
            <h3 class="text-xl font-semibold">Edit Team Member</h3>
            <p class="text-sm text-gray-500">{{ selectedTeamMember?.email }}</p>
          </div>
        </div>
      </template>

      <template #body>
        <UForm :validate="validate" :state="editFormData" class="space-y-6" @submit="saveEditedMember" id="editMemberForm">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
            <!-- Left Column -->
            <div class="space-y-6">
              <!-- Basic Information Section -->
              <div>
                <h4 class="font-medium text-base mb-4 flex items-center text-primary">
                  <UIcon name="i-lucide-user" class="mr-2 text-primary bg-primary/10 p-1.5 rounded-md" />
                  Basic Information
                </h4>
                <div class="space-y-4">
                  <UFormField name="email" label="Email Address">
                    <UInput v-model="editFormData.email" type="email" placeholder="user@example.com" />
                  </UFormField>

                  <UFormField name="name" label="Full Name" help="Enter the user's full name">
                    <UInput v-model="editFormData.name" placeholder="John Doe" />
                  </UFormField>
                </div>
              </div>

              <!-- Roles Section - renamed to Role Settings -->
              <div>
                <h4 class="font-medium text-base mb-4 flex items-center text-indigo-600">
                  <UIcon name="i-lucide-users-2" class="mr-2 text-indigo-600 bg-indigo-100 p-1.5 rounded-md" />
                  Role Settings
                </h4>
                <div class="space-y-4">
                  <UFormField name="is_team_member" label="Team Member Status">
                    <UToggle v-model="editFormData.is_team_member" size="md" :ui="{ wrapper: 'flex items-center gap-3' }">
                      <template #on>
                        <div class="flex items-center gap-1.5">
                          <UIcon name="i-lucide-users" class="text-indigo-600 flex-shrink-0" />
                          <span>Team Member</span>
                        </div>
                      </template>
                      <template #off>
                        <div class="flex items-center gap-1.5">
                          <UIcon name="i-lucide-user" class="text-gray-500 flex-shrink-0" />
                          <span>Regular User</span>
                        </div>
                      </template>
                    </UToggle>
                  </UFormField>

                  <UFormField name="is_superuser" label="Admin Status" :help="selectedTeamMember?.is_superuser ? 'Admin status cannot be changed for security reasons' : ''">
                    <UToggle v-model="editFormData.is_superuser" size="md" :ui="{ wrapper: 'flex items-center gap-3' }" :disabled="selectedTeamMember?.is_superuser">
                      <template #on>
                        <div class="flex items-center gap-1.5">
                          <UIcon name="i-lucide-shield" class="text-indigo-600 flex-shrink-0" />
                          <span>Admin</span>
                        </div>
                      </template>
                      <template #off>
                        <div class="flex items-center gap-1.5">
                          <UIcon name="i-lucide-shield-off" class="text-gray-500 flex-shrink-0" />
                          <span>Not Admin</span>
                        </div>
                      </template>
                    </UToggle>
                  </UFormField>
                </div>
              </div>
            </div>

            <!-- Right Column -->
            <div class="space-y-6">
              <!-- Status Section -->
              <div>
                <h4 class="font-medium text-base mb-4 flex items-center text-emerald-600">
                  <UIcon name="i-lucide-activity" class="mr-2 text-emerald-600 bg-emerald-100 p-1.5 rounded-md" />
                  Account Status
                </h4>
                <div class="space-y-4">
                  <UFormField name="is_active" label="Account Status">
                    <UToggle v-model="editFormData.is_active" size="md" :ui="{ wrapper: 'flex items-center gap-3' }">
                      <template #on>
                        <div class="flex items-center gap-1.5">
                          <UIcon name="i-lucide-check-circle" class="text-emerald-600 flex-shrink-0" />
                          <span>Active</span>
                        </div>
                      </template>
                      <template #off>
                        <div class="flex items-center gap-1.5">
                          <UIcon name="i-lucide-x-circle" class="text-red-500 flex-shrink-0" />
                          <span>Inactive</span>
                        </div>
                      </template>
                    </UToggle>
                  </UFormField>

                  <UFormField name="is_verified" label="Email Verification">
                    <UToggle v-model="editFormData.is_verified" size="md" :ui="{ wrapper: 'flex items-center gap-3' }">
                      <template #on>
                        <div class="flex items-center gap-1.5">
                          <UIcon name="i-lucide-mail-check" class="text-emerald-600 flex-shrink-0" />
                          <span>Verified</span>
                        </div>
                      </template>
                      <template #off>
                        <div class="flex items-center gap-1.5">
                          <UIcon name="i-lucide-mail-question" class="text-amber-500 flex-shrink-0" />
                          <span>Unverified</span>
                        </div>
                      </template>
                    </UToggle>
                  </UFormField>
                </div>
              </div>

              <!-- Preferences Section -->
              <div>
                <h4 class="font-medium text-base mb-4 flex items-center text-amber-600">
                  <UIcon name="i-lucide-settings" class="mr-2 text-amber-600 bg-amber-100 p-1.5 rounded-md" />
                  Preferences
                </h4>
                <UFormField name="locale" label="Language" help="Select the user's preferred language">
                  <USelect
                    v-model="editFormData.locale"
                    :items="[
                      { label: 'English', value: 'en' },
                      { label: 'Spanish', value: 'es' },
                    ]"
                    placeholder="Select language"
                  />
                </UFormField>
              </div>
            </div>
          </div>
        </UForm>
      </template>

      <template #footer>
        <div class="flex justify-end w-full gap-3">
          <UButton color="neutral" variant="soft" label="Cancel" icon="i-lucide-x" @click="editModalOpen = false" />
          <UButton type="submit" form="editMemberForm" color="primary" variant="solid" label="Save Changes" icon="i-lucide-save" :loading="usersStore.loading" />
        </div>
      </template>
    </UModal>

    <!-- Remove from Team Confirmation Modal -->
    <UModal v-model:open="removeFromTeamModalOpen" title="Confirm Team Member Removal">
      <template #body>
        <div class="text-center space-y-4">
          <div class="flex justify-center mb-4">
            <UIcon name="i-lucide-alert-triangle" class="h-16 w-16 text-warning" />
          </div>
          <h3 class="font-bold text-xl mb-4">Remove Team Member</h3>
          <p class="py-4 text-lg">
            Are you sure you want to remove <strong>{{ memberToRemove?.name }}</strong> from the team?
            <br />
            <span class="text-warning">They will lose access to team member privileges.</span>
          </p>
          <div class="flex justify-center gap-4">
            <UButton color="neutral" label="Cancel" @click="removeFromTeamModalOpen = false" />
            <UButton color="warning" icon="i-lucide-user-minus" label="Remove from Team" :loading="usersStore.loading" @click="confirmRemoveFromTeam" />
          </div>
        </div>
      </template>
    </UModal>

    <!-- Delete Confirmation Modal -->
    <UModal v-model:open="deleteModalOpen" title="Confirm Team Member Deletion">
      <template #body>
        <div class="text-center space-y-4">
          <div class="flex justify-center mb-4">
            <UIcon name="i-lucide-alert-triangle" class="h-16 w-16 text-warning" />
          </div>
          <h3 class="font-bold text-xl mb-4">Delete Team Member</h3>
          <p class="py-4 text-lg">
            Are you sure you want to delete <strong>{{ memberToDelete?.name }}</strong> from the team?
            <br />
            <span class="text-warning">This action cannot be undone.</span>
          </p>
          <div class="flex justify-center gap-4">
            <UButton color="neutral" label="Cancel" @click="deleteModalOpen = false" />
            <UButton color="error" icon="i-lucide-trash" label="Delete Team Member" :loading="usersStore.loading" @click="confirmDeleteMember" />
          </div>
        </div>
      </template>
    </UModal>

    <!-- Permissions Modal -->
    <SettingsPermissionsModal v-model:open="permissionsModalOpen" :user="selectedPermissionsMember" @save="handlePermissionsSaved" />
  </div>
</template>

<style>
.permission-container {
  scrollbar-width: thin;
  scrollbar-color: rgba(156, 163, 175, 0.5) transparent;
}

.permission-container::-webkit-scrollbar {
  width: 6px;
}

.permission-container::-webkit-scrollbar-track {
  background: transparent;
}

.permission-container::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.5);
  border-radius: 20px;
}
</style>
