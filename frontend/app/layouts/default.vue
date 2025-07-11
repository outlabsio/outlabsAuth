<script setup lang="ts">
const route = useRoute();

const open = ref(false);

const userStore = useUserStore();

const links = computed(() => {
  const mainLinks = [
    {
      label: "Dashboard",
      icon: "i-lucide-layout-dashboard",
      to: "/dashboard",
      onSelect: () => {
        open.value = false;
      },
    },
    {
      label: "Entities",
      icon: "i-lucide-building",
      to: "/entities",
      onSelect: () => {
        open.value = false;
      },
    },
    {
      label: "Users",
      icon: "i-lucide-users",
      to: "/users",
      onSelect: () => {
        open.value = false;
      },
    },
    {
      label: "Roles",
      icon: "i-lucide-shield",
      to: "/roles",
      onSelect: () => {
        open.value = false;
      },
    },
    {
      label: "Permissions",
      icon: "i-lucide-key",
      to: "/permissions",
      onSelect: () => {
        open.value = false;
      },
    },
  ];

  // Add platform management for superusers
  if (userStore.isAdmin) {
    mainLinks.push({
      label: "Platforms",
      icon: "i-lucide-server",
      to: "/platforms",
      onSelect: () => {
        open.value = false;
      },
    });
  }

  return [
    mainLinks,
    [
      {
        label: "Documentation",
        icon: "i-lucide-book-open",
        to: "https://docs.outlabs.com/auth",
        target: "_blank",
      },
      {
        label: "API Reference",
        icon: "i-lucide-code",
        to: "/api-docs",
        target: "_blank",
      },
    ],
  ];
});

const groups: any[] = [];
</script>

<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar id="default" v-model:open="open" collapsible resizable class="bg-(--ui-bg-elevated)/25" :ui="{ footer: 'lg:border-t lg:border-(--ui-border)' }">
      <template #header="{ collapsed }">
        <UayaLogo :collapsed="collapsed" />
      </template>

      <template #default="{ collapsed }">
        <UDashboardSearchButton :collapsed="collapsed" class="bg-transparent ring-(--ui-border)" />

        <UNavigationMenu :collapsed="collapsed" :items="links[0]" orientation="vertical" />

        <UNavigationMenu :collapsed="collapsed" :items="links[1]" orientation="vertical" class="mt-auto" />
      </template>

      <template #footer="{ collapsed }">
        <UserMenu :collapsed="collapsed" />
      </template>
    </UDashboardSidebar>

    <UDashboardSearch :groups="groups" />

    <slot />

    <NotificationsSlideover />
  </UDashboardGroup>
</template>
