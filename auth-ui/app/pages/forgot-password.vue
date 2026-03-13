<template>
    <div
        class="flex flex-col items-center justify-center gap-4 p-4 min-h-screen"
    >
        <UPageCard class="w-full max-w-md">
            <div v-if="!submitted">
                <UAuthForm
                    :schema="forgotPasswordSchema"
                    title="Forgot password?"
                    description="Enter your email address"
                    icon="i-lucide-mail"
                    :fields="fields"
                    :loading="isLoading"
                    @submit="onSubmit"
                >
                    <template #description>
                        <p class="text-sm text-gray-600 dark:text-gray-400">
                            We'll send you a link to reset your password.
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
                        <NuxtLink
                            to="/login"
                            class="text-sm text-center text-primary hover:underline"
                        >
                            Back to login
                        </NuxtLink>
                    </template>
                </UAuthForm>
            </div>

            <!-- Success State -->
            <div v-else>
                <div class="text-center space-y-4">
                    <div class="flex justify-center">
                        <div class="rounded-full bg-primary/10 p-3">
                            <UIcon
                                name="i-lucide-mail-check"
                                class="w-12 h-12 text-primary"
                            />
                        </div>
                    </div>

                    <h2 class="text-2xl font-bold">Check your email</h2>

                    <p class="text-sm text-gray-600 dark:text-gray-400">
                        If an account exists for
                        <strong>{{ submittedEmail }}</strong
                        >, you will receive a password reset link shortly.
                    </p>

                    <p class="text-xs text-gray-500 dark:text-gray-500">
                        Didn't receive an email? Check your spam folder or try
                        again.
                    </p>

                    <div class="flex flex-col gap-2 pt-4">
                        <UButton
                            color="primary"
                            variant="outline"
                            block
                            @click="resetForm"
                            :disabled="cooldownRemaining > 0"
                        >
                            {{
                                cooldownRemaining > 0
                                    ? `Wait ${cooldownRemaining}s to send another`
                                    : "Send another link"
                            }}
                        </UButton>

                        <UButton
                            color="neutral"
                            variant="ghost"
                            block
                            @click="$router.push('/login')"
                        >
                            Back to login
                        </UButton>
                    </div>
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

// Form fields configuration
const fields: AuthFormField[] = [
    {
        name: "email",
        type: "email",
        label: "Email",
        placeholder: "you@example.com",
        required: true,
    },
];

// Zod validation schema
const forgotPasswordSchema = z.object({
    email: z.string().email("Invalid email address"),
});

type ForgotPasswordSchema = z.infer<typeof forgotPasswordSchema>;

// Component state
const isLoading = ref(false);
const errorMessage = ref("");
const submitted = ref(false);
const submittedEmail = ref("");
const cooldownRemaining = ref(0);
let cooldownInterval: NodeJS.Timeout | null = null;

// Auth store
const authStore = useAuthStore();

// Start cooldown timer
const startCooldown = (seconds: number) => {
    cooldownRemaining.value = seconds;

    // Clear existing interval
    if (cooldownInterval) {
        clearInterval(cooldownInterval);
    }

    // Start countdown
    cooldownInterval = setInterval(() => {
        cooldownRemaining.value--;

        if (cooldownRemaining.value <= 0) {
            if (cooldownInterval) {
                clearInterval(cooldownInterval);
                cooldownInterval = null;
            }
        }
    }, 1000);
};

// Form submission
const onSubmit = async (event: FormSubmitEvent<ForgotPasswordSchema>) => {
    isLoading.value = true;
    errorMessage.value = "";

    try {
        // Call forgot password API
        await authStore.apiCall("/v1/auth/forgot-password", {
            method: "POST",
            body: {
                email: event.data.email,
            },
        });

        // Show success message (even if email doesn't exist - security best practice)
        submittedEmail.value = event.data.email;
        submitted.value = true;

        // Start cooldown (5 minutes = 300 seconds)
        startCooldown(300);
    } catch (error: any) {
        console.error("Forgot password error:", error);

        // Handle rate limit error (429)
        if (error.status === 429) {
            const detail = error.data?.detail || error.detail;
            const retryAfter = detail?.retry_after_seconds || 300;
            const minutes =
                detail?.retry_after_minutes || Math.ceil(retryAfter / 60);

            errorMessage.value = `Too many requests. Please wait ${minutes} minute${
                minutes !== 1 ? "s" : ""
            } before trying again.`;

            // Start cooldown with server-provided time
            startCooldown(retryAfter);

            // Still show success to not reveal if email exists
            submittedEmail.value = event.data.email;
            submitted.value = true;
        } else {
            // For any other error, show success (security best practice - don't reveal if email exists)
            submittedEmail.value = event.data.email;
            submitted.value = true;
        }
    } finally {
        isLoading.value = false;
    }
};

// Reset form
const resetForm = () => {
    if (cooldownRemaining.value > 0) {
        return; // Don't reset if in cooldown
    }

    submitted.value = false;
    submittedEmail.value = "";
    errorMessage.value = "";
};

// Cleanup on unmount
onUnmounted(() => {
    if (cooldownInterval) {
        clearInterval(cooldownInterval);
    }
});
</script>
