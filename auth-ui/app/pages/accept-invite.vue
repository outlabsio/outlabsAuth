<template>
    <div
        class="flex flex-col items-center justify-center gap-4 p-4 min-h-screen"
    >
        <UPageCard class="w-full max-w-md">
            <div v-if="!acceptSuccess">
                <UAuthForm
                    :schema="acceptInviteSchema"
                    title="Set your password"
                    description="You've been invited to join"
                    icon="i-lucide-user-check"
                    :fields="fields"
                    :loading="isLoading"
                    @submit="onSubmit"
                >
                    <template #description>
                        <p class="text-sm text-gray-600 dark:text-gray-400">
                            Choose a password to activate your account.
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
                                Already have an account? Login
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

                <h2 class="text-2xl font-bold">Account activated!</h2>

                <p class="text-gray-600 dark:text-gray-400">
                    Your account has been set up successfully. You can now login
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
    layout: false,
    auth: false,
});

// Get token from URL query
const route = useRoute();
const token = computed(() => route.query.token as string);

// Form fields configuration
const fields: AuthFormField[] = [
    {
        name: "new_password",
        type: "password",
        label: "Password",
        placeholder: "Choose a strong password",
        required: true,
    },
    {
        name: "confirm_password",
        type: "password",
        label: "Confirm Password",
        placeholder: "Confirm your password",
        required: true,
    },
];

// Zod validation schema
const acceptInviteSchema = z
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

type AcceptInviteSchema = z.infer<typeof acceptInviteSchema>;

// Component state
const isLoading = ref(false);
const errorMessage = ref("");
const acceptSuccess = ref(false);

// Auth store
const authStore = useAuthStore();

// Check for token on mount
onMounted(() => {
    if (!token.value) {
        errorMessage.value = "Invalid or missing invite token";
    }
});

// Form submission
const onSubmit = async (event: FormSubmitEvent<AcceptInviteSchema>) => {
    if (!token.value) {
        errorMessage.value = "Invalid or missing invite token";
        return;
    }

    isLoading.value = true;
    errorMessage.value = "";

    try {
        // Call accept invite API
        await authStore.apiCall("/v1/auth/accept-invite", {
            method: "POST",
            body: {
                token: token.value,
                new_password: event.data.new_password,
            },
        });

        acceptSuccess.value = true;
    } catch (error: any) {
        console.error("Accept invite error:", error);

        if (error.status === 400 || error.status === 401) {
            errorMessage.value =
                "Invalid or expired invite token. Please ask for a new invitation.";
        } else if (error.message) {
            errorMessage.value = error.message;
        } else {
            errorMessage.value = "Failed to accept invitation. Please try again.";
        }
    } finally {
        isLoading.value = false;
    }
};
</script>
