<script setup lang="ts">
import { useQuery } from "@pinia/colada";
import { usersQueries } from "~/queries/users";
import { rolesQueries } from "~/queries/roles";
import { useAddMemberMutation } from "~/queries/memberships";
import type { User } from "~/types/auth";
import type { Role } from "~/types/role";

const props = defineProps<{
    entityId: string;
}>();

const open = defineModel<boolean>("open", { default: false });

// Fetch users for selection
const { data: usersData, isLoading: isLoadingUsers } = useQuery(
    usersQueries.list({}, { page: 1, limit: 100 }),
);

// Fetch available roles for this entity
const { data: rolesData, isLoading: isLoadingRoles } = useQuery(
    rolesQueries.list(
        { for_entity_id: props.entityId },
        { page: 1, limit: 100 },
    ),
);

const { mutateAsync: addMember, status: addMemberStatus } =
    useAddMemberMutation();
const isPending = computed(() => addMemberStatus.value === "pending");

// Form state
const state = reactive({
    user_id: "" as string,
    role_ids: [] as string[],
});

// Reset form when modal opens
watch(open, (isOpen) => {
    if (isOpen) {
        state.user_id = "";
        state.role_ids = [];
    }
});

// User options for dropdown
const userOptions = computed(() => {
    const users = usersData.value?.items || [];
    return users.map((user: User) => ({
        label:
            user.first_name && user.last_name
                ? `${user.first_name} ${user.last_name} (${user.email})`
                : user.email,
        value: user.id,
    }));
});

// Role options for multi-select
const roleOptions = computed(() => {
    const roles = rolesData.value?.items || [];
    return roles.map((role: Role) => ({
        label: role.display_name || role.name,
        value: role.id,
    }));
});

// Form validation
const isFormValid = computed(() => {
    return state.user_id !== "";
});

// Submit handler
async function handleSubmit() {
    try {
        await addMember({
            entity_id: props.entityId,
            user_id: state.user_id,
            role_ids: state.role_ids,
        });

        // Close modal (mutation handles toast)
        open.value = false;
    } catch (error: any) {
        console.error("Failed to add member:", error);
    }
}
</script>

<template>
    <UModal
        v-model:open="open"
        title="Add Member"
        description="Add a user to this entity"
    >
        <template #body>
            <div class="space-y-4">
                <!-- User Selection -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">
                        User
                        <span class="text-error">*</span>
                    </label>
                    <USelect
                        v-model="state.user_id"
                        :items="userOptions"
                        placeholder="Select a user..."
                        :loading="isLoadingUsers"
                        searchable
                    />
                </div>

                <!-- Role Selection -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">
                        Roles
                        <span class="text-muted text-xs ml-1">(optional)</span>
                    </label>
                    <USelectMenu
                        v-model="state.role_ids"
                        :items="roleOptions"
                        placeholder="Select roles..."
                        :loading="isLoadingRoles"
                        multiple
                        searchable
                        value-key="value"
                    />
                    <p class="text-xs text-muted">
                        Select roles to assign to this member. Auto-assigned
                        roles will be added automatically.
                    </p>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex justify-end gap-2">
                <UButton
                    label="Cancel"
                    color="neutral"
                    variant="outline"
                    :disabled="isPending"
                    @click="open = false"
                />
                <UButton
                    label="Add Member"
                    icon="i-lucide-user-plus"
                    :loading="isPending"
                    :disabled="!isFormValid || isPending"
                    @click="handleSubmit"
                />
            </div>
        </template>
    </UModal>
</template>
