<template>
  <UDropdownMenu :items="dropdownItems" :content="{ align: 'center', collisionPadding: 12 }" :ui="{ content: collapsed ? 'w-48' : 'w-(--reka-dropdown-menu-trigger-width)' }">
    <UButton
      v-bind="{
        ...currentOrgForDisplay,
        label: collapsed ? undefined : currentOrgForDisplay?.label,
        trailingIcon: collapsed ? undefined : 'i-lucide-chevrons-up-down',
      }"
      color="neutral"
      variant="ghost"
      block
      :square="collapsed"
      class="data-[state=open]:bg-elevated"
      :class="[!collapsed && 'py-2']"
      :ui="{
        trailingIcon: 'text-dimmed',
      }"
      :loading="pending"
    />
  </UDropdownMenu>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from "@nuxt/ui";
import { useContextStore, SYSTEM_CONTEXT, type OrganizationContext } from "~/stores/context-store";

interface Props {
  collapsed?: boolean;
}

defineProps<Props>();

const contextStore = useContextStore();

// Entity type icon mapping
const entityTypeIcons: Record<string, string> = {
  PLATFORM: "i-lucide-shield",
  ORGANIZATION: "i-lucide-building-2",
  DIVISION: "i-lucide-building",
  BRANCH: "i-lucide-building",
  TEAM: "i-lucide-users",
  SYSTEM: "i-lucide-shield",
};

const getOrgIcon = (entityType: string): string => {
  return entityTypeIcons[entityType] || "i-lucide-building-2";
};

// Fetch organizations on mount
const { pending } = await useAsyncData("organizations", () => contextStore.fetchOrganizations());

// Debug logging
watch(
  () => contextStore.availableOrganizations,
  (orgs) => {
    console.log(
      "Team Switcher - Available organizations:",
      orgs.map((org) => org.name)
    );
  },
  { immediate: true }
);

watch(
  () => contextStore.selectedOrganization,
  (org) => {
    console.log("Team Switcher - Selected organization:", org?.name);
  },
  { immediate: true }
);

// Current organization for display
const currentOrgForDisplay = computed(() => {
  const org = contextStore.currentOrganization;
  return {
    label: org.name,
    avatar: {
      icon: getOrgIcon(org.entity_type),
      class: org.is_system ? "bg-purple-600 text-white" : "bg-primary text-primary-foreground",
    },
  };
});

// Dropdown items following Nuxt UI 3 pattern
const dropdownItems = computed<DropdownMenuItem[][]>(() => {
  // If no organizations loaded yet, show loading state
  if (pending.value || contextStore.availableOrganizations.length === 0) {
    return [
      [
        {
          label: "Loading organizations...",
          icon: "i-lucide-loader-2",
          disabled: true,
        },
      ],
    ];
  }

  const organizationItems: DropdownMenuItem[] = contextStore.availableOrganizations.map((org, index) => ({
    label: org.name,
    avatar: {
      icon: getOrgIcon(org.entity_type),
      class: org.is_system ? "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300" : "border",
    },
    suffix: org.is_system ? "Platform Admin" : org.entity_type,
    shortcuts: index < 9 ? [`⌘${index + 1}`] : undefined,
    onSelect: () => handleContextSwitch(org),
  }));

  const actionItems: DropdownMenuItem[] = [
    {
      label: "Create Organization",
      icon: "i-lucide-plus",
      disabled: true,
    },
  ];

  return [organizationItems, actionItems];
});

// Handle context switch
const handleContextSwitch = (org: OrganizationContext) => {
  console.log("Team Switcher: Switching to organization:", org.name, org);
  console.log("Team Switcher: Current context before switch:", contextStore.selectedOrganization?.name);

  contextStore.setSelectedOrganization(org);

  console.log("Team Switcher: Context after switch:", contextStore.selectedOrganization?.name);
  console.log("Team Switcher: Context headers:", contextStore.getContextHeaders);

  // Force a page refresh to reload data with new context
  // This ensures all API calls use the new context headers
  console.log("Team Switcher: Reloading page...");
  window.location.reload();
};

// Keyboard shortcuts for quick switching
onMounted(() => {
  const handleKeyPress = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key >= "1" && e.key <= "9") {
      e.preventDefault();
      const index = parseInt(e.key) - 1;
      const org = contextStore.availableOrganizations[index];
      if (org) {
        handleContextSwitch(org);
      }
    }
  };

  window.addEventListener("keydown", handleKeyPress);

  onUnmounted(() => {
    window.removeEventListener("keydown", handleKeyPress);
  });
});
</script>
