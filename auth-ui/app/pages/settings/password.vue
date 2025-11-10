<script setup lang="ts">
// Page is protected by global auth middleware
definePageMeta({
    layout: "default",
});

// Form state
const form = reactive({
    current_password: "",
    new_password: "",
    confirm_password: "",
});

const isLoading = ref(false);
const errorMessage = ref("");
const changeSuccess = ref(false);

// Auth store
const authStore = useAuthStore();

// Form validation
const isFormValid = computed(() => {
    return (
        form.current_password.length > 0 &&
        form.new_password.length >= 8 &&
        form.confirm_password.length >= 8 &&
        form.new_password === form.confirm_password
    );
});

// Form submission
const onSubmit = async () => {
    // Validate passwords match
    if (form.new_password !== form.confirm_password) {
        errorMessage.value = "Passwords don't match";
        return;
    }

    // Validate password length
    if (form.new_password.length < 8) {
        errorMessage.value = "Password must be at least 8 characters";
        return;
    }

    isLoading.value = true;
    errorMessage.value = "";

    try {
        // Call change password API
        await authStore.apiCall("/v1/users/me/change-password", {
            method: "POST",
            body: {
                current_password: form.current_password,
                new_password: form.new_password,
            },
        });

        // Show success message
        changeSuccess.value = true;

        // Clear form
        form.current_password = "";
        form.new_password = "";
        form.confirm_password = "";
    } catch (error: any) {
        console.error("Change password error:", error);

        // Handle specific error cases with user-friendly messages
        if (error.status === 400) {
            errorMessage.value = "Current password is incorrect";
        } else if (error.status === 422) {
            errorMessage.value = "New password does not meet requirements";
        } else if (error.message) {
            errorMessage.value = error.message;
        } else {
            errorMessage.value = "Failed to change password. Please try again.";
        }
    } finally {
        isLoading.value = false;
    }
};

// Reset form
const resetForm = () => {
    changeSuccess.value = false;
    form.current_password = "";
    form.new_password = "";
    form.confirm_password = "";
    errorMessage.value = "";
};
</script>

<template>
    <UDashboardPanel id="change-password">
        <template #header>
            <UDashboardNavbar title="Change Password">
                <template #leading>
                    <UDashboardSidebarCollapse />
                </template>
            </UDashboardNavbar>
        </template>

        <template #body>
            <div class="max-w-2xl">
                <div v-if="!changeSuccess">
                    <p class="text-sm text-muted mb-6">
                        Update your account password. Make sure to use a strong,
                        unique password.
                    </p>

                    <form @submit.prevent="onSubmit" class="space-y-6">
                        <!-- Current Password -->
                        <UFormField
                            label="Current Password"
                            name="current_password"
                            required
                        >
                            <UInput
                                v-model="form.current_password"
                                type="password"
                                placeholder="Enter your current password"
                                :disabled="isLoading"
                            />
                        </UFormField>

                        <!-- New Password -->
                        <UFormField
                            label="New Password"
                            name="new_password"
                            required
                            help="Password must be at least 8 characters"
                        >
                            <UInput
                                v-model="form.new_password"
                                type="password"
                                placeholder="Enter your new password"
                                :disabled="isLoading"
                            />
                        </UFormField>

                        <!-- Confirm New Password -->
                        <UFormField
                            label="Confirm New Password"
                            name="confirm_password"
                            required
                        >
                            <UInput
                                v-model="form.confirm_password"
                                type="password"
                                placeholder="Confirm your new password"
                                :disabled="isLoading"
                            />
                        </UFormField>

                        <!-- Error Message -->
                        <UAlert
                            v-if="errorMessage"
                            color="error"
                            icon="i-lucide-alert-circle"
                            :title="errorMessage"
                            :close-button="{
                                icon: 'i-lucide-x',
                                color: 'error',
                                variant: 'link',
                                padded: false,
                            }"
                            @close="errorMessage = ''"
                        />

                        <!-- Submit Button -->
                        <div class="flex justify-end gap-3">
                            <UButton
                                color="neutral"
                                variant="outline"
                                @click="$router.push('/dashboard')"
                                :disabled="isLoading"
                            >
                                Cancel
                            </UButton>

                            <UButton
                                type="submit"
                                color="primary"
                                :loading="isLoading"
                                :disabled="!isFormValid"
                            >
                                Change Password
                            </UButton>
                        </div>
                    </form>
                </div>

                <!-- Success Message -->
                <div v-else class="text-center space-y-4 py-8">
                    <div class="flex justify-center">
                        <div
                            class="rounded-full bg-green-100 dark:bg-green-900/30 p-3"
                        >
                            <UIcon
                                name="i-lucide-check-circle"
                                class="w-12 h-12 text-green-600 dark:text-green-400"
                            />
                        </div>
                    </div>

                    <h2 class="text-2xl font-bold">
                        Password changed successfully!
                    </h2>

                    <p class="text-gray-600 dark:text-gray-400">
                        Your password has been updated. For security reasons,
                        you may be logged out on other devices.
                    </p>

                    <div class="flex justify-center gap-3 pt-4">
                        <UButton
                            color="neutral"
                            variant="outline"
                            @click="$router.push('/dashboard')"
                        >
                            Go to Dashboard
                        </UButton>

                        <UButton color="primary" @click="resetForm">
                            Change Password Again
                        </UButton>
                    </div>
                </div>
            </div>
        </template>
    </UDashboardPanel>
</template>
