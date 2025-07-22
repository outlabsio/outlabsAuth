<script setup lang="ts">
import type { NavigationMenuItem } from "@nuxt/ui";

const route = useRoute();
const open = ref(false);
const userStore = useUserStore();
const debugStore = useDebugStore();
const authStore = useAuthStore();

// Initialize debug state
onMounted(() => {
  debugStore.loadDebugState();
});

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

  // Add platform management for system users
  if (userStore.isSystemUser) {
    mainLinks.push({
      label: "Platform",
      icon: "i-lucide-server",
      to: "/platform",
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
    <UDashboardSidebar id="default" v-model:open="open" collapsible resizable class="bg-elevated/25" :ui="{ footer: 'lg:border-t lg:border-default' }">
      <template #header="{ collapsed }">
        <TeamSwitcher :collapsed="collapsed" />
      </template>

      <template #default="{ collapsed }">
        <UDashboardSearchButton :collapsed="collapsed" class="bg-transparent ring-default" />

        <UNavigationMenu :collapsed="collapsed" :items="links[0]" orientation="vertical" tooltip popover />

        <UNavigationMenu :collapsed="collapsed" :items="links[1]" orientation="vertical" tooltip class="mt-auto" />
      </template>

      <template #footer="{ collapsed }">
        <UserMenu :collapsed="collapsed" />
      </template>
    </UDashboardSidebar>

    <UDashboardSearch :groups="groups" />

    <slot />

    <NotificationsSlideover />
    <DebugPanel />
  </UDashboardGroup>
</template>
