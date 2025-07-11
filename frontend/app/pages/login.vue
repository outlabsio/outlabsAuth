<script setup lang="ts">
import { useForm } from "@tanstack/vue-form";
import * as z from "zod";

definePageMeta({
  layout: "auth",
});

// Validation schema
const loginSchema = z.object({
  username: z.string().min(1, "Email is required").email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required").min(6, "Password must be at least 6 characters"),
  rememberMe: z.boolean().optional(),
});

type LoginFormData = z.infer<typeof loginSchema>;

// Store references
const authStore = useAuthStore();
const router = useRouter();

// Form state
const serverError = ref("");

// Initialize TanStack Form
const form = useForm({
  defaultValues: {
    username: "",
    password: "",
    rememberMe: false,
  } as LoginFormData,
  onSubmit: async ({ value }) => {
    serverError.value = "";

    try {
      console.log("Submitting login with:", { username: value.username, password: "***" });
      await authStore.login(value.username, value.password);
      await router.push("/dashboard");
    } catch (error: any) {
      console.error("Login error:", error);

      // Handle different error formats
      if (error.data?.detail) {
        if (Array.isArray(error.data.detail)) {
          serverError.value = error.data.detail.map((err: any) => err.msg).join(", ");
        } else if (typeof error.data.detail === "string") {
          serverError.value = error.data.detail;
        } else {
          serverError.value = JSON.stringify(error.data.detail);
        }
      } else if (error.statusMessage) {
        serverError.value = error.statusMessage;
      } else if (error.status === 422) {
        serverError.value = "Invalid credentials. Please check your username and password.";
      } else {
        serverError.value = "Login failed. Please check your credentials.";
      }
    }
  },
});

// Redirect if already authenticated
onMounted(() => {
  if (authStore.isAuthenticated) {
    router.push("/dashboard");
  }
});
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="w-full max-w-md space-y-8">
      <!-- Logo and Title -->
      <div class="text-center">
        <div class="flex justify-center mb-6">
          <UIcon name="i-lucide-shield-check" class="h-12 w-12 text-primary" />
        </div>
        <h2 class="text-3xl font-bold tracking-tight">Sign in to OutlabsAuth</h2>
        <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">Enter your credentials to access the admin dashboard</p>
      </div>

      <!-- Login Form Card -->
      <UCard>
        <form @submit.prevent.stop="form.handleSubmit" class="space-y-6">
          <!-- Server Error Alert -->
          <UAlert v-if="serverError" color="error" variant="subtle" icon="i-lucide-alert-circle" :title="serverError" :close-button="{ icon: 'i-lucide-x' }" @close="serverError = ''" />

          <!-- Email Field with Live Validation -->
          <form.Field
            name="username"
            :validators="{
              onChange: ({ value }) => {
                if (!value) return 'Email is required';
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) return 'Please enter a valid email address';
                return undefined;
              },
              onBlur: ({ value }) => {
                if (!value) return 'Email is required';
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) return 'Please enter a valid email address';
                return undefined;
              },
            }"
          >
            <template v-slot="{ field }">
              <UFormField label="Email" :error="field.state.meta.errors.length ? field.state.meta.errors[0] : undefined" required>
                <UInput
                  :model-value="field.state.value"
                  @update:model-value="(value) => field.handleChange(String(value))"
                  @blur="field.handleBlur"
                  type="email"
                  placeholder="Enter your email"
                  size="lg"
                  autofocus
                />
              </UFormField>
            </template>
          </form.Field>

          <!-- Password Field with Live Validation -->
          <form.Field
            name="password"
            :validators="{
              onChange: ({ value }) => {
                if (!value) return 'Password is required';
                if (value.length < 6) return 'Password must be at least 6 characters';
                return undefined;
              },
              onBlur: ({ value }) => {
                if (!value) return 'Password is required';
                if (value.length < 6) return 'Password must be at least 6 characters';
                return undefined;
              },
            }"
          >
            <template v-slot="{ field }">
              <UFormField label="Password" :error="field.state.meta.errors.length ? field.state.meta.errors[0] : undefined" required>
                <template #hint>
                  <NuxtLink to="/recovery" class="text-sm text-primary hover:underline"> Forgot password? </NuxtLink>
                </template>
                <UInput
                  :model-value="field.state.value"
                  @update:model-value="(value) => field.handleChange(String(value))"
                  @blur="field.handleBlur"
                  type="password"
                  placeholder="Enter your password"
                  size="lg"
                />
              </UFormField>
            </template>
          </form.Field>

          <!-- Remember Me Checkbox -->
          <form.Field name="rememberMe">
            <template v-slot="{ field }">
              <UCheckbox :model-value="field.state.value" @update:model-value="(value) => field.handleChange(Boolean(value))" label="Remember me" />
            </template>
          </form.Field>

          <!-- Submit Button with Form State -->
          <form.Subscribe>
            <template v-slot="{ canSubmit, isSubmitting }">
              <UButton type="submit" block size="lg" :loading="isSubmitting" :disabled="!canSubmit || isSubmitting">
                {{ isSubmitting ? "Signing in..." : "Sign in" }}
              </UButton>
            </template>
          </form.Subscribe>

          <!-- Sign up link -->
          <div class="text-center text-sm">
            Don't have an account?
            <NuxtLink to="/signup" class="text-primary font-medium hover:underline"> Sign up </NuxtLink>
          </div>
        </form>

        <!-- Debug Form State (only in development) -->
        <div v-if="$dev" class="mt-6 p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
          <h4 class="font-medium mb-2 text-sm">Form State (Dev Only)</h4>
          <form.Subscribe>
            <template v-slot="{ values, errors, isValid, canSubmit }">
              <div class="space-y-2 text-xs">
                <div class="flex gap-2">
                  <UBadge :color="isValid ? 'success' : 'error'" size="xs">
                    {{ isValid ? "Valid" : "Invalid" }}
                  </UBadge>
                  <UBadge :color="canSubmit ? 'success' : 'warning'" size="xs">
                    {{ canSubmit ? "Can Submit" : "Cannot Submit" }}
                  </UBadge>
                </div>
                <div>
                  <strong>Values:</strong>
                  <pre class="text-xs mt-1 p-2 bg-white dark:bg-gray-800 rounded">{{ JSON.stringify(values, null, 2) }}</pre>
                </div>
                <div v-if="Object.keys(errors).length">
                  <strong>Errors:</strong>
                  <pre class="text-xs mt-1 p-2 bg-red-50 dark:bg-red-900/20 rounded">{{ JSON.stringify(errors, null, 2) }}</pre>
                </div>
              </div>
            </template>
          </form.Subscribe>
        </div>
      </UCard>
    </div>
  </div>
</template>
