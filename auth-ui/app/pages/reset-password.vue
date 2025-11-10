<template>
    <div
        class="flex flex-col items-center justify-center gap-4 p-4 min-h-screen"
    >
        <UPageCard class="w-full max-w-md">
            <div v-if="!resetSuccess">
                <UAuthForm
                    :schema="resetPasswordSchema"
                    title="Reset your password"
                    description="Enter your new password"
                    icon="i-lucide-lock"
                    :fields="fields"
                    :loading="isLoading"
                    @submit="onSubmit"
                >
                    <template #description>
                        <p class="text-sm text-gray-600 dark:text-gray-400">
                            Choose a strong password for your account.
                        </p>
                    </template>

                    <template #validation v-if="errorMessage">
                        <UAlert
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
                    </template>

                    <template #footer>
                        <div class="text-center text-sm">
                            <NuxtLink
                                to="/login"
                                class="text-primary hover:underline"
                            >
                                Back to login
                            </NuxtLink>
                        </div>
                    </template>
                </UAuthForm>
            </div>

            <div v-else class="text-center space-y-4 p-6">
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

                <h2 class="text-2xl font-bold">Password reset successful!</h2>

                <p class="text-gray-600 dark:text-gray-400">
                    Your password has been successfully reset. You can now login
                    with your new password.
                </p>

                <div class="pt-4">
                    <UButton
                        color="primary"
                        block
                        @click="$router.push('/login')"
                    >
                        Continue to login
                    </UButton>
                </div>
            </div>
        </UPageCard>
    </div>
</template>

<script setup lang="ts">
import { z } from "zod";
import type { FormSubmitEvent, AuthFormField } from "@nuxt/ui";

// Metadata
definePageMeta({
    layout: false, // Use no layout for auth pages
    auth: false, // Allow unauthenticated access
});

// Get token from URL query
const route = useRoute();
const token = computed(() => route.query.token as string);

// Form fields configuration
const fields: AuthFormField[] = [
    {
        name: "new_password",
        type: "password",
        label: "New Password",
        placeholder: "Enter your new password",
        required: true,
    },
    {
        name: "confirm_password",
        type: "password",
        label: "Confirm Password",
        placeholder: "Confirm your new password",
        required: true,
    },
];

// Zod validation schema
const resetPasswordSchema = z
    .object({
        new_password: z
            .string()
            .min(8, "Password must be at least 8 characters"),
        confirm_password: z
            .string()
            .min(8, "Password must be at least 8 characters"),
    })
    .refine((data) => data.new_password === data.confirm_password, {
        message: "Passwords don't match",
        path: ["confirm_password"],
    });

type ResetPasswordSchema = z.infer<typeof resetPasswordSchema>;

// Component state
const isLoading = ref(false);
const errorMessage = ref("");
const resetSuccess = ref(false);

// Auth store
const authStore = useAuthStore();
const router = useRouter();

// Check for token on mount
onMounted(() => {
    if (!token.value) {
        errorMessage.value = "Invalid or missing reset token";
    }
});

// Form submission
const onSubmit = async (event: FormSubmitEvent<ResetPasswordSchema>) => {
    if (!token.value) {
        errorMessage.value = "Invalid or missing reset token";
        return;
    }

    isLoading.value = true;
    errorMessage.value = "";

    try {
        // Call reset password API
        await authStore.apiCall("/v1/auth/reset-password", {
            method: "POST",
            body: {
                token: token.value,
                new_password: event.data.new_password,
            },
        });

        // Show success message
        resetSuccess.value = true;
    } catch (error: any) {
        console.error("Reset password error:", error);

        // Handle specific error cases
        if (error.status === 400 || error.status === 401) {
            errorMessage.value =
                "Invalid or expired reset token. Please request a new password reset.";
        } else if (error.message) {
            errorMessage.value = error.message;
        } else {
            errorMessage.value = "Failed to reset password. Please try again.";
        }
    } finally {
        isLoading.value = false;
    }
};
</script>
