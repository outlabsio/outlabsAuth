<script setup lang="ts">
import type { DropdownMenuItem } from "@nuxt/ui";

defineProps<{
  collapsed?: boolean;
}>();

const colorMode = useColorMode();
const appConfig = useAppConfig();
const authStore = useAuthStore();
const userStore = useUserStore();
const contextStore = useContextStore();
const debugStore = useDebugStore();
const router = useRouter();

const colors = ["red", "orange", "amber", "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose"];
const neutrals = ["slate", "gray", "zinc", "neutral", "stone"];

// Generate avatar from name if available, otherwise use default
const avatarSrc = computed(() => {
  // We don't have avatar in the user store, so we'll use a default
  return "https://ui.shadcn.com/avatars/01.png";
});

const user = computed(() => ({
  name: userStore.name || "User",
  avatar: {
    src: avatarSrc.value,
    alt: userStore.name || "User",
  },
}));

const handleLogout = async () => {
  await authStore.logout();
  router.push("/login");
};

// Check if user is system admin
const isSystemAdmin = computed(() => {
  // Use userStore which has the proper getters
  const isAdmin = userStore.email === 'system@outlabs.io' || userStore.isSystemUser || userStore.isAdmin;
  console.log('[UserMenu] System admin check:', {
    email: userStore.email,
    isSystemUser: userStore.isSystemUser,
    isAdmin: userStore.isAdmin,
    result: isAdmin
  });
  return isAdmin;
});

const items = computed<DropdownMenuItem[][]>(() => {
  console.log('[UserMenu] Building menu items, isSystemAdmin:', isSystemAdmin.value);
  
  const menuItems: DropdownMenuItem[][] = [
    [
      {
        type: "label",
        label: user.value.name,
        avatar: user.value.avatar,
      },
    ],
    [
      {
        label: "Profile",
        icon: "i-lucide-user",
        to: "/profile",
      },
      {
        label: "Settings",
        icon: "i-lucide-settings",
        to: "/settings",
      },
    ],
  ];

  // Add debug section for system admins
  if (isSystemAdmin.value) {
    console.log('[UserMenu] Adding debug panel menu item');
    menuItems.push([
      {
        label: "Debug Panel",
        icon: "i-lucide-bug",
        type: "checkbox",
        checked: debugStore.enabled,
        onUpdateChecked(checked: boolean) {
          console.log('[UserMenu] Debug panel toggled:', checked);
          debugStore.toggleDebug();
        },
        onSelect(e: Event) {
          e.preventDefault();
        },
      },
    ]);
  } else {
    console.log('[UserMenu] Not adding debug panel - user is not system admin');
  }

  // Continue with the rest of the menu items
  menuItems.push(
  [
    {
      label: "Theme",
      icon: "i-lucide-palette",
      children: [
        {
          label: "Primary",
          slot: "chip",
          chip: appConfig.ui.colors.primary,
          content: {
            align: "center",
            collisionPadding: 16,
          },
          children: colors.map((color) => ({
            label: color,
            chip: color,
            slot: "chip",
            checked: appConfig.ui.colors.primary === color,
            type: "checkbox",
            onSelect: (e) => {
              e.preventDefault();

              appConfig.ui.colors.primary = color;
            },
          })),
        },
        {
          label: "Neutral",
          slot: "chip",
          chip: appConfig.ui.colors.neutral,
          content: {
            align: "end",
            collisionPadding: 16,
          },
          children: neutrals.map((color) => ({
            label: color,
            chip: color,
            slot: "chip",
            type: "checkbox",
            checked: appConfig.ui.colors.neutral === color,
            onSelect: (e) => {
              e.preventDefault();

              appConfig.ui.colors.neutral = color;
            },
          })),
        },
      ],
    },
    {
      label: "Appearance",
      icon: "i-lucide-sun-moon",
      children: [
        {
          label: "Light",
          icon: "i-lucide-sun",
          type: "checkbox",
          checked: colorMode.value === "light",
          onSelect(e: Event) {
            e.preventDefault();

            colorMode.preference = "light";
          },
        },
        {
          label: "Dark",
          icon: "i-lucide-moon",
          type: "checkbox",
          checked: colorMode.value === "dark",
          onUpdateChecked(checked: boolean) {
            if (checked) {
              colorMode.preference = "dark";
            }
          },
          onSelect(e: Event) {
            e.preventDefault();
          },
        },
      ],
    },
  ],
    [
      {
        label: userStore.isAdmin ? "Admin Dashboard" : "Dashboard",
        icon: "i-lucide-layout-dashboard",
        to: userStore.isAdmin ? "/admin" : "/dashboard",
      },
      {
        label: "Documentation",
        icon: "i-lucide-book-open",
        to: "/docs",
        target: "_blank",
      },
    ],
    [
      {
        label: "Log out",
        icon: "i-lucide-log-out",
        onClick: handleLogout,
      },
    ],
  );

  return menuItems;
});
</script>

<template>
  <UDropdownMenu :items="items" :content="{ align: 'center', collisionPadding: 12 }" :ui="{ content: collapsed ? 'w-48' : 'w-(--reka-dropdown-menu-trigger-width)' }">
    <UButton
      v-bind="{
        ...user,
        label: collapsed ? undefined : user?.name,
        trailingIcon: collapsed ? undefined : 'i-lucide-chevrons-up-down',
      }"
      color="neutral"
      variant="ghost"
      block
      :square="collapsed"
      class="data-[state=open]:bg-(--ui-bg-elevated)"
      :ui="{
        trailingIcon: 'text-(--ui-text-dimmed)',
      }"
    />

    <template #chip-leading="{ item }">
      <span :style="{ '--chip': `var(--color-${(item as any).chip}-400)` }" class="ms-0.5 size-2 rounded-full bg-(--chip)" />
    </template>
  </UDropdownMenu>
</template>
