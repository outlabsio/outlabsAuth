<script setup lang="ts">
import type { User } from "~/types/auth";
import {
    useUpdateUserMutation,
    useUpdateUserStatusMutation,
} from "~/queries/users";

const props = defineProps<{
    user: User;
}>();

const userStore = useUserStore();
const usersStore = useUsersStore();
const authStore = useAuthStore();
const toast = useToast();

type UserAccountStatus = "active" | "suspended" | "banned";

const state = reactive({
    email: "",
    first_name: "",
    last_name: "",
    status: "active" as UserAccountStatus,
});

watch(
    () => props.user,
    (newUser) => {
        if (!newUser) {
            return;
        }

        state.email = newUser.email || "";
        state.first_name = newUser.first_name || "";
        state.last_name = newUser.last_name || "";
        state.status = (newUser.status || "active") as UserAccountStatus;
    },
    { immediate: true },
);

const { mutateAsync: updateUser, isLoading: isSubmitting } =
    useUpdateUserMutation();
const { mutateAsync: updateUserStatus, isLoading: isUpdatingStatus } =
    useUpdateUserStatusMutation();
const isSaving = computed(() => isSubmitting.value || isUpdatingStatus.value);

const showPasswordModal = ref(false);
const passwordState = reactive({
    newPassword: "",
    confirmPassword: "",
});
const isChangingPassword = ref(false);

const statusOptions = [
    { label: "Active", value: "active" },
    { label: "Suspended", value: "suspended" },
    { label: "Banned", value: "banned" },
] satisfies { label: string; value: UserAccountStatus }[];

const canSubmit = computed(() => {
    return state.email.trim() !== "" && state.email.includes("@");
});

const hasProfileChanges = computed(() => {
    return (
        state.email !== (props.user.email || "") ||
        state.first_name !== (props.user.first_name || "") ||
        state.last_name !== (props.user.last_name || "")
    );
});

const hasStatusChange = computed(() => state.status !== props.user.status);

const hasChanges = computed(
    () => hasProfileChanges.value || hasStatusChange.value,
);

const validationMessage = computed(() => {
    if (!state.email.trim()) return "Email is required";
    if (!state.email.includes("@")) return "Invalid email format";
    return "";
});

function formatDate(date: string | undefined) {
    if (!date) return "N/A";
    return new Date(date).toLocaleString();
}

async function handleSubmit() {
    if (!canSubmit.value) {
        toast.add({
            title: "Validation error",
            description: validationMessage.value,
            color: "error",
        });
        return;
    }

    if (!hasChanges.value) {
        toast.add({
            title: "No changes to save",
            description: "Update one or more fields before saving.",
            color: "neutral",
        });
        return;
    }

    if (hasProfileChanges.value) {
        await updateUser({
            userId: props.user.id,
            data: {
                email: state.email,
                first_name: state.first_name || undefined,
                last_name: state.last_name || undefined,
            },
        });
    }

    if (hasStatusChange.value) {
        await updateUserStatus({
            userId: props.user.id,
            status: state.status,
        });
    }


    await userStore.fetchUser(props.user.id);
}

async function handlePasswordChange() {
    if (passwordState.newPassword !== passwordState.confirmPassword) {
        toast.add({
            title: "Password mismatch",
            description: "New password and confirmation do not match",
            color: "error",
        });
        return;
    }

    if (passwordState.newPassword.length < 8) {
        toast.add({
            title: "Password too short",
            description: "Password must be at least 8 characters",
            color: "error",
        });
        return;
    }

    isChangingPassword.value = true;

    try {
        await authStore.apiCall(`/v1/users/${props.user.id}/password`, {
            method: "PATCH",
            body: {
                new_password: passwordState.newPassword,
            },
        });

        toast.add({
            title: "Password updated",
            description: "User password was reset successfully.",
            color: "success",
        });

        passwordState.newPassword = "";
        passwordState.confirmPassword = "";
        showPasswordModal.value = false;
        await userStore.fetchUser(props.user.id);
    } catch (error: any) {
        toast.add({
            title: "Failed to change password",
            description: error.message || "An error occurred",
            color: "error",
        });
    } finally {
        isChangingPassword.value = false;
    }
}
</script>

<template>
    <UCard>
        <template #header>
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-lg font-semibold text-foreground">
                        User Information
                    </h3>
                    <p class="text-sm text-muted">
                        Update the user's profile and account status.
                    </p>
                </div>
            </div>
        </template>

        <form @submit.prevent="handleSubmit" class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="text-sm font-medium text-foreground mb-1.5 block">
                        First Name
                    </label>
                    <UInput
                        v-model="state.first_name"
                        placeholder="Jane"
                        :disabled="isSaving"
                    />
                </div>

                <div>
                    <label class="text-sm font-medium text-foreground mb-1.5 block">
                        Last Name
                    </label>
                    <UInput
                        v-model="state.last_name"
                        placeholder="Doe"
                        :disabled="isSaving"
                    />
                </div>
            </div>

            <div>
                <div class="flex items-center justify-between mb-1.5">
                    <label class="text-sm font-medium text-foreground">
                        Email Address
                    </label>
                    <UBadge
                        :color="user.email_verified ? 'success' : 'warning'"
                        variant="subtle"
                    >
                        {{ user.email_verified ? "Verified" : "Unverified" }}
                    </UBadge>
                </div>
                <UInput
                    v-model="state.email"
                    type="email"
                    placeholder="user@example.com"
                    :disabled="isSaving"
                />
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="text-sm font-medium text-foreground mb-1.5 block">
                        Account Status
                    </label>
                    <USelect
                        v-model="state.status"
                        :items="statusOptions"
                        value-key="value"
                        :disabled="isSaving"
                    />
                </div>

                <div
                    class="rounded-lg border border-default bg-muted/40 p-4 flex items-center justify-between"
                >
                    <div>
                        <p class="text-sm font-medium text-foreground">
                            Superuser
                        </p>
                        <p class="text-xs text-muted mt-1">
                            Full system-level permissions
                        </p>
                    </div>
                    <UBadge
                        :color="user.is_superuser ? 'primary' : 'neutral'"
                        variant="subtle"
                    >
                        {{ user.is_superuser ? "Yes" : "No" }}
                    </UBadge>
                </div>
            </div>

            <div
                v-if="user.root_entity_name || user.root_entity_id"
                class="rounded-lg border border-default bg-muted/40 p-4"
            >
                <p class="text-sm font-medium text-foreground">
                    Organization
                </p>
                <p class="text-sm text-muted mt-1">
                    {{ user.root_entity_name || user.root_entity_id }}
                </p>
            </div>

            <div class="rounded-lg border border-default bg-muted/40 p-4">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-foreground">
                            Password
                        </p>
                        <p class="text-xs text-muted mt-1">
                            Reset the user's password without requiring their current password.
                        </p>
                    </div>
                    <UButton
                        icon="i-lucide-key"
                        label="Reset Password"
                        variant="outline"
                        @click="showPasswordModal = true"
                        :disabled="isSaving"
                    />
                </div>
            </div>

            <div
                class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-border"
            >
                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        User ID
                    </p>
                    <p class="text-xs text-muted font-mono">{{ user.id }}</p>
                </div>
                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Created At
                    </p>
                    <p class="text-xs text-muted">
                        {{ formatDate(user.created_at) }}
                    </p>
                </div>
                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Last Updated
                    </p>
                    <p class="text-xs text-muted">
                        {{ formatDate(user.updated_at) }}
                    </p>
                </div>
                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Last Login
                    </p>
                    <p class="text-xs text-muted">
                        {{ formatDate(user.last_login) }}
                    </p>
                </div>
            </div>

            <div
                v-if="validationMessage && !canSubmit"
                class="text-sm text-error"
            >
                {{ validationMessage }}
            </div>

            <div class="flex justify-end">
                <UButton
                    type="submit"
                    label="Save Changes"
                    icon="i-lucide-save"
                    :loading="isSaving"
                    :disabled="!canSubmit || !hasChanges"
                />
            </div>
        </form>
    </UCard>

    <UModal
        v-model:open="showPasswordModal"
        title="Reset Password"
        description="Set a new password for this user"
        :ui="{ footer: 'justify-end' }"
    >
        <span />

        <template #body>
            <form @submit.prevent="handlePasswordChange" class="space-y-4">
                <UFormField label="New Password" name="newPassword" required>
                    <UInput
                        v-model="passwordState.newPassword"
                        type="password"
                        placeholder="Enter new password"
                        class="w-full"
                        :disabled="isChangingPassword"
                    />
                    <template #hint>
                        <span class="text-xs text-muted">
                            Minimum 8 characters
                        </span>
                    </template>
                </UFormField>

                <UFormField
                    label="Confirm Password"
                    name="confirmPassword"
                    required
                >
                    <UInput
                        v-model="passwordState.confirmPassword"
                        type="password"
                        placeholder="Confirm new password"
                        class="w-full"
                        :disabled="isChangingPassword"
                    />
                </UFormField>
            </form>
        </template>

        <template #footer="{ close }">
            <UButton
                label="Cancel"
                color="neutral"
                variant="outline"
                @click="close"
                :disabled="isChangingPassword"
            />
            <UButton
                label="Reset Password"
                icon="i-lucide-key"
                @click="handlePasswordChange"
                :loading="isChangingPassword"
            />
        </template>
    </UModal>
</template>
