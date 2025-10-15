<script setup lang="ts">
const route = useRoute();
const toast = useToast();
const userDetailsStore = useUserDetailsStore();

const userId = computed(() => route.params.user_id as string);

// Fetch user details for the header
onMounted(() => {
  if (userId.value) {
    userDetailsStore.fetchUserDetails(userId.value);
  }
});

// Watch for route changes
watch(
  () => route.params.user_id,
  (newId) => {
    if (newId && typeof newId === "string") {
      userDetailsStore.fetchUserDetails(newId);
    }
  },
  { immediate: false }
);

// Define links for the user navigation menu
const links = computed(() => [
  [
    {
      label: "Profile",
      icon: "i-lucide-user",
      to: `/user/${userId.value}`,
      exact: true,
    },
    {
      label: "Readings",
      icon: "i-lucide-book-open",
      to: `/user/${userId.value}/readings`,
    },
    {
      label: "Transactions",
      icon: "i-lucide-receipt",
      to: `/user/${userId.value}/transactions`,
    },
    {
      label: "Activity",
      icon: "i-lucide-activity",
      to: `/user/${userId.value}/activity`,
    },
  ],
]);

// Update page title to show user name when available
const pageTitle = computed(() => {
  return userDetailsStore.user?.name || `User ${userId.value}`;
});

// Grant Tokens Modal
const showGrantModal = ref(false);
const grantForm = ref({
  token_amount: 0,
  reason: "",
  description: "",
  source: "admin",
});

const sourceOptions = [
  { label: "Admin", value: "admin" },
  { label: "Compensation", value: "compensation" },
  { label: "System", value: "system" },
  { label: "Promo Code", value: "promo_code" },
  { label: "Referral", value: "referral" },
  { label: "Milestone", value: "milestone" },
];

// Handle grant tokens
const handleGrantTokens = async () => {
  if (!userId.value || !grantForm.value.token_amount || !grantForm.value.reason) {
    toast.add({
      title: "Missing Information",
      description: "Please fill in all required fields.",
      color: "error",
    });
    return;
  }

  try {
    await userDetailsStore.grantTokensToUser({
      target_user_id: userId.value,
      token_amount: grantForm.value.token_amount,
      reason: grantForm.value.reason,
      description: grantForm.value.description,
      source: grantForm.value.source,
      category: "admin",
    });

    toast.add({
      title: "Tokens Granted Successfully",
      description: `Successfully granted ${grantForm.value.token_amount} tokens to the user.`,
      color: "success",
    });

    // Reset form and close modal
    grantForm.value = {
      token_amount: 0,
      reason: "",
      description: "",
      source: "admin",
    };
    showGrantModal.value = false;

    // Refresh token grants if on profile page
    if (route.name === "user-user_id") {
      await userDetailsStore.fetchUserTokenGrants(userId.value);
    }
  } catch (error: any) {
    toast.add({
      title: "Error Granting Tokens",
      description: error.message || "Could not grant tokens to the user.",
      color: "error",
    });
  }
};
</script>

<template>
  <UDashboardPanel :ui="{ body: 'lg:py-12' }">
    <template #header>
      <UDashboardNavbar :title="pageTitle">
        <template #leading>
          <UButton to="/users/all" icon="i-lucide-arrow-left" color="neutral" variant="ghost" class="-ml-2.5" aria-label="Back to users" />
        </template>

        <template #right>
          <div class="flex items-center gap-3">
            <UButton v-if="userDetailsStore.user" icon="i-lucide-coins" label="Grant Tokens" color="primary" variant="solid" size="sm" @click="showGrantModal = true" />
          </div>
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <UNavigationMenu :items="links" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <!-- Nested routes will render here -->
      <div class="flex flex-col gap-4 sm:gap-6 lg:gap-12 w-full mx-auto">
        <NuxtPage />
      </div>
    </template>
  </UDashboardPanel>

  <!-- Grant Tokens Modal -->
  <UModal v-model:open="showGrantModal" title="Grant Tokens" description="Grant tokens to this user with a reason">
    <template #header>
      <div class="flex items-start justify-between w-full">
        <div class="flex items-center gap-3">
          <div class="flex items-center justify-center w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900/50 flex-shrink-0">
            <UIcon name="i-lucide-coins" class="h-5 w-5 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <h3 class="text-lg font-semibold">Grant Tokens</h3>
            <p class="text-sm text-muted">Add tokens to {{ userDetailsStore.user?.name || "this user" }}'s account</p>
          </div>
        </div>
        <UButton color="neutral" variant="ghost" icon="i-lucide-x" class="-my-1 -mr-1" @click="showGrantModal = false" />
      </div>
    </template>

    <template #body>
      <div class="p-6">
        <UForm :state="grantForm" class="space-y-8">
          <!-- Grant Form Fields -->
          <div class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <UFormField label="Token Amount" name="token_amount" required help="Enter the number of tokens to grant (1-10,000)" class="w-full">
                <UInput
                  v-model.number="grantForm.token_amount"
                  type="number"
                  min="1"
                  max="10000"
                  placeholder="Enter amount"
                  :disabled="userDetailsStore.grantingTokens"
                  size="lg"
                  trailing-icon="i-lucide-coins"
                  class="w-full"
                />
              </UFormField>

              <UFormField label="Source" name="source" help="Select the source category for this grant" class="w-full">
                <USelect v-model="grantForm.source" :items="sourceOptions" :disabled="userDetailsStore.grantingTokens" size="lg" trailing-icon="i-lucide-tag" class="w-full" />
              </UFormField>
            </div>

            <UFormField label="Reason" name="reason" required help="Provide a clear reason for this token grant (visible to user)" class="w-full">
              <UInput
                v-model="grantForm.reason"
                placeholder="e.g., Customer service compensation for service disruption"
                :disabled="userDetailsStore.grantingTokens"
                size="lg"
                trailing-icon="i-lucide-message-circle"
                class="w-full"
              />
            </UFormField>

            <UFormField label="Description / Internal Note" name="description" help="This note is for internal records only and will not be shown to the user." class="w-full">
              <UTextarea
                v-model="grantForm.description"
                placeholder="Enter internal notes about this grant, e.g., specific incident ID, admin who approved, etc."
                :disabled="userDetailsStore.grantingTokens"
                :rows="4"
                class="w-full"
                resize
              />
            </UFormField>
          </div>

          <!-- Grant Preview Section -->
          <div v-if="grantForm.token_amount > 0" class="space-y-4">
            <div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div class="text-center">
                  <div class="font-medium text-gray-500 dark:text-gray-400">User</div>
                  <div class="text-base font-semibold text-gray-900 dark:text-gray-100">
                    {{ userDetailsStore.user?.name || "Selected User" }}
                  </div>
                </div>
                <div class="text-center">
                  <div class="font-medium text-gray-500 dark:text-gray-400">Grant Amount</div>
                  <div class="text-xl font-bold text-success">+{{ grantForm.token_amount }} tokens</div>
                </div>
                <div class="text-center">
                  <div class="font-medium text-gray-500 dark:text-gray-400">Source</div>
                  <div class="text-base font-semibold text-gray-900 dark:text-gray-100 capitalize">
                    {{ sourceOptions.find((opt) => opt.value === grantForm.source)?.label || grantForm.source }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </UForm>
      </div>
    </template>

    <template #footer>
      <UButton type="button" color="neutral" variant="ghost" @click="showGrantModal = false" :disabled="userDetailsStore.grantingTokens"> Cancel </UButton>
      <UButton
        type="submit"
        color="success"
        :loading="userDetailsStore.grantingTokens"
        :disabled="!grantForm.token_amount || !grantForm.reason"
        @click="handleGrantTokens"
        icon="i-lucide-check"
        class="ml-auto"
      >
        Grant Tokens
      </UButton>
    </template>
  </UModal>
</template>
