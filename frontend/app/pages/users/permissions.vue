<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import { upperFirst } from "scule";
import PermissionModal from "~/components/user/PermissionModal.vue";

// Define Permission type based on permissions.store.ts
interface Permission {
  _id?: string;
  name: string;
  description: string;
}

const toast = useToast();
const permissionsStore = usePermissionsStore();

// Get permissions from the store
const status = ref("idle");

// Update status when loading state changes
watch(
  () => permissionsStore.isLoading,
  (loading) => {
    status.value = loading ? "pending" : "success";
  },
  { immediate: true }
);

// Initialize refs for modal state
const permissionModalOpen = ref(false);
const selectedPermission = ref<Partial<Permission> | null>(null);
const usersModalOpen = ref(false);
const selectedPermissionName = ref("");
const permissionUsers = ref<Array<{ _id: string; name: string; permissions?: string[] }>>([]);
const permissionType = ref<"resource-set" | "custom">("resource-set");
const resourceSetName = ref("");
const resourceDescription = ref("");
const deleteModalOpen = ref(false);
const permissionToDelete = ref<Permission | null>(null);

// For conditions in the template
const canSave = computed(() => {
  if (permissionType.value === "resource-set") {
    return !!resourceSetName.value;
  }
  return selectedPermission.value?.name && selectedPermission.value?.description;
});

const editMode = computed(() => {
  return !!selectedPermission.value?._id;
});

// Initial fetch
onMounted(() => {
  console.log("Permissions page mounted, calling fetchPermissions");
  permissionsStore.fetchPermissions();

  // Let's also add a delayed check
  setTimeout(() => {
    console.log("Delayed check after 1 second:");
    console.log("Permission count:", permissionsStore.permissions.length);
    console.log("Resource sets:", permissionsStore.resourceSets.length);
    console.log("Custom permissions:", permissionsStore.customPermissions.length);
  }, 1000);
});

// Set search query
const setSearchQuery = (query: string | number) => {
  permissionsStore.setSearchQuery(String(query));
};

// View users with a specific permission
const viewUsersWithPermission = async (permissionName: string) => {
  try {
    selectedPermissionName.value = permissionName;
    const users = await permissionsStore.getUsersWithPermission(permissionName);
    permissionUsers.value = users;
    usersModalOpen.value = true;
  } catch (error) {
    toast.add({
      title: "Error",
      description: "Failed to load users with permission",
      color: "error",
    });
  }
};

// View users for a permission set
const viewUsersForSet = async (group: PermissionGroup) => {
  try {
    selectedPermissionName.value = `${group.resource} set`;
    const users = await permissionsStore.getUsersForPermissionSet(group);
    permissionUsers.value = users;
    usersModalOpen.value = true;
  } catch (error) {
    toast.add({
      title: "Error",
      description: "Failed to fetch users with this permission set",
      color: "error",
    });
  }
};

// Add or edit a permission
const editPermission = (permission?: Permission) => {
  if (permission) {
    selectedPermission.value = { ...permission };

    // Check if this is a resource:action formatted permission
    if (permission.name && permission.name.includes(":")) {
      const [resourceName, action] = permission.name.split(":");

      // If it's an 'all' permission, we'll assume it's part of a resource set
      if (action === "all") {
        permissionType.value = "resource-set";
        resourceSetName.value = resourceName || "";

        // Try to extract the base description from the format "Full access to all X operations (Y)"
        if (permission.description) {
          const descMatch = permission.description.match(/Full access to all .+ operations \((.+)\)/);
          resourceDescription.value = descMatch && descMatch[1] ? descMatch[1] : "";
        }
      } else {
        permissionType.value = "custom";
      }
    } else {
      permissionType.value = "custom";
    }
  } else {
    selectedPermission.value = { name: "", description: "" };
    permissionType.value = "resource-set"; // Default for new permissions
    resourceSetName.value = "";
    resourceDescription.value = "";
  }
  permissionModalOpen.value = true;
};

// Edit a resource set
const editResourceSet = (group: PermissionGroup) => {
  permissionType.value = "resource-set";
  resourceSetName.value = group.resource || "";

  // Get description from one of the permissions (preferably from 'all')
  const allPerm = group.permissions.find((p) => p.name?.includes(":all"));
  if (allPerm?.description) {
    const descMatch = allPerm.description.match(/Full access to all .+ operations \((.+)\)/);
    resourceDescription.value = descMatch && descMatch[1] ? descMatch[1] : "";
  } else if (group.permissions.length > 0) {
    const firstPerm = group.permissions[0];
    if (firstPerm?.description) {
      const descMatch = firstPerm.description.match(/\((.+)\)/);
      resourceDescription.value = descMatch && descMatch[1] ? descMatch[1] : "";
    }
  }

  selectedPermission.value = { name: "", description: "" };
  permissionModalOpen.value = true;
};

// Delete a permission
const deletePermission = async (permission: Permission) => {
  if (!permission._id) return;
  permissionToDelete.value = permission;
  deleteModalOpen.value = true;
};

// Confirm deletion of a permission
const confirmDelete = async () => {
  if (!permissionToDelete.value || !permissionToDelete.value._id) return;

  try {
    await permissionsStore.deletePermission(permissionToDelete.value._id);
    toast.add({
      title: "Success",
      description: `Permission ${permissionToDelete.value.name} deleted`,
      color: "success",
    });
    deleteModalOpen.value = false;
    permissionToDelete.value = null;
  } catch (error) {
    toast.add({
      title: "Error",
      description: "Failed to delete permission",
      color: "error",
    });
  }
};

// Add confirmation flow for permission set deletion
const deleteSetModalOpen = ref(false);
const permissionSetToDelete = ref<PermissionGroup | null>(null);

// Prepare to delete a permission set
const deletePermissionSet = (group: PermissionGroup) => {
  permissionSetToDelete.value = group;
  deleteSetModalOpen.value = true;
};

// Confirm deletion of a permission set
const confirmDeleteSet = async () => {
  if (!permissionSetToDelete.value) return;

  try {
    const result = await permissionsStore.deleteResourceSet(permissionSetToDelete.value);
    if (result.errors.length > 0) {
      toast.add({
        title: "Warning",
        description: `Deleted ${result.deletedCount} of ${result.total} permissions. Some errors occurred.`,
        color: "warning",
      });
    } else {
      toast.add({
        title: "Success",
        description: `Permission set deleted successfully`,
        color: "success",
      });
    }
    deleteSetModalOpen.value = false;
    permissionSetToDelete.value = null;
  } catch (error) {
    toast.add({
      title: "Error",
      description: "Failed to delete permission set",
      color: "error",
    });
  }
};

// Save a permission (create or update)
const savePermission = async () => {
  if (!selectedPermission.value) return;

  try {
    if (permissionType.value === "resource-set" && !selectedPermission.value._id) {
      // Create a complete set of permissions for resource
      if (!resourceSetName.value) {
        toast.add({
          title: "Validation Error",
          description: "Resource name is required",
          color: "error",
        });
        return;
      }

      const result = await permissionsStore.createResourceSet(resourceSetName.value, resourceDescription.value);

      if (result.errors.length > 0) {
        toast.add({
          title: "Warning",
          description: `Created ${result.createdCount} of ${result.total} permissions. Some may already exist.`,
          color: "warning",
        });
      } else {
        toast.add({
          title: "Success",
          description: `Created complete permission set for ${resourceSetName.value}`,
          color: "success",
        });
      }
    } else if (selectedPermission.value._id) {
      // Update existing permission
      await permissionsStore.updatePermission(selectedPermission.value as Permission);
      toast.add({
        title: "Success",
        description: `Permission ${selectedPermission.value.name} updated`,
        color: "success",
      });
    } else {
      // Create new custom permission
      await permissionsStore.createPermission({
        name: selectedPermission.value.name || "",
        description: selectedPermission.value.description || "",
      });
      toast.add({
        title: "Success",
        description: `Permission ${selectedPermission.value.name} created`,
        color: "success",
      });
    }
    permissionModalOpen.value = false;
    resourceSetName.value = "";
    resourceDescription.value = "";
    selectedPermission.value = null;
  } catch (error) {
    toast.add({
      title: "Error",
      description: "Failed to save permission",
      color: "error",
    });
  }
};

// Define row action items
function getRowItems(row: any) {
  return [
    {
      type: "label",
      label: "Actions",
    },
    {
      label: "Edit permission",
      icon: "i-lucide-edit",
      onSelect() {
        editPermission(row.original);
      },
    },
    {
      label: "View users",
      icon: "i-lucide-users",
      onSelect() {
        viewUsersWithPermission(row.original.name);
      },
    },
    {
      type: "separator",
    },
    {
      label: "Delete permission",
      icon: "i-lucide-trash",
      color: "error",
      onSelect() {
        deletePermission(row.original);
      },
    },
  ];
}

// Resource Sets Table Columns
const resourceSetsColumns = computed(() => [
  {
    accessorKey: "resource",
    header: "Resource",
  },
  {
    accessorKey: "description",
    header: "Description",
  },
  {
    accessorKey: "actions",
    header: "Actions",
  },
]);

// Custom Permissions Table Columns
const customPermissionsColumns = computed(() => [
  {
    accessorKey: "name",
    header: "Name",
  },
  {
    accessorKey: "description",
    header: "Description",
  },
  {
    accessorKey: "actions",
    header: "Actions",
  },
]);

// Debug computed to check data structure
const resourceSetsData = computed(() => {
  console.log("Computing resourceSetsData");
  console.log("permissionsStore.resourceSets:", permissionsStore.resourceSets);

  // Ensure we're returning each set as a row object with all required fields
  const result = permissionsStore.resourceSets.map((set) => {
    // Return a new object to ensure reactivity
    return {
      // These fields must match the column accessorKeys
      resource: set.resource,
      description: permissionsStore.getResourceSetDescription(set),
      permissions: set.permissions,
      // For action handlers
      original: set,
    };
  });

  console.log("resourceSetsData result:", result);
  return result;
});

const customPermissionsData = computed(() => {
  console.log("Computing customPermissionsData");
  console.log("permissionsStore.customPermissions:", permissionsStore.customPermissions);

  // Ensure we're returning each permission as a row object with all required fields
  const result = permissionsStore.customPermissions.map((perm) => {
    // Return a new object to ensure reactivity
    return {
      // These fields must match the column accessorKeys
      name: perm.name,
      description: perm.description,
      // For action handlers
      original: perm,
    };
  });

  console.log("customPermissionsData result:", result);
  return result;
});

const pagination = ref({
  pageIndex: 0,
  pageSize: 10,
});

// Watch pagination changes
watch(
  () => pagination.value,
  (newPagination) => {
    const { pageIndex, pageSize } = newPagination;
    permissionsStore.fetchPermissions(pageIndex * pageSize, pageSize);
  },
  { deep: true }
);

// Fix type issues with table column parameters
type TableApiColumn = {
  id: string;
  getCanHide: () => boolean;
  getIsVisible: () => boolean;
  toggleVisibility: (value: boolean) => void;
};
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-1.5 mb-4">
      <UInput class="max-w-sm" icon="i-lucide-search" placeholder="Search permissions..." @update:model-value="setSearchQuery($event)" />
      <div class="flex flex-wrap items-center gap-1.5">
        <UButton icon="i-lucide-plus" label="Add permission" color="primary" size="sm" variant="subtle" :loading="permissionsStore.isCreating" @click="editPermission()" />
      </div>
    </div>

    <!-- Two-column layout for permissions -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Permission Sets Column -->
      <UCard class="h-fit">
        <template #header>
          <div class="flex items-center">
            <UIcon name="i-lucide-layers" class="h-6 w-6 mr-2 text-primary" />
            <h3 class="text-lg font-bold">Permission Sets</h3>
            <UBadge color="primary" size="sm" class="ml-2">{{ permissionsStore.resourceSetsCount }}</UBadge>
          </div>
        </template>

        <div v-if="status === 'pending'" class="p-8 flex justify-center">
          <UIcon name="i-lucide-loader-2" class="animate-spin h-8 w-8 text-gray-400" />
        </div>

        <div v-else-if="permissionsStore.resourceSets.length === 0" class="flex flex-col items-center justify-center py-6">
          <UIcon name="i-lucide-layers" class="text-gray-400 h-12 w-12 mb-2" />
          <p class="text-gray-500">No permission sets found</p>
        </div>

        <div v-else>
          <table class="w-full min-w-full overflow-hidden">
            <tbody class="divide-y divide-default">
              <tr v-for="set in resourceSetsData" :key="set.resource" class="hover:bg-elevated/50">
                <td class="p-4 text-sm border-b border-(--ui-border)">
                  <div class="font-semibold flex items-center">
                    <UIcon name="i-lucide-layers" class="h-5 w-5 mr-2 text-primary" />
                    {{ set.resource }}
                  </div>
                </td>
                <td class="p-4 text-sm whitespace-nowrap border-b border-(--ui-border)">{{ set.description }}</td>
                <td class="p-4 text-sm whitespace-nowrap border-b border-(--ui-border)">
                  <div class="flex gap-2">
                    <UButton
                      icon="i-lucide-pencil"
                      size="xs"
                      color="neutral"
                      variant="subtle"
                      :loading="permissionsStore.isUpdating && selectedPermission?._id === set.original.resource"
                      @click="editResourceSet(set.original)"
                    />
                    <UButton
                      icon="i-lucide-trash"
                      size="xs"
                      color="error"
                      variant="subtle"
                      :loading="permissionsStore.isDeleting && selectedPermission?._id === set.original.resource"
                      @click="deletePermissionSet(set.original)"
                    />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>

      <!-- Custom Permissions Column -->
      <UCard class="h-fit">
        <template #header>
          <div class="flex items-center">
            <UIcon name="i-lucide-key" class="h-6 w-6 mr-2 text-secondary" />
            <h3 class="text-lg font-bold">Custom Permissions</h3>
            <UBadge color="secondary" size="sm" class="ml-2">{{ permissionsStore.customPermissionsCount }}</UBadge>
          </div>
        </template>

        <div v-if="status === 'pending'" class="p-8 flex justify-center">
          <UIcon name="i-lucide-loader-2" class="animate-spin h-8 w-8 text-gray-400" />
        </div>

        <div v-else-if="permissionsStore.customPermissions.length === 0" class="flex flex-col items-center justify-center py-6">
          <UIcon name="i-lucide-key" class="text-gray-400 h-12 w-12 mb-2" />
          <p class="text-gray-500">No custom permissions found</p>
        </div>

        <div v-else>
          <table class="w-full min-w-full overflow-hidden">
            <tbody class="divide-y divide-default">
              <tr v-for="perm in customPermissionsData" :key="perm.name" class="hover:bg-elevated/50">
                <td class="p-4 text-sm border-b border-(--ui-border)">
                  <div class="font-semibold flex items-center">
                    <UIcon name="i-lucide-key" class="h-5 w-5 mr-2 text-secondary" />
                    {{ perm.name }}
                  </div>
                </td>
                <td class="p-4 text-sm whitespace-nowrap border-b border-(--ui-border)">{{ perm.description }}</td>
                <td class="p-4 text-sm whitespace-nowrap border-b border-(--ui-border)">
                  <div class="flex gap-2">
                    <UButton
                      icon="i-lucide-pencil"
                      size="xs"
                      color="neutral"
                      variant="subtle"
                      :loading="permissionsStore.isUpdating && selectedPermission?._id === perm.original._id"
                      @click="editPermission(perm.original)"
                    />
                    <UButton
                      icon="i-lucide-users"
                      size="xs"
                      color="neutral"
                      variant="subtle"
                      :loading="permissionsStore.isLoadingUsers && selectedPermission?._id === perm.original._id"
                      @click="viewUsersWithPermission(perm.original.name)"
                    />
                    <UButton
                      icon="i-lucide-trash"
                      size="xs"
                      color="error"
                      variant="subtle"
                      :loading="permissionsStore.isDeleting && selectedPermission?._id === perm.original._id"
                      @click="deletePermission(perm.original)"
                    />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>
    </div>
  </div>

  <!-- Permission Modal -->
  <PermissionModal
    v-model:open="permissionModalOpen"
    v-model:permission-type="permissionType"
    v-model:resource-set-name="resourceSetName"
    v-model:resource-description="resourceDescription"
    v-model:selected-permission="selectedPermission"
    :edit-mode="editMode"
    :is-loading="permissionsStore.isCreating || permissionsStore.isUpdating"
    @save="savePermission"
  />

  <!-- Users with Permission Modal -->
  <UModal v-model:open="usersModalOpen" :title="`Users with ${selectedPermissionName} permission`">
    <template #body>
      <div class="space-y-4">
        <div v-if="permissionUsers.length === 0" class="py-4 text-center text-gray-500">No users have this permission.</div>

        <div v-else class="space-y-2 max-h-80 overflow-y-auto">
          <div v-for="user in permissionUsers" :key="user._id" class="flex items-center justify-between p-2 rounded bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700">
            <div class="flex items-center">
              <UAvatar :src="`https://avatars.dicebear.com/api/initials/${user.name}.svg`" size="sm" class="mr-3" />
              <div>
                {{ user.name }}
                <div v-if="'permissions' in user" class="text-xs text-gray-500">
                  {{ user.permissions?.join(", ") }}
                </div>
              </div>
            </div>
            <UButton size="xs" color="error" variant="subtle" icon="i-lucide-x" label="Remove" :disabled="true" />
          </div>
        </div>

        <div class="mt-4 flex justify-end">
          <UButton label="Close" color="neutral" variant="subtle" :disabled="permissionsStore.isLoadingUsers" @click="usersModalOpen = false" />
        </div>
      </div>
    </template>
  </UModal>

  <!-- Delete Confirmation Modal -->
  <UModal v-model:open="deleteModalOpen" title="Confirm Deletion">
    <template #body>
      <div class="text-center space-y-4">
        <div class="flex justify-center mb-4">
          <UIcon name="i-lucide-alert-triangle" class="h-16 w-16 text-error" />
        </div>
        <h3 class="font-bold text-xl mb-4">Confirm Deletion</h3>
        <p class="py-4 text-lg">
          Are you sure you want to delete the permission "{{ permissionToDelete?.name }}"?
          <br />
          <strong class="text-orange-500">Make sure you know what you're doing.</strong>
          <br />
          This action cannot be undone and may break the entire permission system.
        </p>
        <div class="flex justify-center gap-4">
          <UButton color="neutral" label="Cancel" @click="deleteModalOpen = false" />
          <UButton color="error" icon="i-lucide-alert-triangle" label="Confirm Deletion" @click="confirmDelete" />
        </div>
      </div>
    </template>
  </UModal>

  <!-- Delete Permission Set Confirmation Modal -->
  <UModal v-model:open="deleteSetModalOpen" title="Confirm Set Deletion">
    <template #body>
      <div class="text-center space-y-4">
        <div class="flex justify-center mb-4">
          <UIcon name="i-lucide-alert-triangle" class="h-16 w-16 text-error" />
        </div>
        <h3 class="font-bold text-xl mb-4">Confirm Permission Set Deletion</h3>
        <p class="py-4 text-lg">
          Are you sure you want to delete the entire permission set for "<strong>{{ permissionSetToDelete?.resource }}</strong
          >"?
          <br />
          <strong class="text-orange-500">This will delete {{ permissionSetToDelete?.permissions?.length || 0 }} permissions at once.</strong>
          <br />
          This action cannot be undone and may break your system's permission structure.
        </p>
        <div class="flex justify-center gap-4">
          <UButton color="neutral" label="Cancel" @click="deleteSetModalOpen = false" />
          <UButton color="error" icon="i-lucide-alert-triangle" label="Confirm Deletion" @click="confirmDeleteSet" />
        </div>
      </div>
    </template>
  </UModal>
</template>
