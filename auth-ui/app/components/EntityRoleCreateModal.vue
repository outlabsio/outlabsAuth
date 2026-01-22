<script setup lang="ts">
import { useCreateRoleMutation } from "~/queries/roles";
import type { RoleScope } from "~/types/role";

const props = defineProps<{
    entityId: string;
    entityName: string;
}>();

const open = defineModel<boolean>("open", { default: false });

// Validate entityId is provided
const isValidEntity = computed(
    () => !!props.entityId && props.entityId.length > 0,
);

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

// Form state
const state = reactive({
    name: "",
    display_name: "",
    description: "",
    permissions: [] as string[],
    scope: "entity_only" as RoleScope,
    is_auto_assigned: false,
});

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

// Reset form when modal opens
watch(open, (isOpen) => {
    if (isOpen) {
        Object.assign(state, {
            name: "",
            display_name: "",
            description: "",
            permissions: [],
            scope: "entity_only",
            is_auto_assigned: false,
        });
    }
});

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

// Mutation for creating roles
const { mutate: createRole, isLoading: isSubmitting } = useCreateRoleMutation();

// Help slideover state
const showPermissionsHelp = ref(false);

async function handleSubmit() {
    // Validate entityId before submission
    if (!isValidEntity.value) {
        console.error(
            "❌ [EntityRoleCreateModal] Cannot create role: entityId is missing",
        );
        return;
    }

    try {
        // Build payload for entity-local role
        const payload = {
            name: state.name,
            display_name: state.display_name,
            description: state.description,
            permissions: state.permissions,
            is_global: false,
            // Entity-local role fields
            scope_entity_id: props.entityId,
            scope: state.scope,
            is_auto_assigned: state.is_auto_assigned,
        };

        console.log(
            "🚀 [EntityRoleCreateModal] Creating entity-local role:",
            JSON.stringify(payload, null, 2),
        );
        await createRole(payload);
        // Close modal on success
        open.value = false;
    } catch (error) {
        console.error("❌ [EntityRoleCreateModal] Error creating role:", error);
        // Error handling is done by the mutation
    }
}
</script>

<template>
    <UModal
        v-model:open="open"
        title="Create Entity Role"
        :description="`Create a role scoped to ${entityName}`"
        fullscreen
    >
        <template #body>
            <!-- Error state when entityId is missing -->
            <div
                v-if="!isValidEntity"
                class="flex flex-col items-center justify-center py-12 space-y-4"
            >
                <UIcon
                    name="i-lucide-alert-triangle"
                    class="w-16 h-16 text-error"
                />
                <h3 class="text-lg font-semibold">Missing Entity Context</h3>
                <p class="text-muted text-center max-w-md">
                    Cannot create an entity-local role without selecting an
                    entity first. Please select an entity from the tree and try
                    again.
                </p>
                <UButton label="Close" @click="open = false" />
            </div>

            <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
                <!-- Left Column: Basic Info -->
                <div class="space-y-6">
                    <!-- Entity Context Banner -->
                    <UAlert
                        icon="i-lucide-building"
                        color="info"
                        variant="subtle"
                        :title="`Role for: ${entityName}`"
                        description="This role will only be available within this entity's context."
                    />

                    <div class="space-y-4">
                        <h3
                            class="text-lg font-semibold flex items-center gap-2"
                        >
                            <UIcon name="i-lucide-info" class="w-5 h-5" />
                            Basic Information
                        </h3>

                        <!-- Grid layout for Display Name and Name -->
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
                                                    shown in the UI.
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
                                                        <li>"Team Lead"</li>
                                                        <li>
                                                            "Content Reviewer"
                                                        </li>
                                                        <li>
                                                            "Budget Approver"
                                                        </li>
                                                    </ul>
                                                </div>
                                            </div>
                                        </template>
                                    </UPopover>
                                </label>
                                <UInput
                                    v-model="state.display_name"
                                    placeholder="Team Lead"
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
                                                    Technical identifier used in
                                                    code and APIs. Must be
                                                    unique, lowercase.
                                                </p>
                                                <UAlert
                                                    icon="i-lucide-lightbulb"
                                                    color="info"
                                                    variant="subtle"
                                                    description="Auto-generated from Display Name."
                                                    class="mt-2"
                                                />
                                            </div>
                                        </template>
                                    </UPopover>
                                </label>
                                <UInput
                                    v-model="state.name"
                                    placeholder="team_lead"
                                    icon="i-lucide-tag"
                                />
                                <p class="text-xs text-muted">
                                    Lowercase, no spaces
                                </p>
                            </div>
                        </div>

                        <!-- Full width description -->
                        <div class="space-y-2 w-full">
                            <label class="block text-sm font-medium"
                                >Description</label
                            >
                            <UTextarea
                                v-model="state.description"
                                placeholder="A brief description of what this role can do..."
                                :rows="3"
                                class="w-full"
                            />
                        </div>
                    </div>

                    <!-- Role Scope Section -->
                    <div class="space-y-4">
                        <h3
                            class="text-lg font-semibold flex items-center gap-2"
                        >
                            <UIcon name="i-lucide-target" class="w-5 h-5" />
                            Permission Scope
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
                                            Permission Scope
                                        </h4>
                                        <p class="text-sm text-muted">
                                            Controls where this role's
                                            permissions apply.
                                        </p>
                                        <div
                                            class="space-y-2 mt-2 text-xs text-muted"
                                        >
                                            <div>
                                                <p class="font-medium">
                                                    This Entity Only
                                                </p>
                                                <p>
                                                    Permissions only work within
                                                    this specific entity.
                                                </p>
                                            </div>
                                            <div>
                                                <p class="font-medium">
                                                    Entity + Children
                                                </p>
                                                <p>
                                                    Permissions apply to this
                                                    entity and all its
                                                    descendants.
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
                                    state.scope === 'entity_only'
                                        ? 'border-primary bg-primary/5'
                                        : 'border-default hover:border-primary/50',
                                ]"
                                @click="state.scope = 'entity_only'"
                            >
                                <div
                                    class="flex flex-col items-center text-center space-y-2 p-2"
                                >
                                    <UIcon
                                        name="i-lucide-box"
                                        class="w-8 h-8"
                                        :class="
                                            state.scope === 'entity_only'
                                                ? 'text-primary'
                                                : 'text-muted'
                                        "
                                    />
                                    <div>
                                        <p class="font-semibold text-sm">
                                            This Entity Only
                                        </p>
                                        <p class="text-xs text-muted">
                                            Permissions stay here
                                        </p>
                                    </div>
                                </div>
                            </UCard>

                            <UCard
                                :class="[
                                    'cursor-pointer transition-all border-2',
                                    state.scope === 'hierarchy'
                                        ? 'border-primary bg-primary/5'
                                        : 'border-default hover:border-primary/50',
                                ]"
                                @click="state.scope = 'hierarchy'"
                            >
                                <div
                                    class="flex flex-col items-center text-center space-y-2 p-2"
                                >
                                    <UIcon
                                        name="i-lucide-git-branch"
                                        class="w-8 h-8"
                                        :class="
                                            state.scope === 'hierarchy'
                                                ? 'text-primary'
                                                : 'text-muted'
                                        "
                                    />
                                    <div>
                                        <p class="font-semibold text-sm">
                                            Entity + Children
                                        </p>
                                        <p class="text-xs text-muted">
                                            Permissions inherit down
                                        </p>
                                    </div>
                                </div>
                            </UCard>
                        </div>

                        <!-- Scope explanation -->
                        <UAlert
                            v-if="state.scope === 'entity_only'"
                            icon="i-lucide-info"
                            color="neutral"
                            variant="subtle"
                            title="Entity-Only Scope"
                            description="Members with this role will only have these permissions when operating within this specific entity. Permissions will not apply in child entities."
                        />
                        <UAlert
                            v-else
                            icon="i-lucide-info"
                            color="neutral"
                            variant="subtle"
                            title="Hierarchy Scope"
                            description="Members with this role will have these permissions in this entity AND all of its child entities. The role will also appear in child entities' 'Inherited Roles' section."
                        />
                    </div>

                    <!-- Auto-Assignment Section -->
                    <div class="space-y-4">
                        <h3
                            class="text-lg font-semibold flex items-center gap-2"
                        >
                            <UIcon name="i-lucide-zap" class="w-5 h-5" />
                            Auto-Assignment
                        </h3>

                        <UCard>
                            <div class="flex items-start gap-3">
                                <USwitch
                                    v-model="state.is_auto_assigned"
                                    size="lg"
                                />
                                <div class="space-y-1">
                                    <p class="font-medium text-sm">
                                        Auto-assign to new members
                                    </p>
                                    <p class="text-xs text-muted">
                                        When enabled, this role will
                                        automatically be assigned to anyone who
                                        joins this entity.
                                    </p>
                                </div>
                            </div>
                        </UCard>

                        <UAlert
                            v-if="state.is_auto_assigned"
                            icon="i-lucide-zap"
                            color="warning"
                            variant="subtle"
                            title="Auto-Assignment Active"
                            description="New members added to this entity will automatically receive this role. Make sure the permissions are appropriate for all members."
                        />
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
            <div
                v-if="isValidEntity"
                class="flex items-center justify-between w-full"
            >
                <div class="text-sm text-muted">
                    Role will be scoped to
                    <span class="font-medium">{{ entityName }}</span>
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
                                    >post:create</code
                                >
                                <span class="text-muted ml-2"
                                    >Create posts</span
                                >
                            </div>
                        </div>
                    </div>
                </div>

                <USeparator />

                <div>
                    <h4 class="font-semibold mb-2">Entity-Local Roles</h4>
                    <p class="text-sm text-muted mb-3">
                        Entity-local roles are scoped to a specific entity and
                        its context.
                    </p>
                    <div class="space-y-3 text-sm">
                        <div class="p-3 bg-elevated rounded-lg">
                            <p class="font-medium mb-1 flex items-center gap-2">
                                <UIcon
                                    name="i-lucide-box"
                                    class="w-4 h-4 text-primary"
                                />
                                Entity-Only Scope
                            </p>
                            <p class="text-muted text-xs">
                                Permissions only apply when the user is acting
                                within this specific entity. They won't have
                                these permissions in child entities.
                            </p>
                        </div>
                        <div class="p-3 bg-elevated rounded-lg">
                            <p class="font-medium mb-1 flex items-center gap-2">
                                <UIcon
                                    name="i-lucide-git-branch"
                                    class="w-4 h-4 text-primary"
                                />
                                Hierarchy Scope
                            </p>
                            <p class="text-muted text-xs">
                                Permissions apply in this entity AND all
                                descendant entities. This is useful for roles
                                like "Department Manager" who need access to
                                sub-teams.
                            </p>
                        </div>
                    </div>
                </div>

                <USeparator />

                <div>
                    <h4 class="font-semibold mb-2">Auto-Assignment</h4>
                    <p class="text-sm text-muted mb-3">
                        When enabled, new members joining this entity
                        automatically receive this role.
                    </p>
                    <UAlert
                        icon="i-lucide-lightbulb"
                        color="info"
                        variant="subtle"
                        title="Example Use Cases"
                    >
                        <template #description>
                            <ul
                                class="list-disc list-inside text-xs mt-1 space-y-1"
                            >
                                <li>
                                    A "Team Member" role that all team members
                                    should have
                                </li>
                                <li>
                                    A "Basic Access" role for department
                                    defaults
                                </li>
                                <li>
                                    A "Viewer" role for read-only access to
                                    entity resources
                                </li>
                            </ul>
                        </template>
                    </UAlert>
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
                                >Use "Entity-Only" scope for roles specific to
                                this level</span
                            >
                        </div>
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <span
                                >Use "Hierarchy" scope for management roles that
                                oversee children</span
                            >
                        </div>
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <span
                                >Be careful with auto-assigned roles - they
                                affect all new members</span
                            >
                        </div>
                        <div class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check"
                                class="w-4 h-4 mt-0.5 text-success"
                            />
                            <span
                                >Grant minimum permissions needed (least
                                privilege)</span
                            >
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </USlideover>
</template>
