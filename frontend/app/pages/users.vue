<script setup lang="ts">
const links = [
  [
    {
      label: "All Users",
      icon: "i-lucide-users",
      to: "/users/all",
    },
    {
      label: "Team Members",
      icon: "i-lucide-user",
      to: "/users/team",
    },
    {
      label: "Team Invites",
      icon: "i-lucide-mail-plus",
      to: "/users/invites",
    },
    {
      label: "Permissions",
      icon: "i-lucide-shield",
      to: "/users/permissions",
    },
  ],
  [
    {
      label: "Uaya",
      icon: "i-lucide-book-open",
      to: "https://uaya.org",
      target: "_blank",
    },
    {
      label: "Learn",
      icon: "i-lucide-book-open",
      to: "https://learn.uaya.org",
      target: "_blank",
    },
  ],
];
</script>

<template>
  <UDashboardPanel id="settings" :ui="{ body: 'lg:py-6' }">
    <template #header>
      <UDashboardNavbar title="Settings">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <!-- NOTE: The `-mx-1` class is used to align with the `DashboardSidebarCollapse` button here. -->
        <UNavigationMenu :items="links" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-4 sm:gap-6 lg:gap-12 w-full">
        <NuxtPage />
      </div>
    </template>
  </UDashboardPanel>
</template>
