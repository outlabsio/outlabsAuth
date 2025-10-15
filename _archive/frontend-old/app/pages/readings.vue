<script setup lang="ts">
const route = useRoute();

// Define links for the readings navigation menu
const links = computed(() => [
  [
    {
      label: "User Readings",
      icon: "i-lucide-users",
      to: "/readings",
      exact: true,
    },
    {
      label: "Anonymous",
      icon: "i-lucide-user-x",
      to: "/readings/anonymous",
    },
    {
      label: "Analytics",
      icon: "i-lucide-bar-chart-3",
      to: "/readings/analytics",
    },
  ],
]);

// Dynamic page title based on current route
const pageTitle = computed(() => {
  const routeName = route.name?.toString() || "";

  if (routeName === "readings-index" || routeName === "readings") {
    return "User Readings";
  } else if (routeName === "readings-anonymous") {
    return "Anonymous Readings";
  } else if (routeName === "readings-analytics") {
    return "Reading Analytics";
  }

  return "Readings";
});
</script>

<template>
  <UDashboardPanel :ui="{ body: 'lg:py-12' }">
    <template #header>
      <UDashboardNavbar :title="pageTitle">
        <template #leading>
          <UButton to="/" icon="i-lucide-arrow-left" color="neutral" variant="ghost" class="-ml-2.5" aria-label="Back to dashboard" />
        </template>

        <template #right>
          <div class="flex items-center gap-3">
            <!-- Add any action buttons here if needed in the future -->
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
</template>
