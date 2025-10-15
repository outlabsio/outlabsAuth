<script setup lang="ts">
import type { User } from "~/stores/users.store";
import type { Permission, PermissionGroup } from "~/stores/permissions.store";
import { upperFirst } from "scule";

const props = defineProps<{
  open: boolean;
  user: User | null;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  save: [permissions: { id: string; granted: boolean }[]];
}>();

// Local reactive state
const searchQuery = ref("");
const userPermissions = ref<{ id: string; granted: boolean }[]>([]);
const loading = ref(false);

// Get permissions store for data
const permissionsStore = usePermissionsStore();

// Track assigned permissions
const assignedPermissions = ref<string[]>([]);

// Add toggle for active permissions only
const showOnlyActive = ref(false);

// Fetch permissions on component mount
onMounted(() => {
  if (!permissionsStore.permissions.length) {
    permissionsStore.fetchPermissions(0, 100); // Fetch all permissions
  }
});

// Watch for user changes and load permissions
watch(
  () => props.user,
  (newUser) => {
    if (newUser) {
      loadUserPermissions(newUser.id);
    } else {
      assignedPermissions.value = [];
    }
  },
  { immediate: true }
);

// Load permissions for the user
const loadUserPermissions = (userId: string) => {
  // In a real app, fetch assigned permissions from an API
  // For demo, we'll use random assignment
  loading.value = true;

  // Simulate API call
  setTimeout(() => {
    // Randomly assign some permissions to the user
    assignedPermissions.value = permissionsStore.permissions
      .filter(() => Math.random() > 0.6)
      .map((p) => p._id || "")
      .filter((id) => id); // Filter out empty IDs

    loading.value = false;
  }, 500);
};

// Toggle permission status
const togglePermission = (permissionId: string) => {
  const index = assignedPermissions.value.indexOf(permissionId);
  if (index > -1) {
    assignedPermissions.value.splice(index, 1);
  } else {
    assignedPermissions.value.push(permissionId);
  }
};

// Check if permission is granted
const isPermissionGranted = (permissionId: string) => {
  return assignedPermissions.value.includes(permissionId);
};

// Filter permissions based on search query and active toggle
const filteredPermissions = computed(() => {
  if (!searchQuery.value && !showOnlyActive.value) return permissionsStore.permissionsByResource;

  const search = searchQuery.value.toLowerCase();
  const filteredGroups: PermissionGroup[] = [];

  permissionsStore.permissionsByResource.forEach((group) => {
    // Filter permissions in the group
    const filteredPerms = group.permissions.filter((p) => {
      // First check for active only filter
      if (showOnlyActive.value && p._id && !assignedPermissions.value.includes(p._id)) {
        return false;
      }

      // Then apply search filter if needed
      if (!searchQuery.value) return true;

      return p.name.toLowerCase().includes(search) || p.description.toLowerCase().includes(search) || group.resource.toLowerCase().includes(search);
    });

    // If any permission matches, add the group with matched permissions
    if (filteredPerms.length > 0) {
      filteredGroups.push({
        resource: group.resource,
        permissions: filteredPerms,
      });
    }
  });

  return filteredGroups;
});

// Handler for granting all permissions in a resource
const grantAllInResource = (resource: string) => {
  const group = permissionsStore.permissionsByResource.find((g) => g.resource === resource);
  if (!group) return;

  group.permissions.forEach((perm) => {
    if (perm._id && !assignedPermissions.value.includes(perm._id)) {
      assignedPermissions.value.push(perm._id);
    }
  });
};

// Handler for revoking all permissions in a resource
const revokeAllInResource = (resource: string) => {
  const group = permissionsStore.permissionsByResource.find((g) => g.resource === resource);
  if (!group) return;

  group.permissions.forEach((perm) => {
    if (perm._id) {
      const index = assignedPermissions.value.indexOf(perm._id);
      if (index > -1) {
        assignedPermissions.value.splice(index, 1);
      }
    }
  });
};

// Check if all permissions in a resource are granted
const isAllResourceGranted = (resource: string) => {
  const group = permissionsStore.permissionsByResource.find((g) => g.resource === resource);
  if (!group || !group.permissions.length) return false;

  return group.permissions.every((perm) => perm._id && assignedPermissions.value.includes(perm._id));
};

// Check if some permissions in a resource are granted
const isSomeResourceGranted = (resource: string) => {
  const group = permissionsStore.permissionsByResource.find((g) => g.resource === resource);
  if (!group || !group.permissions.length) return false;

  return group.permissions.some((perm) => perm._id && assignedPermissions.value.includes(perm._id));
};

// Handler to save permissions
const savePermissions = async () => {
  loading.value = true;
  try {
    // Format permissions for backend
    const permissionsPayload = assignedPermissions.value.map((id) => ({
      id,
      granted: true,
    }));

    // Mock successful save
    await new Promise((resolve) => setTimeout(resolve, 800));

    // Use toast notification
    useToast().add({
      title: "Success",
      description: "User permissions updated successfully",
      color: "success",
    });

    // Emit events to parent component
    emit("save", permissionsPayload);
    emit("update:open", false);
  } catch (err) {
    useToast().add({
      title: "Error",
      description: "Failed to update user permissions",
      color: "error",
    });
    console.error("Failed to update permissions:", err);
  } finally {
    loading.value = false;
  }
};

// Close modal handler
const closeModal = () => {
  emit("update:open", false);
};

// Get resource icon based on resource name
const getResourceIcon = (resource: string) => {
  const icons: Record<string, string> = {
    users: "i-lucide-users",
    content: "i-lucide-file-text",
    settings: "i-lucide-settings",
    analytics: "i-lucide-bar-chart",
    billing: "i-lucide-credit-card",
    products: "i-lucide-package",
    orders: "i-lucide-shopping-bag",
    reports: "i-lucide-pie-chart",
  };

  return icons[resource.toLowerCase()] || "i-lucide-key";
};

// Get color class for resource
const getResourceColor = (resource: string): { color: string; bgColor: string } => {
  const colors: Record<string, { color: string; bgColor: string }> = {
    users: { color: "text-indigo-600", bgColor: "bg-indigo-100" },
    content: { color: "text-blue-600", bgColor: "bg-blue-100" },
    settings: { color: "text-amber-600", bgColor: "bg-amber-100" },
    analytics: { color: "text-emerald-600", bgColor: "bg-emerald-100" },
    billing: { color: "text-purple-600", bgColor: "bg-purple-100" },
    products: { color: "text-cyan-600", bgColor: "bg-cyan-100" },
    orders: { color: "text-orange-600", bgColor: "bg-orange-100" },
    reports: { color: "text-teal-600", bgColor: "bg-teal-100" },
  };

  return colors[resource.toLowerCase()] || { color: "text-primary", bgColor: "bg-primary/10" };
};

// Format permission names for display (remove resource: prefix)
const formatPermissionName = (name: string, resource: string) => {
  if (name.startsWith(`${resource}:`)) {
    const action = name.split(":")[1];
    return upperFirst(action);
  }
  return name;
};

// No results state when filtering
const hasNoResults = computed(() => {
  if (!searchQuery.value) return false;
  return filteredPermissions.value.length === 0;
});

// Generate a safe avatar URL
const avatarUrl = computed(() => {
  if (!props.user) return "";
  const nameValue = props.user.name || props.user.email || "";
  return `https://avatars.dicebear.com/api/initials/${encodeURIComponent(String(nameValue))}.svg`;
});
</script>

<template>
  <UModal :open="open" @update:open="closeModal" size="2xl">
    <template #header>
      <div class="flex items-center gap-2">
        <UAvatar v-if="user" :src="avatarUrl" size="sm" />
        <div>
          <h3 class="text-xl font-semibold">Manage Permissions</h3>
          <p class="text-sm text-gray-500">{{ user?.name || user?.email }}</p>
        </div>
      </div>
    </template>

    <template #body>
      <div class="space-y-6">
        <!-- Search and Filters -->
        <div class="mb-6">
          <div class="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
            <UInput v-model="searchQuery" placeholder="Search permissions..." icon="i-lucide-search" trailing class="w-full sm:w-2/3" size="sm" />
            <div class="flex items-center gap-2">
              <USwitch v-model="showOnlyActive" size="sm" color="success" />
              <span class="text-sm">Only show active permissions</span>
            </div>
          </div>
        </div>

        <!-- Loading state -->
        <div v-if="loading || permissionsStore.isLoading" class="py-8 flex justify-center">
          <UIcon name="i-lucide-loader-2" class="animate-spin h-8 w-8 text-gray-400" />
        </div>

        <!-- Permissions list -->
        <div v-else class="space-y-6 max-h-[60vh] overflow-y-auto pr-1 permission-container">
          <div v-for="group in filteredPermissions" :key="group.resource" class="space-y-3">
            <!-- Only show groups with permissions -->
            <template v-if="group.permissions.length > 0">
              <!-- Category Header -->
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <UIcon :name="getResourceIcon(group.resource)" :class="[getResourceColor(group.resource).color, getResourceColor(group.resource).bgColor, 'p-2 rounded-md']" />
                  <h3 class="font-medium" :class="getResourceColor(group.resource).color">
                    {{ upperFirst(group.resource) }}
                  </h3>
                </div>

                <!-- Select/Deselect All -->
                <div class="flex items-center gap-2">
                  <UButton v-if="!isAllResourceGranted(group.resource)" size="xs" color="neutral" variant="ghost" @click="grantAllInResource(group.resource)"> Grant All </UButton>
                  <UButton v-if="isSomeResourceGranted(group.resource)" size="xs" color="neutral" variant="ghost" @click="revokeAllInResource(group.resource)"> Revoke All </UButton>
                </div>
              </div>

              <!-- Permissions in this resource -->
              <div class="grid grid-cols-1 lg:grid-cols-2 gap-3 pl-2">
                <div
                  v-for="permission in group.permissions"
                  :key="permission._id"
                  class="flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors"
                  :class="{
                    'bg-success-500 dark:bg-success-800/10 border-success-500 dark:border-success-800 text-white': permission._id && isPermissionGranted(permission._id),
                    'border-(--ui-border) hover:bg-(--ui-hover)': !(permission._id && isPermissionGranted(permission._id)),
                  }"
                  @click="permission._id && togglePermission(permission._id)"
                >
                  <div class="flex items-center gap-2 w-full">
                    <div>
                      <p class="font-medium" :class="{ 'text-white': permission._id && isPermissionGranted(permission._id) }">{{ formatPermissionName(permission.name, group.resource) }}</p>
                      <p class="text-xs" :class="{ 'text-white/90': permission._id && isPermissionGranted(permission._id), 'text-gray-500': !(permission._id && isPermissionGranted(permission._id)) }">
                        {{ permission.description }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <!-- No results state -->
          <div v-if="hasNoResults" class="py-8 text-center text-gray-500">
            <UIcon name="i-lucide-search-x" class="mx-auto h-12 w-12 mb-3 opacity-50" />
            <p class="text-lg">No permissions match your search</p>
            <p class="text-sm">Try a different search term or clear the search</p>
            <UButton class="mt-4" variant="soft" @click="searchQuery = ''">Clear Search</UButton>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-between w-full">
        <UButton color="neutral" variant="soft" @click="closeModal">Cancel</UButton>
        <UButton type="button" color="primary" @click="savePermissions" :loading="loading"> Save Permissions </UButton>
      </div>
    </template>
  </UModal>
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
