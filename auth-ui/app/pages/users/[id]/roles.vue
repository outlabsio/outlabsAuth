<script setup lang="ts">
/**
 * Roles Tab
 * Manage user's role assignments
 * SimpleRBAC: Global roles
 * EnterpriseRBAC: Roles with entity context
 */

import type { User } from "~/types/auth";
import { rolesQueries } from "~/queries/roles";

const props = defineProps<{
    user: User;
}>();

const userStore = useUserStore();
const toast = useToast();

// Fetch user's current roles
const userRoles = computed(() => userStore.userRoles);

// Fetch all available roles
const { data: allRoles, isLoading: isLoadingAvailableRoles } = useQuery(
    rolesQueries.list(),
);

// Available roles (exclude already assigned)
const availableRoles = computed(() => {
    if (!allRoles.value) return [];
    const assignedRoleIds = userRoles.value.map((ur) => ur.role.id);
    return (
        allRoles.value.items?.filter((r) => !assignedRoleIds.includes(r.id)) ||
        []
    );
});

// Selected role for adding
const selectedRoleId = ref("");
const showRemoveRoleConfirm = ref(false);
const roleToRemove = ref<{ id: string; name: string } | null>(null);
const isRemovingRole = ref(false);

// Add role handler
async function handleAddRole() {
    if (!selectedRoleId.value) {
        toast.add({
            title: "No role selected",
            description: "Please select a role to assign",
            color: "warning",
        });
        return;
    }

    const success = await userStore.assignRole(
        props.user.id,
        selectedRoleId.value,
    );

    if (success) {
        selectedRoleId.value = "";
    }
}

// Remove role handler
async function handleRemoveRole(roleId: string) {
    const role = userRoles.value.find((ur) => ur.role.id === roleId);

    if (!role) return;

    roleToRemove.value = {
        id: roleId,
        name: role.role.display_name || role.role.name,
    };
    showRemoveRoleConfirm.value = true;
}

function resetRemoveRoleConfirm() {
    if (isRemovingRole.value) {
        return;
    }
    showRemoveRoleConfirm.value = false;
    roleToRemove.value = null;
}

async function confirmRemoveRole() {
    if (!roleToRemove.value) {
        return;
    }

    isRemovingRole.value = true;
    try {
        await userStore.removeRole(props.user.id, roleToRemove.value.id);
        showRemoveRoleConfirm.value = false;
        roleToRemove.value = null;
    } finally {
        isRemovingRole.value = false;
    }
}

watch(showRemoveRoleConfirm, (isOpen) => {
    if (!isOpen && !isRemovingRole.value) {
        roleToRemove.value = null;
    }
});

// Format date helper
function formatDate(date: string) {
    return new Date(date).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}
</script>

<template>
    <div class="flex flex-col gap-6">
        <!-- Header -->
        <div class="flex items-center justify-between">
            <div>
                <h3 class="text-lg font-semibold text-foreground">
                    Role Assignments
                </h3>
                <p class="text-sm text-muted">
                    Manage global roles for this user
                </p>
            </div>
            <UBadge color="primary" variant="subtle">
                {{ userRoles.length }}
                {{ userRoles.length === 1 ? "role" : "roles" }}
            </UBadge>
        </div>

        <!-- Current Roles List -->
        <div class="space-y-3">
            <div v-if="userStore.isLoadingRoles" class="text-center py-8">
                <UIcon
                    name="i-lucide-loader-2"
                    class="w-6 h-6 animate-spin text-primary mb-2"
                />
                <p class="text-sm text-muted">Loading roles...</p>
            </div>

            <div v-else-if="userRoles.length === 0" class="text-center py-8">
                <UIcon
                    name="i-lucide-shield-off"
                    class="w-12 h-12 text-muted mb-4"
                />
                <p class="text-sm font-medium text-foreground mb-1">
                    No roles assigned
                </p>
                <p class="text-xs text-muted">
                    This user has no roles assigned yet
                </p>
            </div>

            <UCard
                v-else
                v-for="membership in userRoles"
                :key="membership.role.id"
                class="hover:bg-muted/50 transition-colors"
            >
                <div class="flex items-start justify-between">
                    <!-- Role Info -->
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-1">
                            <p class="font-medium text-foreground">
                                {{
                                    membership.role.display_name ||
                                    membership.role.name
                                }}
                            </p>
                            <UBadge
                                v-if="membership.role.is_global"
                                color="info"
                                variant="subtle"
                            >
                                Global
                            </UBadge>
                        </div>

                        <p
                            v-if="membership.role.description"
                            class="text-sm text-muted mb-2"
                        >
                            {{ membership.role.description }}
                        </p>

                        <div class="flex items-center gap-4 text-xs text-muted">
                            <div class="flex items-center gap-1">
                                <UIcon name="i-lucide-shield" class="w-3 h-3" />
                                <span
                                    >{{
                                        membership.role.permissions?.length || 0
                                    }}
                                    permissions</span
                                >
                            </div>
                            <div class="flex items-center gap-1">
                                <UIcon
                                    name="i-lucide-calendar"
                                    class="w-3 h-3"
                                />
                                <span
                                    >Granted
                                    {{
                                        formatDate(membership.granted_at)
                                    }}</span
                                >
                            </div>
                        </div>
                    </div>

                    <!-- Remove Button -->
                    <UButton
                        icon="i-lucide-trash"
                        color="error"
                        variant="ghost"
                        size="sm"
                        @click="handleRemoveRole(membership.role.id)"
                    />
                </div>
            </UCard>
        </div>

        <!-- Add Role Section -->
        <div class="border-t border-default pt-6">
            <h4 class="text-sm font-semibold text-foreground mb-3">Add Role</h4>

            <div v-if="isLoadingAvailableRoles" class="text-center py-4">
                <UIcon
                    name="i-lucide-loader-2"
                    class="w-5 h-5 animate-spin text-primary"
                />
            </div>

            <div
                v-else-if="availableRoles.length === 0"
                class="text-center py-4"
            >
                <p class="text-sm text-muted">
                    All available roles have been assigned
                </p>
            </div>

            <div v-else class="flex gap-2">
                <USelect
                    v-model="selectedRoleId"
                    :items="
                        availableRoles.map((r) => ({
                            label: r.display_name || r.name,
                            value: r.id,
                        }))
                    "
                    value-key="value"
                    placeholder="Select a role to assign"
                    class="flex-1"
                />
                <UButton
                    icon="i-lucide-plus"
                    label="Add Role"
                    @click="handleAddRole"
                    :disabled="!selectedRoleId"
                />
            </div>

            <p class="text-xs text-muted mt-2">
                Assigning a role grants all permissions associated with that
                role
            </p>
        </div>
    </div>

    <ConfirmActionModal
        v-model:open="showRemoveRoleConfirm"
        title="Remove role assignment?"
        :description="
            roleToRemove
                ? `This will remove '${roleToRemove.name}' from this user.`
                : 'This will remove this role from the user.'
        "
        confirm-label="Remove role"
        confirm-color="warning"
        :loading="isRemovingRole"
        @confirm="confirmRemoveRole"
        @cancel="resetRemoveRoleConfirm"
    />
</template>
