<script setup lang="ts">
/**
 * Basic Info Tab
 * Edit user's basic information: email, full_name, username, status, etc.
 */

import type { User } from "~/types/auth";
import { useUpdateUserMutation } from "~/queries/users";

const props = defineProps<{
    user: User;
}>();

const userStore = useUserStore();
const authStore = useAuthStore();
const toast = useToast();

// Form state
const state = reactive({
    email: "",
    username: "",
    full_name: "",
    is_active: true,
    status: "active",
    metadata: {} as Record<string, any>,
});

// Watch for user changes and populate form
watch(
    () => props.user,
    (newUser) => {
        if (newUser) {
            state.email = newUser.email || "";
            state.username = newUser.username || newUser.email.split("@")[0];
            state.full_name = newUser.full_name || "";
            state.is_active = newUser.is_active !== false;
            state.status = newUser.status || "active";
            state.metadata = newUser.metadata || {};
        }
    },
    { immediate: true },
);

// Update mutation
const { mutate: updateUser, isPending: isSubmitting } = useUpdateUserMutation();

// Password change modal
const showPasswordModal = ref(false);
const passwordState = reactive({
    newPassword: "",
    confirmPassword: "",
});
const isChangingPassword = ref(false);

// Status options
const statusOptions = [
    { label: "Active", value: "active" },
    { label: "Suspended", value: "suspended" },
    { label: "Banned", value: "banned" },
];

// Form validation
const canSubmit = computed(() => {
    return state.email.trim() !== "" && state.email.includes("@");
});

const validationMessage = computed(() => {
    if (!state.email.trim()) return "Email is required";
    if (!state.email.includes("@")) return "Invalid email format";
    return "";
});

// Submit handler
async function handleSubmit() {
    if (!canSubmit.value) {
        toast.add({
            title: "Validation Error",
            description: validationMessage.value,
            color: "error",
        });
        return;
    }

    // Call mutation - toasts handled by mutation callbacks
    await updateUser({
        userId: props.user.id,
        data: {
            email: state.email,
            full_name: state.full_name || undefined,
            is_active: state.is_active,
            metadata:
                Object.keys(state.metadata).length > 0
                    ? state.metadata
                    : undefined,
        },
    });

    // Refresh user data in store
    await userStore.fetchUser(props.user.id);
}

// Password change handler (admin reset - no current password needed)
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
        // Admin password reset endpoint (no current password required)
        await authStore.apiCall(`/v1/users/${props.user.id}/password`, {
            method: "PATCH",
            body: {
                new_password: passwordState.newPassword,
            },
        });

        toast.add({
            title: "Password updated",
            description: "User's password has been changed successfully",
            color: "success",
        });

        // Reset form and close modal
        passwordState.newPassword = "";
        passwordState.confirmPassword = "";
        showPasswordModal.value = false;
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
                        Update user's basic information and settings
                    </p>
                </div>
            </div>
        </template>

        <form @submit.prevent="handleSubmit" class="space-y-6">
            <!-- Email -->
            <div>
                <div class="flex items-center justify-between mb-1.5">
                    <label class="text-sm font-medium text-foreground"
                        >Email Address</label
                    >
                    <UBadge
                        v-if="user.email_verified"
                        color="success"
                        variant="subtle"
                    >
                        <UIcon
                            name="i-lucide-check-circle"
                            class="w-3 h-3 mr-1"
                        />
                        Verified
                    </UBadge>
                    <UBadge v-else color="warning" variant="subtle">
                        <UIcon
                            name="i-lucide-alert-circle"
                            class="w-3 h-3 mr-1"
                        />
                        Unverified
                    </UBadge>
                </div>
                <UInput
                    v-model="state.email"
                    type="email"
                    placeholder="user@example.com"
                    :disabled="isSubmitting"
                />
            </div>

            <!-- Username (Read-only) -->
            <div>
                <div class="flex items-center justify-between mb-1.5">
                    <label class="text-sm font-medium text-foreground"
                        >Username</label
                    >
                    <UTooltip text="Username cannot be changed">
                        <UButton
                            icon="i-lucide-info"
                            color="neutral"
                            variant="ghost"
                            size="2xs"
                        />
                    </UTooltip>
                </div>
                <UInput
                    v-model="state.username"
                    placeholder="username"
                    disabled
                    readonly
                />
                <p class="mt-1.5 text-xs text-muted">
                    Usernames are automatically generated and cannot be modified
                </p>
            </div>

            <!-- Full Name -->
            <div>
                <label class="text-sm font-medium text-foreground mb-1.5 block"
                    >Full Name</label
                >
                <UInput
                    v-model="state.full_name"
                    placeholder="John Doe"
                    :disabled="isSubmitting"
                />
            </div>

            <!-- Status & Active Toggle -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- Status Dropdown -->
                <div>
                    <label
                        class="text-sm font-medium text-foreground mb-1.5 block"
                        >Status</label
                    >
                    <USelect
                        v-model="state.status"
                        :options="statusOptions"
                        :disabled="isSubmitting"
                    />
                </div>

                <!-- Active Toggle -->
                <div
                    class="flex items-center justify-between p-4 bg-muted/50 rounded-lg"
                >
                    <div>
                        <span class="text-sm font-medium text-foreground"
                            >Active</span
                        >
                        <p class="text-xs text-muted mt-1">
                            {{
                                state.is_active
                                    ? "User can log in"
                                    : "User is deactivated"
                            }}
                        </p>
                    </div>
                    <USwitch
                        v-model="state.is_active"
                        :disabled="isSubmitting"
                    />
                </div>
            </div>

            <!-- Password Change Button -->
            <div class="p-4 bg-muted/50 rounded-lg">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-foreground">
                            Password
                        </p>
                        <p class="text-xs text-muted mt-1">
                            Reset user's password (admin)
                        </p>
                    </div>
                    <UButton
                        icon="i-lucide-key"
                        label="Reset Password"
                        variant="outline"
                        @click="showPasswordModal = true"
                        :disabled="isSubmitting"
                    />
                </div>
            </div>

            <!-- System Fields (Read-only) -->
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
                        {{
                            user.created_at
                                ? new Date(user.created_at).toLocaleDateString()
                                : "N/A"
                        }}
                    </p>
                </div>
                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Last Updated
                    </p>
                    <p class="text-xs text-muted">
                        {{
                            user.updated_at
                                ? new Date(user.updated_at).toLocaleDateString()
                                : "N/A"
                        }}
                    </p>
                </div>
                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Superuser
                    </p>
                    <UBadge
                        :color="user.is_superuser ? 'primary' : 'neutral'"
                        variant="subtle"
                    >
                        {{ user.is_superuser ? "Yes" : "No" }}
                    </UBadge>
                </div>
            </div>

            <!-- Validation Message -->
            <div
                v-if="validationMessage && !canSubmit"
                class="text-sm text-error"
            >
                {{ validationMessage }}
            </div>

            <!-- Submit Button -->
            <div class="flex justify-end">
                <UButton
                    type="submit"
                    label="Save Changes"
                    icon="i-lucide-save"
                    :loading="isSubmitting"
                    :disabled="!canSubmit"
                />
            </div>
        </form>
    </UCard>

    <!-- Password Reset Modal -->
    <UModal
        v-model:open="showPasswordModal"
        title="Reset Password"
        description="Set a new password for this user"
        :ui="{ footer: 'justify-end' }"
    >
        <!-- Hidden trigger - modal controlled via v-model:open -->
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
                        <span class="text-xs text-muted"
                            >Minimum 8 characters</span
                        >
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
