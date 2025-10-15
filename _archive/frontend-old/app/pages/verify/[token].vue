<template>
  <div class="min-h-screen flex items-center justify-center bg-cover bg-center">
    <div class="w-full max-w-md p-8 glassbase backdrop-blur-xl rounded-[4rem] text-white">
      <UiCard class="text-center">
        <h1 class="text-3xl font-bold mb-6 text-center font-display">Verify Your Account</h1>
        <p v-if="loading" class="text-center">Verifying your account...</p>
        <p v-if="error" class="mt-4 text-error text-sm text-center">{{ error }}</p>
        <p v-if="success" class="mt-4 text-success text-sm text-center">{{ success }}</p>
        <div v-if="success" class="mt-6 text-center">
          <NuxtLink to="/login" class="btn btn-primary"> Go to Login </NuxtLink>
        </div>
      </UiCard>
    </div>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const loading = ref(true);
const error = ref("");
const success = ref("");
const isLoading = ref(false);

const token = route.params.token as string;

async function handleVerification() {
  isLoading.value = true;
  error.value = "";
  success.value = "";

  try {
    const result: any = await authStore.verifyUser(token);
    if (result && result.success) {
      success.value = "Your account has been successfully verified!";
      setTimeout(() => router.push("/login"), 3000);
    } else {
      error.value = "We couldn't verify your account. Please try again.";
    }
  } catch (err: any) {
    console.error("Verification error:", err);
    switch (err.message) {
      case "VERIFICATION_FAILED":
        error.value = "Verification failed. Please try again.";
        break;
      default:
        error.value = `An error occurred: ${err.message || "Unknown error"}`;
    }
  } finally {
    isLoading.value = false;
  }
}

onMounted(async () => {
  try {
    const result: any = await authStore.verifyUser(token);
    if (result && result.is_verified) {
      success.value = "Your account has been successfully verified!";
    } else {
      error.value = "We couldn't verify your account. Please try again.";
    }
  } catch (err: any) {
    console.error("User verification error:", err);
    switch (err.message) {
      case "VERIFY_USER_ALREADY_VERIFIED":
        error.value = "This account has already been verified.";
        break;
      case "VERIFY_USER_BAD_TOKEN":
        error.value = "Invalid verification token. Please request a new one.";
        break;
      default:
        error.value = "An error occurred during verification.";
    }
  } finally {
    loading.value = false;
  }
});
</script>
