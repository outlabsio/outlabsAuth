<script setup lang="ts">
import type { NavigationMenuItem } from "@nuxt/ui";

const route = useRoute();
const authStore = useAuthStore();
const permissionsStore = usePermissionsStore();

const open = ref(false);
const canAccess = (permission: string) =>
    authStore.currentUser?.is_superuser || permissionsStore.hasPermission(permission);

const canReadUsers = computed(() => canAccess("user:read"));
const canReadRoles = computed(() => canAccess("role:read"));
const canReadPermissions = computed(() => canAccess("permission:read"));
const canReadEntities = computed(() => canAccess("entity:read"));
const canUseApiKeys = computed(
    () => authStore.features.api_keys && authStore.isAuthenticated,
);

const dashboardLink: NavigationMenuItem = {
    label: "Dashboard",
    icon: "i-lucide-layout-dashboard",
    to: "/dashboard",
    exact: true,
    onSelect: () => {
        open.value = false;
    },
};

const usersLink: NavigationMenuItem = {
    label: "Users",
    icon: "i-lucide-users",
    to: "/users",
    onSelect: () => {
        open.value = false;
    },
};

const rolesLink: NavigationMenuItem = {
    label: "Roles",
    icon: "i-lucide-shield",
    to: "/roles",
    onSelect: () => {
        open.value = false;
    },
};

const permissionsLink: NavigationMenuItem = {
    label: "Permissions",
    icon: "i-lucide-lock",
    to: "/permissions",
    onSelect: () => {
        open.value = false;
    },
};

const apiKeysLink: NavigationMenuItem = {
    label: "API Keys",
    icon: "i-lucide-key",
    to: "/api-keys",
    onSelect: () => {
        open.value = false;
    },
};

// EnterpriseRBAC-only links
const enterpriseLinks = [
    {
        label: "Entities",
        icon: "i-lucide-building",
        to: "/entities",
        onSelect: () => {
            open.value = false;
        },
    },
];

// Main navigation links - dynamically composed based on preset
const links = computed(() => {
    const mainLinks: NavigationMenuItem[] = [dashboardLink];

    if (canReadUsers.value) {
        mainLinks.push(usersLink);
    }
    if (canReadRoles.value) {
        mainLinks.push(rolesLink);
    }
    if (canReadPermissions.value) {
        mainLinks.push(permissionsLink);
    }
    if (canUseApiKeys.value) {
        mainLinks.push(apiKeysLink);
    }

    // Insert Entities link after Roles if EnterpriseRBAC
    if (authStore.isEnterpriseRBAC && canReadEntities.value) {
        const rolesIndex = mainLinks.findIndex((link) => link.to === "/roles");
        if (rolesIndex >= 0) {
            mainLinks.splice(rolesIndex + 1, 0, ...enterpriseLinks);
        } else {
            mainLinks.push(...enterpriseLinks);
        }
    }

    // Build settings children
    const settingsChildren = [
        {
            label: "General",
            to: "/settings",
            exact: true,
            onSelect: () => {
                open.value = false;
            },
        },
        {
            label: "Profile",
            to: "/settings/profile",
            onSelect: () => {
                open.value = false;
            },
        },
        {
            label: "Security",
            to: "/settings/security",
            onSelect: () => {
                open.value = false;
            },
        },
        {
            label: "Password",
            to: "/settings/password",
            onSelect: () => {
                open.value = false;
            },
        },
    ];

    // Add Entity Types settings for superusers in EnterpriseRBAC mode
    if (authStore.isEnterpriseRBAC && authStore.currentUser?.is_superuser) {
        settingsChildren.push({
            label: "Entity Types",
            to: "/settings/entity-types",
            onSelect: () => {
                open.value = false;
            },
        });
    }

    return [
        [...mainLinks],
        [
            {
                label: "Settings",
                to: "/settings",
                icon: "i-lucide-settings",
                defaultOpen: false,
                type: "trigger",
                children: settingsChildren,
            },
        ],
        [
            {
                label: "Documentation",
                icon: "i-lucide-book-open",
                to: "https://github.com/outlabs/outlabs-auth/tree/main/docs",
                target: "_blank",
            },
            {
                label: "Help & Support",
                icon: "i-lucide-help-circle",
                to: "https://github.com/outlabs/outlabs-auth/discussions",
                target: "_blank",
            },
        ],
    ] satisfies NavigationMenuItem[][];
});

// Search groups for global search
const groups = computed(() => {
    const shortcuts = [
        {
            id: "g-d",
            label: "Go to Dashboard",
            suffix: "G D",
        },
    ];

    if (canReadUsers.value) {
        shortcuts.push({
            id: "g-u",
            label: "Go to Users",
            suffix: "G U",
        });
    }

    if (canReadRoles.value) {
        shortcuts.push({
            id: "g-r",
            label: "Go to Roles",
            suffix: "G R",
        });
    }

    // Add Entities shortcut for EnterpriseRBAC
    if (authStore.isEnterpriseRBAC && canReadEntities.value) {
        shortcuts.push({
            id: "g-e",
            label: "Go to Entities",
            suffix: "G E",
        });
    }

    return [
        {
            id: "links",
            label: "Go to",
            items: links.value
                .flat()
                .filter(
                    (item): item is NavigationMenuItem =>
                        !!item && !("children" in item),
                ),
        },
        {
            id: "shortcuts",
            label: "Shortcuts",
            items: shortcuts,
        },
    ];
});
</script>

<template>
    <UDashboardGroup unit="rem">
        <UDashboardSidebar
            id="default"
            v-model:open="open"
            collapsible
            resizable
            class="bg-elevated/25"
            :ui="{ footer: 'lg:border-t lg:border-default' }"
        >
            <template #header="{ collapsed }">
                <EntityContextMenu :collapsed="collapsed" />
            </template>

            <template #default="{ collapsed }">
                <UDashboardSearchButton
                    :collapsed="collapsed"
                    class="bg-transparent ring-default"
                />

                <UNavigationMenu
                    :collapsed="collapsed"
                    :items="links[0]"
                    orientation="vertical"
                    tooltip
                    popover
                />

                <UNavigationMenu
                    :collapsed="collapsed"
                    :items="links[1]"
                    orientation="vertical"
                    tooltip
                    popover
                />

                <UNavigationMenu
                    :collapsed="collapsed"
                    :items="links[2]"
                    orientation="vertical"
                    tooltip
                    class="mt-auto"
                />

                <!-- Mode Indicator -->
                <div
                    v-if="!collapsed && authStore.state.isConfigLoaded"
                    class="px-3 py-2 mt-2 border-t border-default"
                >
                    <div class="flex items-center gap-2 text-xs text-muted">
                        <UIcon
                            :name="
                                authStore.isEnterpriseRBAC
                                    ? 'i-lucide-building-2'
                                    : 'i-lucide-box'
                            "
                            class="w-3 h-3"
                        />
                        <span>{{
                            authStore.state.config?.preset || "Unknown"
                        }}</span>
                    </div>
                </div>
                <div
                    v-else-if="collapsed && authStore.state.isConfigLoaded"
                    class="flex justify-center py-2 mt-2 border-t border-default"
                >
                    <UTooltip
                        :text="authStore.state.config?.preset || 'Unknown'"
                    >
                        <UIcon
                            :name="
                                authStore.isEnterpriseRBAC
                                    ? 'i-lucide-building-2'
                                    : 'i-lucide-box'
                            "
                            class="w-4 h-4 text-muted"
                        />
                    </UTooltip>
                </div>
            </template>

            <template #footer="{ collapsed }">
                <UserMenu :collapsed="collapsed" />
            </template>
        </UDashboardSidebar>

        <UDashboardSearch :groups="groups" />

        <UDashboardPanel class="flex-1 flex flex-col overflow-hidden">
            <slot />
        </UDashboardPanel>
    </UDashboardGroup>
</template>
