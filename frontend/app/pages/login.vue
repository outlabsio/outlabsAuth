<script setup lang="ts">
definePageMeta({
  layout: "auth",
});

// Store references
const authStore = useAuthStore();
const router = useRouter();

// Form data
const formData = reactive({
  username: "",
  password: "",
  rememberMe: false,
});

// Form state
const isLoading = ref(false);
const errorMessage = ref("");

// Validation errors
const errors = reactive({
  username: "",
  password: "",
});

// Validation function
const validateForm = () => {
  errors.username = "";
  errors.password = "";

  if (!formData.username) {
    errors.username = "Username is required";
  }

  if (!formData.password) {
    errors.password = "Password is required";
  }

  return !errors.username && !errors.password;
};

// Submit handler
const handleSubmit = async () => {
  errorMessage.value = "";

  if (!validateForm()) {
    return;
  }

  isLoading.value = true;

  try {
    console.log("Submitting login with:", { username: formData.username, password: "***" });
    await authStore.login(formData.username, formData.password);
    await router.push("/dashboard");
  } catch (error: any) {
    console.error("Login error:", error);

    // Handle different error formats
    if (error.data?.detail) {
      if (Array.isArray(error.data.detail)) {
        errorMessage.value = error.data.detail.map((err: any) => err.msg).join(", ");
      } else if (typeof error.data.detail === "string") {
        errorMessage.value = error.data.detail;
      } else {
        errorMessage.value = JSON.stringify(error.data.detail);
      }
    } else if (error.statusMessage) {
      errorMessage.value = error.statusMessage;
    } else if (error.status === 422) {
      errorMessage.value = "Invalid credentials. Please check your username and password.";
    } else {
      errorMessage.value = "Login failed. Please check your credentials.";
    }
  } finally {
    isLoading.value = false;
  }
};

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
        <form @submit.prevent="handleSubmit" class="space-y-6">
          <!-- Server Error Alert -->
          <UAlert v-if="errorMessage" color="error" variant="subtle" icon="i-lucide-alert-circle" :title="errorMessage" :close-button="{ icon: 'i-lucide-x' }" @close="errorMessage = ''" />

          <!-- Username Field -->
          <UFormField label="Username" :error="errors.username" required>
            <UInput
              v-model="formData.username"
              @blur="
                () => {
                  if (!formData.username) errors.username = 'Username is required';
                  else errors.username = '';
                }
              "
              placeholder="Enter your username"
              size="lg"
              :disabled="isLoading"
              autofocus
            />
          </UFormField>

          <!-- Password Field -->
          <UFormField label="Password" :error="errors.password" required>
            <template #hint>
              <NuxtLink to="/recovery" class="text-sm text-primary hover:underline"> Forgot password? </NuxtLink>
            </template>
            <UInput
              v-model="formData.password"
              @blur="
                () => {
                  if (!formData.password) errors.password = 'Password is required';
                  else errors.password = '';
                }
              "
              type="password"
              placeholder="Enter your password"
              size="lg"
              :disabled="isLoading"
            />
          </UFormField>

          <!-- Remember Me Checkbox -->
          <UCheckbox v-model="formData.rememberMe" label="Remember me" :disabled="isLoading" />

          <!-- Submit Button -->
          <UButton type="submit" block size="lg" :loading="isLoading" :disabled="isLoading">
            {{ isLoading ? "Signing in..." : "Sign in" }}
          </UButton>

          <!-- Sign up link -->
          <div class="text-center text-sm">
            Don't have an account?
            <NuxtLink to="/signup" class="text-primary font-medium hover:underline"> Sign up </NuxtLink>
          </div>
        </form>
      </UCard>
    </div>
  </div>
</template>
