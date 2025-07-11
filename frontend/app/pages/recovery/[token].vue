<template>
  <div class="fixed inset-0 w-full overflow-hidden flex flex-col">
    <div class="relative flex-grow flex flex-col overflow-y-auto">
      <!-- Background -->
      <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/10 to-secondary/10">
        <!-- Card -->
        <div class="w-full max-w-md p-8 bg-base-100/20 backdrop-blur-xl rounded-[4rem]">
          <UiCard class="text-center bg-base-100">
            <Logo class="w-12 h-12 mx-auto mt-6 mb-10" />
            <h1 class="text-3xl font-bold mb-6 text-center font-display">Reset Your Password</h1>
            <transition name="fade-slide" mode="out-in">
              <div v-if="!success" key="reset-form" class="reset-form">
                <transition name="fade" mode="out-in">
                  <div v-if="!showRecoveryButton" key="reset-form">
                    <form @submit.prevent="handlePasswordReset" class="space-y-4">
                      <!-- New Password input -->
                      <div>
                        <label class="input flex items-center gap-2 bg-base-200 border-base-300/20" :class="{ 'input-error': errors.newPassword }">
                          <Icon name="lucide:key" class="h-4 w-4 opacity-70" />
                          <input
                            v-model="newPassword"
                            type="password"
                            class="grow focus:outline-none text-center"
                            placeholder="New Password"
                            @blur="handleBlur('newPassword')"
                            @input="handleInput('newPassword')"
                          />
                        </label>
                        <transition name="collapse">
                          <p v-if="errors.newPassword" class="text-error text-xs mt-1">{{ errors.newPassword }}</p>
                        </transition>
                      </div>

                      <!-- Confirm Password input -->
                      <div>
                        <label class="input flex items-center gap-2 bg-base-200 border-base-300/20" :class="{ 'input-error': errors.confirmPassword }">
                          <Icon name="lucide:key" class="h-4 w-4 opacity-70" />
                          <input
                            v-model="confirmPassword"
                            type="password"
                            class="grow focus:outline-none text-center"
                            placeholder="Confirm Password"
                            @blur="handleBlur('confirmPassword')"
                            @input="handleInput('confirmPassword')"
                          />
                        </label>
                        <transition name="collapse">
                          <p v-if="errors.confirmPassword" class="text-error text-xs mt-1">{{ errors.confirmPassword }}</p>
                        </transition>
                      </div>

                      <button type="submit" class="btn btn-primary w-full" :class="{ 'btn-disabled': isLoading }" :disabled="isLoading">
                        <span v-if="isLoading" class="loading loading-spinner"></span>
                        Reset Password
                      </button>
                    </form>
                  </div>
                  <div v-else key="recovery-button" class="space-y-4">
                    <p class="text-error text-sm text-center">{{ error }}</p>
                    <button @click="goToRecovery" class="btn btn-secondary w-full">Request New Reset Link</button>
                  </div>
                </transition>
              </div>
              <div v-else key="success-message" class="success-message">
                <p class="text-success text-xl mb-4">{{ success }}</p>
                <div class="relative w-24 h-24 mx-auto">
                  <svg class="w-full h-full" viewBox="0 0 100 100">
                    <circle class="text-base-200 stroke-current" stroke-width="4" cx="50" cy="50" r="46" fill="transparent" />
                    <circle class="text-primary progress-ring__circle stroke-current" stroke-width="4" stroke-linecap="round" cx="50" cy="50" r="46" fill="transparent" :style="{ strokeDashoffset }" />
                  </svg>
                  <div class="absolute inset-0 flex items-center justify-center">
                    <span class="text-2xl font-light">{{ countdownValue }}</span>
                  </div>
                </div>
              </div>
            </transition>
            <div v-if="!success" class="mt-6 text-center">
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

<script setup lang="ts">
import { z } from "zod";

definePageMeta({
  layout: "default",
});

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const newPassword = ref("");
const confirmPassword = ref("");
const error = ref("");
const success = ref("");
const isLoading = ref(false);
const errors = reactive({
  newPassword: "",
  confirmPassword: "",
});
const isUnmounted = ref(false);

const fieldBlurred = reactive({
  newPassword: false,
  confirmPassword: false,
});

const token = route.params.token as string;

const showRecoveryButton = ref(false);

const countdownValue = ref(5);
const strokeDashoffset = ref(0);
const circumference = 2 * Math.PI * 46; // Updated to match the new radius

function startCountdown() {
  const timer = setInterval(() => {
    if (countdownValue.value > 0) {
      countdownValue.value--;
      strokeDashoffset.value = circumference * (1 - countdownValue.value / 5);
    } else {
      clearInterval(timer);
      router.push("/login");
    }
  }, 1000);
}

onUnmounted(() => {
  isUnmounted.value = true;
  isLoading.value = false;
});

const schema = z
  .object({
    newPassword: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/, "Password must contain uppercase, lowercase and a number"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

function validateField(field: "newPassword" | "confirmPassword") {
  const formData = { newPassword: newPassword.value, confirmPassword: confirmPassword.value };
  const result = schema.safeParse(formData);

  if (!result.success) {
    const fieldError = result.error.issues.find((issue) => issue.path[0] === field);
    errors[field] = fieldError ? fieldError.message : "";
  } else {
    errors[field] = "";
  }
}

function handleBlur(field: "newPassword" | "confirmPassword") {
  fieldBlurred[field] = true;
  validateField(field);
}

function handleInput(field: "newPassword" | "confirmPassword") {
  if (fieldBlurred[field]) {
    validateField(field);
  }
}

async function handlePasswordReset() {
  validateField("newPassword");
  validateField("confirmPassword");

  if (Object.values(errors).some((error) => error !== "")) {
    error.value = "Please fix the errors before submitting";
    return;
  }

  isLoading.value = true;
  error.value = "";
  success.value = "";

  try {
    await authStore.resetPassword(token, newPassword.value);
    if (!isUnmounted.value) {
      success.value = "Your password has been reset successfully!";
      startCountdown();
    }
  } catch (err: any) {
    if (!isUnmounted.value) {
      error.value = err.data?.message || "An unknown error occurred";
      showRecoveryButton.value = error.value === "invalidOrExpiredResetToken";
    }
  } finally {
    if (!isUnmounted.value) {
      isLoading.value = false;
    }
  }
}

function goToRecovery() {
  router.push("/recovery");
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.5s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

.reset-form,
.success-message {
  transition: all 0.5s ease;
}

.progress-ring__circle {
  stroke-dasharray: 289.027; /* Updated to match the new circumference */
  transition: stroke-dashoffset 0.35s;
  transform: rotate(-90deg);
  transform-origin: 50% 50%;
}
</style>
