<template>
  <div class="min-h-screen flex items-center justify-center bg-cover bg-center">
    <div class="w-full max-w-md p-8 glassbase backdrop-blur-xl rounded-[4rem] text-white">
      <UiCard class="text-center">
        <h1 class="text-3xl font-bold mb-6 text-center font-display">Request Verification Email</h1>
        <form @submit.prevent="handleVerificationRequest" class="space-y-4">
          <!-- Email input -->
          <div>
            <label class="input flex items-center gap-2 bg-white/5" :class="{ 'input-error': errors.email }">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4 opacity-70">
                <path d="M2.5 3A1.5 1.5 0 0 0 1 4.5v.793c.026.009.051.02.076.032L7.674 8.51c.206.1.446.1.652 0l6.598-3.185A.755.755 0 0 1 15 5.293V4.5A1.5 1.5 0 0 0 13.5 3h-11Z" />
                <path d="M15 6.954 8.978 9.86a2.25 2.25 0 0 1-1.956 0L1 6.954V11.5A1.5 1.5 0 0 0 2.5 13h11a1.5 1.5 0 0 0 1.5-1.5V6.954Z" />
              </svg>
              <input
                v-model="email"
                type="email"
                class="grow bg-transparent focus:outline-none text-center placeholder-white/80"
                placeholder="Enter your email address"
                @blur="handleBlur('email')"
                @input="handleInput('email')"
              />
            </label>
            <transition name="collapse">
              <p v-if="errors.email" class="text-red-400 text-xs mt-1">{{ errors.email }}</p>
            </transition>
          </div>

          <button type="submit" class="btn btn-primary w-full" :class="{ 'btn-disabled': isLoading || cooldownRemaining > 0 }" :disabled="isLoading || cooldownRemaining > 0">
            <span v-if="isLoading" class="loading loading-spinner"></span>
            <span v-else-if="cooldownRemaining > 0">Please wait {{ cooldownRemaining }} seconds</span>
            <span v-else>Send Verification Email</span>
          </button>
        </form>
        <p v-if="error" class="mt-4 text-red-400 text-sm text-center">{{ error }}</p>
        <p v-if="success" class="mt-4 text-green-400 text-sm text-center">{{ success }}</p>
      </UiCard>
    </div>
  </div>
</template>

<script setup>
import { z } from "zod";

const authStore = useAuthStore();

const email = ref("");
const error = ref("");
const success = ref("");
const isLoading = ref(false);
const errors = reactive({
  email: "",
});
const isFormValid = ref(false);

const fieldBlurred = reactive({
  email: false,
});

const schema = z.object({
  email: z.string().email("Invalid email address"),
});

const cooldownRemaining = ref(0);
const cooldownDuration = 60; // 60 seconds cooldown

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

function handleBlur(field) {
  fieldBlurred[field] = true;
  validateField(field);
}

function handleInput(field) {
  if (fieldBlurred[field]) {
    validateField(field);
  }
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

async function handleVerificationRequest() {
  if (cooldownRemaining.value > 0) return;

  validateField("email");

  if (!isFormValid.value) {
    return;
  }

  isLoading.value = true;
  error.value = "";
  success.value = "";

  try {
    const result = await authStore.requestVerification(email.value);
    if (result) {
      success.value = "Verification email sent! Please check your inbox.";
      email.value = "";
      startCooldown();
    } else {
      error.value = "Failed to send verification email. Please try again.";
    }
  } catch (err) {
    console.error("Verification request error:", err);
    if (err.statusCode === 429) {
      error.value = "Too many requests. Please try again later.";
      startCooldown();
    } else {
      error.value = err.message || "An error occurred while sending the verification email.";
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
