<template>
  <div class="fixed inset-0 w-full overflow-hidden flex flex-col">
    <div class="relative flex-grow flex flex-col overflow-y-auto">
      <!--- Background -->
      <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/10 to-secondary/10">
        <!--- Card -->
        <div class="w-full max-w-md p-8 bg-base-100/20 backdrop-blur-xl rounded-[4rem]">
          <UiCard class="text-center bg-base-100">
            <Logo class="w-12 h-12 mx-auto mt-6 mb-10" />
            <!--<h1 class="text-3xl text-primary mb-6 text-center font-light">{{ $t("signup.title") }}</h1>-->

            <form @submit.prevent="handleSignup" class="space-y-4">
              <!-- Name input -->
              <div>
                <label class="input flex items-center gap-2 bg-base-200 border-base-300/20" :class="{ 'input-error': errors.name }">
                  <Icon name="lucide:user" class="h-4 w-4 opacity-70" />
                  <input v-model="name" type="text" class="grow focus:outline-none text-center" placeholder="Full Name" @blur="handleBlur('name')" @input="handleInput('name')" />
                </label>
                <transition name="collapse">
                  <p v-if="errors.name" class="text-error text-xs mt-1">{{ errors.name }}</p>
                </transition>
              </div>

              <!-- Email input -->
              <div>
                <label class="input flex items-center gap-2 bg-base-200 border-base-300/20" :class="{ 'input-error': errors.email }">
                  <Icon name="lucide:mail" class="h-4 w-4 opacity-70" />
                  <input v-model="email" type="email" class="grow focus:outline-none text-center" placeholder="Email Address" @blur="handleBlur('email')" @input="handleInput('email')" />
                </label>
                <transition name="collapse">
                  <p v-if="errors.email" class="text-error text-xs mt-1">{{ errors.email }}</p>
                </transition>
              </div>

              <!-- Password input -->
              <div>
                <label class="input flex items-center gap-2 bg-base-200 border-base-300/20" :class="{ 'input-error': errors.password }">
                  <Icon name="lucide:key" class="h-4 w-4 opacity-70" />
                  <input v-model="password" type="password" class="grow focus:outline-none text-center" placeholder="Password" @blur="handleBlur('password')" @input="handleInput('password')" />
                </label>
                <transition name="collapse">
                  <p v-if="errors.password" class="text-error text-xs mt-1">{{ errors.password }}</p>
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

              <!-- Invitation Code input -->
              <div class="flex flex-col items-center justify-center p-4 bg-base-200 border border-base-300/20 rounded-lg">
                <label class="flex items-center justify-center text-sm mb-4">
                  <Icon name="lucide:lock" class="h-4 w-4 opacity-70 mr-2" />
                  <span>Invitation Code</span>
                </label>
                <UiOtp v-model="invitationCode" @update:modelValue="handleInvitationCodeChange" />
                <transition name="collapse">
                  <p v-if="errors.invitationCode" class="text-error text-xs mt-1">{{ errors.invitationCode }}</p>
                </transition>
              </div>

              <button type="submit" class="btn btn-primary w-full" :class="{ 'btn-disabled': isLoading }" :disabled="isLoading">
                <span v-if="isLoading" class="loading loading-spinner"></span>
                Sign Up
              </button>
            </form>
            <p v-if="error" class="mt-4 text-error text-sm text-center">{{ error }}</p>
            <div class="mt-5 text-center">
              <p class="text-sm">
                Already have an account?
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
const router = useRouter();

const name = ref("");
const email = ref("");
const password = ref("");
const confirmPassword = ref("");
const invitationCode = ref("");
const error = ref("");
const isLoading = ref(false);
const errors = reactive({
  name: "",
  email: "",
  password: "",
  confirmPassword: "",
  invitationCode: "",
});
const isUnmounted = ref(false);

const fieldBlurred = reactive({
  name: false,
  email: false,
  password: false,
  confirmPassword: false,
  invitationCode: false,
});

onUnmounted(() => {
  isUnmounted.value = true;
  isLoading.value = false;
});

const schema = z
  .object({
    name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Invalid email address"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/, "Password must contain uppercase, lowercase and a number"),
    confirmPassword: z.string(),
    invitationCode: z.string().length(6, "Invitation code must be 6 characters"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

function validateField(field) {
  const formData = {
    name: name.value,
    email: email.value,
    password: password.value,
    confirmPassword: confirmPassword.value,
    invitationCode: invitationCode.value.trim() || undefined,
  };
  const result = schema.safeParse(formData);

  if (!result.success) {
    const fieldError = result.error.issues.find((issue) => issue.path[0] === field);
    errors[field] = fieldError ? fieldError.message : "";
  } else {
    errors[field] = "";
  }
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

function handleInvitationCodeChange(value) {
  invitationCode.value = value;
  if (fieldBlurred.invitationCode) {
    validateField("invitationCode");
  }
}

async function handleSignup() {
  console.log("Signup Component: Starting signup process");
  validateField("name");
  validateField("email");
  validateField("password");
  validateField("confirmPassword");
  validateField("invitationCode");

  if (Object.values(errors).some((error) => error !== "")) {
    console.log("Signup Component: Validation errors found");
    error.value = "Please fix the errors before submitting";
    return;
  }

  isLoading.value = true;
  error.value = "";

  try {
    console.log("Signup Component: Calling authStore.signup");
    await authStore.signup(name.value, email.value, password.value, invitationCode.value.trim());
    console.log("Signup Component: Signup successful");

    if (!isUnmounted.value) {
      console.log("Signup Component: Attempting login");
      await authStore.login(email.value, password.value);
      console.log("Signup Component: Login successful");
      router.push("/");
    }
  } catch (err) {
    console.error("Signup Component: Signup/Login error:", err);

    if (!isUnmounted.value) {
      console.log("Signup Component: Processing error message");
      switch (err.message) {
        case "INVALID_OR_EXPIRED_INVITATION_CODE":
          error.value = "Invalid or expired invitation code";
          break;
        case "REGISTER_USER_ALREADY_EXISTS":
          error.value = "User already exists";
          break;
        case "REGISTER_INVALID_PASSWORD":
          error.value = "Invalid password: must contain uppercase, lowercase and a number";
          break;
        default:
          error.value = `Signup error: ${err.message}`;
          break;
      }
      console.log("Signup Component: Set error message:", error.value);
    }
  } finally {
    if (!isUnmounted.value) {
      isLoading.value = false;
      console.log("Signup Component: Process completed, isLoading set to false");
    }
  }
}
</script>

<style>
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
/* Aggressive autofill style overrides */
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
input:-webkit-autofill:active,
input:autofill,
input:autofill:hover,
input:autofill:focus,
input:autofill:active {
  -webkit-text-fill-color: hsl(var(--bc)) !important; /* Use base-content color */
  color: hsl(var(--bc)) !important; /* Fallback for non-webkit browsers */
  -webkit-box-shadow: 0 0 0 1000px transparent inset !important;
  transition: background-color 5000s ease-in-out 0s !important;
  background: transparent !important;
  background-clip: content-box !important;
  border-color: inherit !important;
  box-shadow: none !important;
}

/* Ensure all text properties are inherited */
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
input:-webkit-autofill:active,
input:autofill,
input:autofill:hover,
input:autofill:focus,
input:autofill:active {
  font: inherit !important;
  font-size: inherit !important;
  font-family: inherit !important;
  line-height: inherit !important;
  letter-spacing: inherit !important;
  word-spacing: inherit !important;
  text-transform: inherit !important;
  text-indent: inherit !important;
  text-shadow: inherit !important;
  text-align: inherit !important;
  -webkit-text-fill-color: currentColor !important;
}

/* Override any potential background images */
input:-webkit-autofill,
input:autofill {
  background-image: none !important;
}

/* Attempt to override any borders */
input:-webkit-autofill,
input:autofill {
  border: none !important;
  border-image: none !important;
  outline: none !important;
}

/* Target WebKit browsers specifically */
@media screen and (-webkit-min-device-pixel-ratio: 0) {
  input:-webkit-autofill {
    background-color: transparent !important;
  }
}

/* Firefox-specific override */
@-moz-document url-prefix() {
  input:-moz-autofill,
  input:-moz-autofill-preview {
    filter: none !important;
    background: transparent !important;
  }
}
</style>
