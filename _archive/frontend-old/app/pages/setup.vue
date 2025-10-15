<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({
  layout: "auth",
});

// Store references
const authStore = useAuthStore();
const router = useRouter();
const toast = useToast();

// Form schema
const schema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string(),
  firstName: z.string().min(1, 'First name is required'),
  lastName: z.string().min(1, 'Last name is required'),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

type Schema = z.infer<typeof schema>

// Form state
const state = reactive({
  email: '',
  password: '',
  confirmPassword: '',
  firstName: '',
  lastName: '',
});

const isLoading = ref(false);

// Submit handler
const onSubmit = async (event: FormSubmitEvent<Schema>) => {
  isLoading.value = true;

  try {
    await authStore.initializeSystem(
      event.data.email,
      event.data.password,
      event.data.firstName,
      event.data.lastName
    );

    toast.add({
      title: 'System Initialized',
      description: 'System has been successfully initialized. You can now log in with your credentials.',
      color: 'success',
    });

    // Redirect to login page
    await router.push('/login');
  } catch (error: any) {
    console.error('Setup error:', error);
    
    const errorMessage = error.data?.detail || error.statusMessage || 'Failed to initialize system';
    toast.add({
      title: 'Setup Failed',
      description: errorMessage,
      color: 'error',
    });
  } finally {
    isLoading.value = false;
  }
};

// Check if system is already initialized
onMounted(async () => {
  try {
    const status = await authStore.checkSystemStatus();
    if (!status.requires_setup) {
      toast.add({
        title: 'System Already Initialized',
        description: 'The system has already been initialized.',
        color: 'info',
      });
      await router.push('/login');
    }
  } catch (error) {
    console.error('Failed to check system status:', error);
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
        <h2 class="text-3xl font-bold tracking-tight">OutlabsAuth</h2>
        <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
          Let's set up your system by creating the first administrator account
        </p>
      </div>

      <!-- Setup Form Card -->
      <UCard>
        <UForm :schema="schema" :state="state" @submit="onSubmit" class="space-y-6">
          <!-- Email Field -->
          <UFormField name="email">
            <UInput
              v-model="state.email"
              type="email"
              placeholder="Email address"
              size="lg"
              :disabled="isLoading"
              autofocus
              class="w-full"
            />
          </UFormField>

          <!-- First Name and Last Name in a grid -->
          <div class="grid grid-cols-2 gap-4">
            <UFormField name="firstName">
              <UInput
                v-model="state.firstName"
                placeholder="First name"
                size="lg"
                :disabled="isLoading"
                class="w-full"
              />
            </UFormField>

            <UFormField name="lastName">
              <UInput
                v-model="state.lastName"
                placeholder="Last name"
                size="lg"
                :disabled="isLoading"
                class="w-full"
              />
            </UFormField>
          </div>

          <!-- Password Field -->
          <UFormField name="password">
            <UInput
              v-model="state.password"
              type="password"
              placeholder="Password"
              size="lg"
              :disabled="isLoading"
              class="w-full"
            />
          </UFormField>

          <!-- Confirm Password Field -->
          <UFormField name="confirmPassword">
            <UInput
              v-model="state.confirmPassword"
              type="password"
              placeholder="Confirm password"
              size="lg"
              :disabled="isLoading"
              class="w-full"
            />
          </UFormField>

          <!-- Submit Button -->
          <UButton 
            type="submit" 
            block 
            size="lg" 
            :loading="isLoading" 
            :disabled="isLoading"
          >
            {{ isLoading ? "Setting up..." : "Complete Setup" }}
          </UButton>
        </UForm>
      </UCard>
    </div>
  </div>
</template>