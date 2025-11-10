<template>
    <div
        class="flex flex-col items-center justify-center gap-4 p-4 min-h-screen"
    >
        <UPageCard class="w-full max-w-md">
            <UAuthForm
                :schema="loginSchema"
                title="Welcome back!"
                description="Sign in to your OutlabsAuth account"
                icon="i-lucide-lock-keyhole"
                :fields="fields"
                :loading="isLoading"
                @submit="onSubmit"
            >
                <template #description>
                    <p class="text-sm text-gray-600 dark:text-gray-400">
                        Sign in with your credentials. Try:
                        <code
                            class="text-xs bg-neutral-100 dark:bg-neutral-800 px-1 py-0.5 rounded"
                            >newuser@example.com</code
                        >
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
                            to="/forgot-password"
                            class="text-primary hover:underline"
                        >
                            Forgot password?
                        </NuxtLink>
                    </div>
                </template>
            </UAuthForm>
        </UPageCard>
    </div>
</template>

<script setup lang="ts">
import { z } from "zod";
import type { FormSubmitEvent, AuthFormField } from "@nuxt/ui";

// Metadata
definePageMeta({
    layout: false, // Use no layout for login page
});

// Auth form fields configuration - Email and password for real API
const fields: AuthFormField[] = [
    {
        name: "email",
        type: "email",
        label: "Email",
        placeholder: "you@example.com",
        required: true,
    },
    {
        name: "password",
        type: "password",
        label: "Password",
        placeholder: "Enter your password",
        required: true,
    },
];

// Zod validation schema - Email and password
const loginSchema = z.object({
    email: z.string().email("Invalid email address"),
    password: z.string().min(1, "Password is required"),
});

type LoginSchema = z.infer<typeof loginSchema>;

// Component state
const isLoading = ref(false);
const errorMessage = ref("");

// Stores
const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

// Form submission - Real API mode: use actual credentials
const onSubmit = async (event: FormSubmitEvent<LoginSchema>) => {
    isLoading.value = true;
    errorMessage.value = "";

    try {
        await authStore.login({
            email: event.data.email,
            password: event.data.password,
        });

        // Initialize context after successful login
        const contextStore = useContextStore();
        await contextStore.initialize();

        // Redirect to intended page or dashboard
        const redirect = route.query.redirect as string;
        await router.push(redirect || "/dashboard");
    } catch (error: any) {
        console.error("Login error:", error);
        errorMessage.value = error.message || "Invalid email address";
    } finally {
        isLoading.value = false;
    }
};
</script>
