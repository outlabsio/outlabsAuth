<script setup lang="ts">
import { useCreateRoleMutation } from "~/queries/roles";
import { useQuery } from "@pinia/colada";
import { entitiesQueries } from "~/queries/entities";

const open = defineModel<boolean>("open", { default: false });

const authStore = useAuthStore();

// Check if EnterpriseRBAC mode (for scope selection)
const isEnterpriseRBAC = computed(() => authStore.isEnterpriseRBAC);

// Fetch root entities for scope selection (EnterpriseRBAC only)
const { data: entitiesData } = useQuery(
    entitiesQueries.list({ root_only: true }, { page: 1, limit: 100 }),
);

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

// Root entity options for scope selection
const rootEntityOptions = computed(() => {
    const entities = entitiesData.value?.items || [];
    return entities.map((e) => ({
        label: e.display_name || e.name,
        value: e.id,
    }));
});

// Form state
const state = reactive({
    name: "",
    display_name: "",
    description: "",
    permissions: [] as string[],
    is_global: true,
    // EnterpriseRBAC scope
    scope_type: "global" as "global" | "organization",
    root_entity_id: undefined as string | undefined,
});

// Sync scope_type with is_global
watch(
    () => state.scope_type,
    (scopeType) => {
        state.is_global = scopeType === "global";
        if (scopeType === "global") {
            state.root_entity_id = undefined;
        }
    },
);

// Auto-generate name from display_name
watch(
    () => state.display_name,
    (newDisplayName) => {
        if (newDisplayName && !state.name) {
            state.name = newDisplayName
                .toLowerCase()
                .replace(/\s+/g, "_")
                .replace(/[^a-z0-9_-]/g, "");
        }
    },
);

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

// Mutation for creating roles
const { mutate: createRole, isLoading: isSubmitting } = useCreateRoleMutation();

async function handleSubmit() {
    try {
        // Build payload
        const payload = {
            name: state.name,
            display_name: state.display_name,
            description: state.description,
            permissions: state.permissions,
            is_global: state.is_global,
            // Include root_entity_id only for organization-scoped roles
            ...(state.scope_type === "organization" && state.root_entity_id
                ? { root_entity_id: state.root_entity_id }
                : {}),
        };

        console.log(
            "🚀 [RoleCreateModal] Submitting role with payload:",
            JSON.stringify(payload, null, 2),
        );
        await createRole(payload);
        // Close modal and reset form on success
        open.value = false;
        Object.assign(state, {
            name: "",
            display_name: "",
            description: "",
            permissions: [],
            is_global: true,
            scope_type: "global",
            root_entity_id: undefined,
        });
    } catch (error) {
        console.error("❌ [RoleCreateModal] Error creating role:", error);
        // Error handling is done by the mutation
    }
}
</script>

<template>
    <UModal
        v-model:open="open"
        title="Create Role"
        description="Create a new role with specific permissions"
        fullscreen
    >
        <template #body>
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
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
                                                    database. Must be unique,
                                                    lowercase, and use
                                                    underscores or hyphens only.
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
                                                            "content_manager"
                                                        </li>
                                                        <li>"dept-admin"</li>
                                                        <li>
                                                            "regional_supervisor"
                                                        </li>
                                                    </ul>
                                                </div>
                                                <UAlert
                                                    icon="i-lucide-lightbulb"
                                                    color="info"
                                                    variant="subtle"
                                                    description="Auto-generated from Display Name, but you can customize it."
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
                                />
                                <p class="text-xs text-muted">
                                    Lowercase, no spaces
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

                    <!-- Role Scope (EnterpriseRBAC only) -->
                    <div v-if="isEnterpriseRBAC" class="space-y-4">
                        <h3
                            class="text-lg font-semibold flex items-center gap-2"
                        >
                            <UIcon name="i-lucide-target" class="w-5 h-5" />
                            Role Scope
                            <UPopover>
                                <UButton
                                    icon="i-lucide-help-circle"
                                    color="neutral"
                                    variant="ghost"
                                    size="xs"
                                />
                                <template #content>
                                    <div class="p-4 max-w-sm space-y-2">
                                        <h4 class="font-semibold text-sm">
                                            Role Scope
                                        </h4>
                                        <p class="text-sm text-muted">
                                            Determines where this role can be
                                            assigned.
                                        </p>
                                        <div
                                            class="space-y-2 mt-2 text-xs text-muted"
                                        >
                                            <div>
                                                <p class="font-medium">
                                                    Global
                                                </p>
                                                <p>
                                                    Available system-wide, can
                                                    be assigned in any
                                                    organization.
                                                </p>
                                            </div>
                                            <div>
                                                <p class="font-medium">
                                                    Organization-specific
                                                </p>
                                                <p>
                                                    Only available within a
                                                    specific organization's
                                                    hierarchy.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </template>
                            </UPopover>
                        </h3>

                        <div class="grid grid-cols-2 gap-4">
                            <UCard
                                :class="[
                                    'cursor-pointer transition-all border-2',
                                    state.scope_type === 'global'
                                        ? 'border-primary bg-primary/5'
                                        : 'border-default hover:border-primary/50',
                                ]"
                                @click="state.scope_type = 'global'"
                            >
                                <div
                                    class="flex flex-col items-center text-center space-y-2 p-2"
                                >
                                    <UIcon
                                        name="i-lucide-globe"
                                        class="w-8 h-8"
                                        :class="
                                            state.scope_type === 'global'
                                                ? 'text-primary'
                                                : 'text-muted'
                                        "
                                    />
                                    <div>
                                        <p class="font-semibold text-sm">
                                            Global
                                        </p>
                                        <p class="text-xs text-muted">
                                            System-wide
                                        </p>
                                    </div>
                                </div>
                            </UCard>

                            <UCard
                                :class="[
                                    'cursor-pointer transition-all border-2',
                                    state.scope_type === 'organization'
                                        ? 'border-primary bg-primary/5'
                                        : 'border-default hover:border-primary/50',
                                ]"
                                @click="state.scope_type = 'organization'"
                            >
                                <div
                                    class="flex flex-col items-center text-center space-y-2 p-2"
                                >
                                    <UIcon
                                        name="i-lucide-building-2"
                                        class="w-8 h-8"
                                        :class="
                                            state.scope_type === 'organization'
                                                ? 'text-primary'
                                                : 'text-muted'
                                        "
                                    />
                                    <div>
                                        <p class="font-semibold text-sm">
                                            Organization
                                        </p>
                                        <p class="text-xs text-muted">
                                            Scoped to one org
                                        </p>
                                    </div>
                                </div>
                            </UCard>
                        </div>

                        <!-- Organization selector (when scope_type is 'organization') -->
                        <div
                            v-if="state.scope_type === 'organization'"
                            class="space-y-2"
                        >
                            <label class="block text-sm font-medium">
                                Select Organization
                            </label>
                            <USelect
                                v-model="state.root_entity_id"
                                :items="rootEntityOptions"
                                placeholder="Choose an organization..."
                                icon="i-lucide-building-2"
                            />
                            <p class="text-xs text-muted">
                                This role will only be available within the
                                selected organization's hierarchy.
                            </p>
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
                    All fields are required except description
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
                        label="Create Role"
                        icon="i-lucide-shield"
                        :loading="isSubmitting"
                        @click="handleSubmit"
                    />
                </div>
            </div>
        </template>
    </UModal>

    <!-- Permissions Help Slideover -->
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

                <USeparator />

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

                <USeparator />

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

                <USeparator />

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
