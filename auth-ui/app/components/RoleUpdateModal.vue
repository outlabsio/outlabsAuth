<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { rolesQueries, useUpdateRoleMutation } from '~/queries/roles'

const props = defineProps<{
    roleId: string
}>();

const open = defineModel<boolean>("open", { default: false });

const authStore = useAuthStore();

// Get available permissions from auth config (dynamically loaded from backend)
const availablePermissions = computed(() => authStore.availablePermissions);

// Group permissions by category
const permissionsByCategory = computed(() => {
    const grouped: Record<string, typeof availablePermissions.value> = {};
    availablePermissions.value.forEach((perm) => {
        if (!grouped[perm.category]) {
            grouped[perm.category] = [];
        }
        grouped[perm.category]!.push(perm);
    });
    return grouped;
});

// Fetch existing role data when modal opens
const { data: existingRole, isLoading: isLoadingRole } = useQuery({
    key: computed(() => ['role', props.roleId]),
    query: () => rolesQueries.detail(props.roleId),
    enabled: computed(() => open.value && !!props.roleId)
});

// Form state
const state = reactive({
    name: "",
    display_name: "",
    description: "",
    permissions: [] as string[],
    is_global: true, // SimpleRBAC roles are always global
});

// Pre-populate form when role data loads
watch(existingRole, (role) => {
    if (role) {
        state.name = role.name;
        state.display_name = role.display_name;
        state.description = role.description || "";
        state.permissions = role.permissions || [];
        state.is_global = role.is_global ?? true;
    }
}, { immediate: true });

// Helper to check if all permissions in a category are selected
function isCategoryFullySelected(category: string) {
    const categoryPerms = permissionsByCategory.value[category];
    if (!categoryPerms) return false;
    return categoryPerms.every((perm) =>
        state.permissions.includes(perm.value),
    );
}

// Helper to toggle all permissions in a category
function toggleCategory(category: string) {
    const categoryPerms = permissionsByCategory.value[category];
    if (!categoryPerms) return;

    const isFullySelected = isCategoryFullySelected(category);

    if (isFullySelected) {
        // Remove all permissions from this category
        state.permissions = state.permissions.filter(
            (p) => !categoryPerms.some((cp) => cp.value === p),
        );
    } else {
        // Add all permissions from this category
        const newPerms = categoryPerms.map((p) => p.value);
        state.permissions = [...new Set([...state.permissions, ...newPerms])];
    }
}

// Submit handler
const showPermissionsHelp = ref(false);

// Mutation for updating roles
const { mutate: updateRole, isPending: isSubmitting } = useUpdateRoleMutation()

async function handleSubmit() {
    try {
        console.log('🚀 [RoleUpdateModal] Updating role with payload:', JSON.stringify(state, null, 2))
        await updateRole({
            roleId: props.roleId,
            data: {
                display_name: state.display_name,
                description: state.description,
                permissions: state.permissions,
                is_global: state.is_global
            }
        })
        // Close modal on success
        open.value = false;
    } catch (error) {
        console.error('❌ [RoleUpdateModal] Error updating role:', error)
        // Error handling is done by the mutation
    }
}
</script>

<template>
    <UModal
        v-model:open="open"
        title="Update Role"
        description="Update role details and permissions"
        fullscreen
    >
        <template #body>
            <div v-if="isLoadingRole" class="flex items-center justify-center py-12">
                <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
            </div>

            <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
                <!-- Left Column: Basic Info -->
                <div class="space-y-6">
                    <div class="space-y-4">
                        <h3
                            class="text-lg font-semibold flex items-center gap-2"
                        >
                            <UIcon name="i-lucide-info" class="w-5 h-5" />
                            Basic Information
                        </h3>

                        <!-- Grid layout for Display Name and Name only -->
                        <div class="grid grid-cols-2 gap-4">
                            <div class="space-y-2">
                                <label
                                    class="block text-sm font-medium flex items-center gap-1.5"
                                >
                                    Display Name
                                    <UPopover>
                                        <UButton
                                            icon="i-lucide-help-circle"
                                            color="neutral"
                                            variant="ghost"
                                            size="xs"
                                            class="text-muted hover:text-highlighted"
                                        />
                                        <template #content>
                                            <div class="p-4 max-w-xs space-y-2">
                                                <h4
                                                    class="font-semibold text-sm"
                                                >
                                                    Display Name
                                                </h4>
                                                <p class="text-sm text-muted">
                                                    The human-friendly name
                                                    shown throughout the UI.
                                                    This is what users will see
                                                    when viewing or selecting
                                                    roles.
                                                </p>
                                                <div
                                                    class="text-xs text-muted mt-2"
                                                >
                                                    <p class="font-medium mb-1">
                                                        Examples:
                                                    </p>
                                                    <ul
                                                        class="list-disc list-inside pl-2 space-y-0.5"
                                                    >
                                                        <li>
                                                            "Content Manager"
                                                        </li>
                                                        <li>
                                                            "Department Admin"
                                                        </li>
                                                        <li>
                                                            "Regional
                                                            Supervisor"
                                                        </li>
                                                    </ul>
                                                </div>
                                            </div>
                                        </template>
                                    </UPopover>
                                </label>
                                <UInput
                                    v-model="state.display_name"
                                    placeholder="Content Manager"
                                    icon="i-lucide-shield"
                                />
                            </div>

                            <div class="space-y-2">
                                <label
                                    class="block text-sm font-medium flex items-center gap-1.5"
                                >
                                    Name
                                    <UPopover>
                                        <UButton
                                            icon="i-lucide-help-circle"
                                            color="neutral"
                                            variant="ghost"
                                            size="xs"
                                            class="text-muted hover:text-highlighted"
                                        />
                                        <template #content>
                                            <div class="p-4 max-w-xs space-y-2">
                                                <h4
                                                    class="font-semibold text-sm"
                                                >
                                                    Role Name (Identifier)
                                                </h4>
                                                <p class="text-sm text-muted">
                                                    The technical identifier
                                                    used in code, APIs, and
                                                    database. Cannot be changed after creation.
                                                </p>
                                                <UAlert
                                                    icon="i-lucide-lock"
                                                    color="warning"
                                                    variant="subtle"
                                                    description="Role name cannot be modified to preserve system integrity."
                                                    class="mt-2"
                                                />
                                            </div>
                                        </template>
                                    </UPopover>
                                </label>
                                <UInput
                                    v-model="state.name"
                                    placeholder="content_manager"
                                    icon="i-lucide-tag"
                                    disabled
                                />
                                <p class="text-xs text-muted">
                                    Cannot be changed
                                </p>
                            </div>
                        </div>

                        <!-- Full width description outside the grid -->
                        <div class="space-y-2 w-full">
                            <label class="block text-sm font-medium"
                                >Description</label
                            >
                            <UTextarea
                                v-model="state.description"
                                placeholder="A brief description of what this role can do..."
                                :rows="4"
                                class="w-full"
                            />
                        </div>
                    </div>

                    <!-- Selected permissions count -->
                    <UCard>
                        <div class="flex items-center gap-3">
                            <div class="p-2 bg-primary/10 rounded-lg">
                                <UIcon
                                    name="i-lucide-check-circle"
                                    class="w-6 h-6 text-primary"
                                />
                            </div>
                            <div>
                                <p class="text-2xl font-bold">
                                    {{ state.permissions.length }}
                                </p>
                                <p class="text-sm text-muted">
                                    Permission(s) selected
                                </p>
                            </div>
                        </div>
                    </UCard>
                </div>

                <!-- Right Columns: Permissions (2 columns) -->
                <div class="lg:col-span-2 space-y-6">
                    <div>
                        <div class="flex items-center justify-between mb-4">
                            <h3
                                class="text-lg font-semibold flex items-center gap-2"
                            >
                                <UIcon
                                    name="i-lucide-shield-check"
                                    class="w-5 h-5"
                                />
                                Permissions
                            </h3>
                            <UButton
                                label="Learn about permissions"
                                icon="i-lucide-book-open"
                                color="neutral"
                                variant="ghost"
                                size="xs"
                                @click="showPermissionsHelp = true"
                            />
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div
                                v-for="(
                                    perms, category
                                ) in permissionsByCategory"
                                :key="category"
                            >
                                <UCard>
                                    <!-- Category header with select all -->
                                    <div
                                        class="flex items-center justify-between mb-3"
                                    >
                                        <h4 class="text-sm font-semibold">
                                            {{ category }}
                                        </h4>
                                        <UButton
                                            :label="
                                                isCategoryFullySelected(
                                                    category,
                                                )
                                                    ? 'Clear'
                                                    : 'All'
                                            "
                                            size="xs"
                                            :variant="
                                                isCategoryFullySelected(
                                                    category,
                                                )
                                                    ? 'solid'
                                                    : 'ghost'
                                            "
                                            :color="
                                                isCategoryFullySelected(
                                                    category,
                                                )
                                                    ? 'primary'
                                                    : 'neutral'
                                            "
                                            @click="toggleCategory(category)"
                                        />
                                    </div>

                                    <!-- Permission checkboxes -->
                                    <div class="space-y-2">
                                        <div
                                            v-for="perm in perms"
                                            :key="perm.value"
                                        >
                                            <UCheckbox
                                                :model-value="
                                                    state.permissions.includes(
                                                        perm.value,
                                                    )
                                                "
                                                @update:model-value="
                                                    (checked) => {
                                                        if (checked) {
                                                            state.permissions =
                                                                [
                                                                    ...state.permissions,
                                                                    perm.value,
                                                                ];
                                                        } else {
                                                            state.permissions =
                                                                state.permissions.filter(
                                                                    (p) =>
                                                                        p !==
                                                                        perm.value,
                                                                );
                                                        }
                                                    }
                                                "
                                                :label="perm.label"
                                            />
                                        </div>
                                    </div>
                                </UCard>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex items-center justify-between w-full">
                <div class="text-sm text-muted">
                    Only display name, description, and permissions can be updated
                </div>
                <div class="flex justify-end gap-2">
                    <UButton
                        label="Cancel"
                        color="neutral"
                        variant="outline"
                        @click="open = false"
                        :disabled="isSubmitting"
                    />
                    <UButton
                        label="Update Role"
                        icon="i-lucide-save"
                        :loading="isSubmitting"
                        @click="handleSubmit"
                    />
                </div>
            </div>
        </template>
    </UModal>

    <!-- Permissions Help Slideover (same as create modal) -->
    <USlideover
        v-model:open="showPermissionsHelp"
        title="Understanding Permissions"
    >
        <template #body>
            <div class="space-y-6">
                <div>
                    <h4 class="font-semibold mb-2">Permission Format</h4>
                    <p class="text-sm text-muted mb-3">
                        Permissions follow the pattern:
                        <code class="px-1.5 py-0.5 bg-elevated rounded text-xs"
                            >resource:action</code
                        >
                    </p>
                    <div class="space-y-2 text-sm">
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-arrow-right"
                                class="w-4 h-4 mt-0.5 text-primary"
                            />
                            <div>
                                <code
                                    class="text-xs bg-elevated px-1.5 py-0.5 rounded"
                                    >user:read</code
                                >
                                <span class="text-muted ml-2"
                                    >Read user information</span
                                >
                            </div>
                        </div>
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-arrow-right"
                                class="w-4 h-4 mt-0.5 text-primary"
                            />
                            <div>
                                <code
                                    class="text-xs bg-elevated px-1.5 py-0.5 rounded"
                                    >user:create</code
                                >
                                <span class="text-muted ml-2"
                                    >Create new users</span
                                >
                            </div>
                        </div>
                    </div>
                </div>

                <UDivider />

                <div>
                    <h4 class="font-semibold mb-2">
                        Tree Permissions (EnterpriseRBAC)
                    </h4>
                    <p class="text-sm text-muted mb-3">
                        Tree permissions allow hierarchical access control
                        across entity trees.
                    </p>
                    <UAlert
                        icon="i-lucide-lightbulb"
                        color="info"
                        variant="subtle"
                        title="What are tree permissions?"
                        description="Permissions ending in '_tree' grant access to the entity and all its descendants in the hierarchy."
                    />
                    <div class="mt-3 space-y-2 text-sm">
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-tree-deciduous"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <div>
                                <code
                                    class="text-xs bg-elevated px-1.5 py-0.5 rounded"
                                    >user:read_tree</code
                                >
                                <p class="text-muted text-xs mt-1">
                                    Read users in this entity AND all child
                                    entities
                                </p>
                            </div>
                        </div>
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-tree-deciduous"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <div>
                                <code
                                    class="text-xs bg-elevated px-1.5 py-0.5 rounded"
                                    >entity:manage_tree</code
                                >
                                <p class="text-muted text-xs mt-1">
                                    Manage this entity AND all descendant
                                    entities
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                <UDivider />

                <div>
                    <h4 class="font-semibold mb-2">Permission Categories</h4>
                    <div class="space-y-3 text-sm">
                        <div>
                            <p class="font-medium mb-1 flex items-center gap-2">
                                <UIcon
                                    name="i-lucide-users"
                                    class="w-4 h-4 text-primary"
                                />
                                Users
                            </p>
                            <p class="text-muted text-xs">
                                Manage user accounts, profiles, and
                                authentication
                            </p>
                        </div>
                        <div>
                            <p class="font-medium mb-1 flex items-center gap-2">
                                <UIcon
                                    name="i-lucide-shield"
                                    class="w-4 h-4 text-primary"
                                />
                                Roles
                            </p>
                            <p class="text-muted text-xs">
                                Create and modify role definitions and
                                assignments
                            </p>
                        </div>
                        <div>
                            <p class="font-medium mb-1 flex items-center gap-2">
                                <UIcon
                                    name="i-lucide-building"
                                    class="w-4 h-4 text-primary"
                                />
                                Entities
                            </p>
                            <p class="text-muted text-xs">
                                Manage organizational structure (departments,
                                teams, etc.)
                            </p>
                        </div>
                        <div>
                            <p class="font-medium mb-1 flex items-center gap-2">
                                <UIcon
                                    name="i-lucide-key"
                                    class="w-4 h-4 text-primary"
                                />
                                API Keys
                            </p>
                            <p class="text-muted text-xs">
                                Create and manage programmatic access keys
                            </p>
                        </div>
                    </div>
                </div>

                <UDivider />

                <div>
                    <h4 class="font-semibold mb-2">Best Practices</h4>
                    <div class="space-y-2 text-sm text-muted">
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <span
                                >Grant minimum permissions needed (principle of
                                least privilege)</span
                            >
                        </div>
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <span
                                >Use tree permissions for managers overseeing
                                teams</span
                            >
                        </div>
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <span
                                >Group related permissions into meaningful
                                roles</span
                            >
                        </div>
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <span
                                >Review and audit role permissions
                                regularly</span
                            >
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </USlideover>
</template>
