<template>
  <div class="fixed inset-0 w-full overflow-hidden flex flex-col">
    <div class="relative flex-grow flex flex-col overflow-y-auto">
      <!-- Background -->
      <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/10 to-secondary/10">
        <!-- Card -->
        <div class="w-full max-w-md p-8 bg-base-100/20 backdrop-blur-xl rounded-[4rem]">
          <UiCard class="text-center bg-base-100">
            <Logo class="w-12 h-12 mx-auto mt-6 mb-10" />
            <h1 class="text-3xl font-bold mb-6 text-center font-display">Forgot Password</h1>
            <form @submit.prevent="handlePasswordResetRequest" class="space-y-4" novalidate>
              <!-- Email input -->
              <div>
                <label class="input flex items-center gap-2 bg-base-200 border-base-300/20" :class="{ 'input-error': errors.email }">
                  <Icon name="lucide:mail" class="h-4 w-4 opacity-70" />
                  <input
                    v-model="email"
                    type="email"
                    class="grow focus:outline-none text-center"
                    placeholder="Email Address"
                    @input="handleInput('email')"
                    @blur="handleBlur('email')"
                    autocomplete="off"
                  />
                </label>
                <transition name="collapse">
                  <p v-if="showErrors.email && errors.email" class="text-error text-xs mt-1">{{ errors.email }}</p>
                </transition>
              </div>

              <button type="submit" class="btn btn-primary w-full" :class="{ 'btn-disabled': isLoading || cooldownRemaining > 0 }" :disabled="isLoading || cooldownRemaining > 0">
                <span v-if="isLoading" class="loading loading-spinner"></span>
                <span v-else-if="cooldownRemaining > 0">Please wait {{ cooldownRemaining }} seconds</span>
                <span v-else>Reset Password</span>
              </button>
            </form>
            <p v-if="error" class="mt-4 text-error text-sm text-center">{{ error }}</p>
            <p v-if="success" class="mt-4 text-success text-sm text-center">{{ success }}</p>
            <div class="mt-6 text-center">
              <p class="text-sm text-base-content">
                Remember your password?
                <NuxtLink to="/login" class="text-primary hover:text-secondary transition-colors duration-300"> Login </NuxtLink>
              </p>
            </div>
          </UiCard>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { z } from "zod";
definePageMeta({
  layout: "default",
});

const authStore = useAuthStore();

const email = ref("");
const error = ref("");
const success = ref("");
const isLoading = ref(false);
const cooldownRemaining = ref(0);
const cooldownDuration = 60; // 60 seconds cooldown
const errors = reactive({
  email: "",
});
const isFormValid = ref(false);

const fieldBlurred = reactive({
  email: false,
});

const showErrors = reactive({
  email: false,
});

const schema = z.object({
  email: z.string().email("Invalid email address"),
});

function validateField(field) {
  const formData = { email: email.value };
  const result = schema.safeParse(formData);

  if (!result.success) {
    const fieldError = result.error.issues.find((issue) => issue.path[0] === field);
    errors[field] = fieldError ? fieldError.message : "";
  } else {
    errors[field] = "";
  }

  isFormValid.value = result.success;
}

function handleInput(field) {
  validateField(field);
}

function handleBlur(field) {
  showErrors[field] = true;
}

const startCooldown = () => {
  cooldownRemaining.value = cooldownDuration;
  const timer = setInterval(() => {
    cooldownRemaining.value--;
    if (cooldownRemaining.value <= 0) {
      clearInterval(timer);
    }
  }, 1000);
};

async function handlePasswordResetRequest() {
  if (cooldownRemaining.value > 0) return;

  validateField("email");

  if (errors.email) {
    showErrors.email = true;
    return;
  }

  isLoading.value = true;
  error.value = "";
  success.value = "";

  try {
    const resetSuccess = await authStore.requestPasswordReset(email.value);
    if (resetSuccess) {
      success.value = "Password reset link sent! Please check your email.";
      email.value = ""; // Clear the email input after successful request
      showErrors.email = false;
      startCooldown();
    } else {
      error.value = "Failed to send reset link. Please try again.";
    }
  } catch (err) {
    console.error("Password reset request error:", err);
    if (err.statusCode === 429) {
      error.value = "Too many requests. Please try again later.";
      startCooldown();
    } else {
      error.value = err.message || "An error occurred. Please try again.";
    }
  } finally {
    isLoading.value = false;
  }
}
</script>

<style scoped>
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease-in-out;
  max-height: 100px;
  opacity: 1;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
