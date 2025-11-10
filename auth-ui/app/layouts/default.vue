<script setup lang="ts">
import type { NavigationMenuItem } from "@nuxt/ui";

const route = useRoute();
const authStore = useAuthStore();

const open = ref(false);

// Base navigation links (all presets)
const baseLinks = [
    {
        label: "Dashboard",
        icon: "i-lucide-layout-dashboard",
        to: "/",
        exact: true,
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
        icon: "i-lucide-lock",
        to: "/permissions",
        onSelect: () => {
            open.value = false;
        },
    },
    {
        label: "API Keys",
        icon: "i-lucide-key",
        to: "/api-keys",
        onSelect: () => {
            open.value = false;
        },
    },
];

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
    const mainLinks = [...baseLinks];

    // Insert Entities link after Roles if EnterpriseRBAC
    if (authStore.isEnterpriseRBAC) {
        const rolesIndex = mainLinks.findIndex((link) => link.to === "/roles");
        mainLinks.splice(rolesIndex + 1, 0, ...enterpriseLinks);
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
                children: [
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
                ],
            },
        ],
        [
            {
                label: "Documentation",
                icon: "i-lucide-book-open",
                to: "https://github.com/yourusername/outlabsauth",
                target: "_blank",
            },
            {
                label: "Help & Support",
                icon: "i-lucide-help-circle",
                to: "https://github.com/yourusername/outlabsauth/issues",
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
        {
            id: "g-u",
            label: "Go to Users",
            suffix: "G U",
        },
        {
            id: "g-r",
            label: "Go to Roles",
            suffix: "G R",
        },
    ];

    // Add Entities shortcut for EnterpriseRBAC
    if (authStore.isEnterpriseRBAC) {
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
            items: links.value.flat().filter((item) => !("children" in item)),
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
            </template>

            <template #footer="{ collapsed }">
                <UserMenu :collapsed="collapsed" />
            </template>
        </UDashboardSidebar>

        <UDashboardSearch :groups="groups" />

        <slot />
    </UDashboardGroup>
</template>
