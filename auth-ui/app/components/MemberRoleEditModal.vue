<script setup lang="ts">
import { useQuery } from "@pinia/colada";
import { rolesQueries } from "~/queries/roles";
import { useUpdateMemberRolesMutation } from "~/queries/memberships";
import type { EntityMember } from "~/types/membership";
import type { Role } from "~/types/role";
import type { UiColor } from "~/types/ui";

const props = defineProps<{
    entityId: string;
    member: EntityMember;
}>();

const open = defineModel<boolean>("open", { default: false });

// Fetch roles available for this entity
const { data: rolesData, isLoading: isLoadingRoles } = useQuery(() => ({
    ...rolesQueries.list({ for_entity_id: props.entityId }, { limit: 100 }),
    enabled: open.value && !!props.entityId,
}));

// Get all available roles
const availableRoles = computed(() => rolesData.value?.items || []);

// Group roles by type for display
const rolesByType = computed(() => {
    const roles = availableRoles.value;
    const grouped = {
        entityLocal: [] as Role[],
        inherited: [] as Role[],
        global: [] as Role[],
    };

    for (const role of roles) {
        if (role.is_global) {
            grouped.global.push(role);
        } else if (role.scope_entity_id === props.entityId) {
            grouped.entityLocal.push(role);
        } else if (role.scope_entity_id) {
            // Entity-local from an ancestor (inherited)
            grouped.inherited.push(role);
        } else {
            // Org-scoped (root_entity_id set but no scope_entity_id)
            grouped.global.push(role);
        }
    }

    return grouped;
});

// Selected role IDs (start with current member roles)
const selectedRoleIds = ref<string[]>([]);

// Initialize selection when modal opens or member changes
watch(
    [open, () => props.member],
    ([isOpen, member]) => {
        if (isOpen && member) {
            selectedRoleIds.value = member.roles.map((r) => r.id);
        }
    },
    { immediate: true }
);

// Check if a role is selected
function isRoleSelected(roleId: string): boolean {
    return selectedRoleIds.value.includes(roleId);
}

// Toggle role selection
function toggleRole(roleId: string) {
    if (isRoleSelected(roleId)) {
        selectedRoleIds.value = selectedRoleIds.value.filter(
            (id) => id !== roleId
        );
    } else {
        selectedRoleIds.value = [...selectedRoleIds.value, roleId];
    }
}

// Check if there are changes
const hasChanges = computed(() => {
    const currentIds = props.member.roles.map((r) => r.id).sort();
    const newIds = [...selectedRoleIds.value].sort();
    return JSON.stringify(currentIds) !== JSON.stringify(newIds);
});

// Mutation for updating roles
const { mutate: updateRoles, isLoading: isSubmitting } =
    useUpdateMemberRolesMutation();

// Submit handler
async function handleSubmit() {
    await updateRoles({
        entityId: props.entityId,
        userId: props.member.user_id,
        data: {
            role_ids: selectedRoleIds.value,
        },
    });
    open.value = false;
}

// Get member display name
const memberDisplayName = computed(() => {
    if (props.member.user_first_name && props.member.user_last_name) {
        return `${props.member.user_first_name} ${props.member.user_last_name}`;
    }
    return props.member.user_email;
});

// Get scope badge color
function getScopeBadgeColor(role: Role): UiColor {
    if (role.is_global) return "info";
    if (role.scope === "entity_only") return "warning";
    return "success"; // hierarchy
}

// Get scope badge label
function getScopeBadgeLabel(role: Role): string {
    if (role.is_global) return "Global";
    if (role.scope === "entity_only") return "This entity only";
    return "Hierarchy";
}
</script>

<template>
    <UModal v-model:open="open" title="Edit Member Roles" :ui="{ content: 'sm:max-w-lg' }">
        <template #body>
            <!-- Member Info -->
            <div class="flex items-center gap-3 pb-4 mb-4 border-b border-default">
                <UAvatar :alt="memberDisplayName" size="lg" />
                <div>
                    <p class="font-medium">{{ memberDisplayName }}</p>
                    <p class="text-sm text-muted">{{ member.user_email }}</p>
                </div>
            </div>

            <!-- Loading State -->
            <div
                v-if="isLoadingRoles"
                class="flex items-center justify-center py-8"
            >
                <UIcon
                    name="i-lucide-loader-2"
                    class="w-6 h-6 animate-spin text-primary"
                />
            </div>

            <!-- Roles Selection -->
            <div v-else class="space-y-6">
                <!-- Entity-Local Roles -->
                <div v-if="rolesByType.entityLocal.length > 0">
                    <h4
                        class="text-sm font-semibold mb-3 flex items-center gap-2"
                    >
                        <UIcon name="i-lucide-map-pin" class="w-4 h-4" />
                        Roles at this Entity
                    </h4>
                    <div class="space-y-2">
                        <div
                            v-for="role in rolesByType.entityLocal"
                            :key="role.id"
                            class="flex items-center justify-between p-3 rounded-lg border border-default hover:bg-muted/30 transition-colors cursor-pointer"
                            @click="toggleRole(role.id)"
                        >
                            <div class="flex items-center gap-3">
                                <UCheckbox
                                    :model-value="isRoleSelected(role.id)"
                                    @click.stop
                                    @update:model-value="toggleRole(role.id)"
                                />
                                <div>
                                    <p class="font-medium text-sm">
                                        {{ role.display_name || role.name }}
                                    </p>
                                    <p
                                        v-if="role.description"
                                        class="text-xs text-muted"
                                    >
                                        {{ role.description }}
                                    </p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <UBadge
                                    v-if="role.is_auto_assigned"
                                    color="primary"
                                    variant="subtle"
                                    size="xs"
                                >
                                    Auto
                                </UBadge>
                                <UBadge
                                    :color="getScopeBadgeColor(role)"
                                    variant="subtle"
                                    size="xs"
                                >
                                    {{ getScopeBadgeLabel(role) }}
                                </UBadge>
                                <UBadge color="neutral" variant="subtle" size="xs">
                                    {{ role.permissions?.length || 0 }} perms
                                </UBadge>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Inherited Roles -->
                <div v-if="rolesByType.inherited.length > 0">
                    <h4
                        class="text-sm font-semibold mb-3 flex items-center gap-2"
                    >
                        <UIcon name="i-lucide-git-branch" class="w-4 h-4" />
                        Inherited Roles
                        <UTooltip text="Roles from parent entities with hierarchy scope">
                            <UIcon
                                name="i-lucide-info"
                                class="w-3.5 h-3.5 text-muted"
                            />
                        </UTooltip>
                    </h4>
                    <div class="space-y-2">
                        <div
                            v-for="role in rolesByType.inherited"
                            :key="role.id"
                            class="flex items-center justify-between p-3 rounded-lg border border-default hover:bg-muted/30 transition-colors cursor-pointer"
                            @click="toggleRole(role.id)"
                        >
                            <div class="flex items-center gap-3">
                                <UCheckbox
                                    :model-value="isRoleSelected(role.id)"
                                    @click.stop
                                    @update:model-value="toggleRole(role.id)"
                                />
                                <div>
                                    <p class="font-medium text-sm">
                                        {{ role.display_name || role.name }}
                                    </p>
                                    <p class="text-xs text-muted">
                                        from {{ role.scope_entity_name || "parent entity" }}
                                    </p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <UBadge
                                    color="success"
                                    variant="subtle"
                                    size="xs"
                                >
                                    Hierarchy
                                </UBadge>
                                <UBadge color="neutral" variant="subtle" size="xs">
                                    {{ role.permissions?.length || 0 }} perms
                                </UBadge>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Global/Org Roles -->
                <div v-if="rolesByType.global.length > 0">
                    <h4
                        class="text-sm font-semibold mb-3 flex items-center gap-2"
                    >
                        <UIcon name="i-lucide-globe" class="w-4 h-4" />
                        Global Roles
                    </h4>
                    <div class="space-y-2">
                        <div
                            v-for="role in rolesByType.global"
                            :key="role.id"
                            class="flex items-center justify-between p-3 rounded-lg border border-default hover:bg-muted/30 transition-colors cursor-pointer"
                            @click="toggleRole(role.id)"
                        >
                            <div class="flex items-center gap-3">
                                <UCheckbox
                                    :model-value="isRoleSelected(role.id)"
                                    @click.stop
                                    @update:model-value="toggleRole(role.id)"
                                />
                                <div>
                                    <p class="font-medium text-sm">
                                        {{ role.display_name || role.name }}
                                    </p>
                                    <p
                                        v-if="role.description"
                                        class="text-xs text-muted"
                                    >
                                        {{ role.description }}
                                    </p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <UBadge color="info" variant="subtle" size="xs">
                                    Global
                                </UBadge>
                                <UBadge color="neutral" variant="subtle" size="xs">
                                    {{ role.permissions?.length || 0 }} perms
                                </UBadge>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Empty State -->
                <div
                    v-if="
                        availableRoles.length === 0 && !isLoadingRoles
                    "
                    class="text-center py-8"
                >
                    <UIcon
                        name="i-lucide-shield-off"
                        class="w-12 h-12 text-muted mx-auto mb-3"
                    />
                    <p class="text-muted">No roles available for this entity</p>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex items-center justify-between w-full">
                <p class="text-sm text-muted">
                    {{ selectedRoleIds.length }} role(s) selected
                </p>
                <div class="flex gap-2">
                    <UButton
                        label="Cancel"
                        color="neutral"
                        variant="outline"
                        @click="open = false"
                        :disabled="isSubmitting"
                    />
                    <UButton
                        label="Save Changes"
                        icon="i-lucide-save"
                        :loading="isSubmitting"
                        :disabled="!hasChanges"
                        @click="handleSubmit"
                    />
                </div>
            </div>
        </template>
    </UModal>
</template>
