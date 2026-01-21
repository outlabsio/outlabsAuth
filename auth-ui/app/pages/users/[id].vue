<script setup lang="ts">
/**
 * User Detail Layout Wrapper
 * Provides tab navigation and user context for nested routes
 * Follows Nuxt nested routes pattern
 */

const route = useRoute();
const userStore = useUserStore();
const authStore = useAuthStore();

// Extract user ID from route params
const userId = computed(() => route.params.id as string);

// Check if entity hierarchy is enabled (EnterpriseRBAC mode)
const hasEntityHierarchy = computed(
    () => authStore.state.config?.features?.entity_hierarchy === true,
);

// Fetch user data when route changes
watch(
    userId,
    async (id) => {
        if (id) {
            await userStore.fetchUser(id);
            // Prefetch roles and permissions
            const prefetchPromises = [
                userStore.fetchUserRoles(id),
                userStore.fetchUserPermissions(id),
            ];
            // Also prefetch memberships if entity hierarchy is enabled
            if (hasEntityHierarchy.value) {
                prefetchPromises.push(userStore.fetchUserMemberships(id));
            }
            await Promise.all(prefetchPromises);
        }
    },
    { immediate: true },
);

// User data from store
const user = computed(() => userStore.currentUser);
const isLoading = computed(() => userStore.isLoading);

// Tab items with values for route sync
const tabItems = computed(() => {
    const items = [
        {
            label: "Basic Info",
            icon: "i-lucide-user",
            value: "info",
        },
        {
            label: "Roles",
            icon: "i-lucide-shield",
            value: "roles",
        },
        {
            label: "Permissions",
            icon: "i-lucide-lock",
            value: "permissions",
        },
    ];

    // Add Entities tab only in EnterpriseRBAC mode
    if (hasEntityHierarchy.value) {
        items.push({
            label: "Entities",
            icon: "i-lucide-building-2",
            value: "entities",
        });
    }

    items.push({
        label: "Activity",
        icon: "i-lucide-activity",
        value: "activity",
    });

    return items;
});

// Tab navigation synced with route
const currentTab = computed({
    get: () => {
        const path = route.path;
        if (path.endsWith("/roles")) return "roles";
        if (path.endsWith("/permissions")) return "permissions";
        if (path.endsWith("/entities")) return "entities";
        if (path.endsWith("/activity")) return "activity";
        return "info";
    },
    set: (value: string) => {
        const routes: Record<string, string> = {
            info: `/users/${userId.value}`,
            roles: `/users/${userId.value}/roles`,
            permissions: `/users/${userId.value}/permissions`,
            entities: `/users/${userId.value}/entities`,
            activity: `/users/${userId.value}/activity`,
        };
        navigateTo(routes[value]);
    },
});

// Status badge color
const statusColor = computed(() => {
    if (!user.value) return "neutral";
    switch (user.value.status) {
        case "active":
            return "success";
        case "suspended":
            return "warning";
        case "banned":
            return "error";
        case "deleted":
            return "neutral";
        default:
            return "neutral";
    }
});

// Cleanup on unmount
onUnmounted(() => {
    userStore.clearUser();
});
</script>

<template>
    <div class="flex flex-col h-full">
        <!-- Loading State -->
        <div
            v-if="isLoading && !user"
            class="flex items-center justify-center flex-1"
        >
            <div class="text-center">
                <UIcon
                    name="i-lucide-loader-2"
                    class="w-8 h-8 animate-spin text-primary mb-2"
                />
                <p class="text-sm text-muted">Loading user...</p>
            </div>
        </div>

        <!-- User Content -->
        <template v-else-if="user">
            <!-- Fixed Header Section -->
            <div class="flex-shrink-0 border-b border-default bg-default">
                <div class="container mx-auto px-4 py-6">
                    <div class="flex items-start justify-between">
                        <!-- User Info -->
                        <div class="flex items-start gap-4">
                            <!-- Avatar Placeholder -->
                            <div
                                class="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center"
                            >
                                <UIcon
                                    name="i-lucide-user"
                                    class="w-8 h-8 text-primary"
                                />
                            </div>

                            <div>
                                <div class="flex items-center gap-2 mb-1">
                                    <h1
                                        class="text-2xl font-bold text-foreground"
                                    >
                                        {{
                                            user.full_name ||
                                            user.username ||
                                            user.email
                                        }}
                                    </h1>
                                    <UBadge
                                        :color="statusColor"
                                        variant="subtle"
                                    >
                                        {{ user.status }}
                                    </UBadge>
                                    <UBadge
                                        v-if="user.is_superuser"
                                        color="primary"
                                        variant="subtle"
                                    >
                                        <UIcon
                                            name="i-lucide-shield"
                                            class="w-3 h-3 mr-1"
                                        />
                                        Superuser
                                    </UBadge>
                                </div>
                                <p class="text-sm text-muted">
                                    {{ user.email }}
                                </p>
                                <p
                                    v-if="
                                        user.username &&
                                        user.username !== user.email
                                    "
                                    class="text-xs text-muted"
                                >
                                    @{{ user.username }}
                                </p>
                            </div>
                        </div>

                        <!-- Actions -->
                        <div class="flex gap-2">
                            <UButton
                                icon="i-lucide-arrow-left"
                                label="Back to Users"
                                variant="outline"
                                color="neutral"
                                @click="navigateTo('/users')"
                            />
                        </div>
                    </div>
                </div>

                <!-- Tab Navigation -->
                <div class="container mx-auto px-4">
                    <UTabs
                        v-model="currentTab"
                        :items="tabItems"
                        :content="false"
                        variant="link"
                        color="primary"
                    />
                </div>
            </div>

            <!-- Scrollable Tab Content -->
            <div class="flex-1 overflow-y-auto">
                <div class="container mx-auto px-4 py-6">
                    <NuxtPage :user="user" />
                </div>
            </div>
        </template>

        <!-- Error State -->
        <div v-else class="flex items-center justify-center flex-1">
            <div class="text-center">
                <UIcon
                    name="i-lucide-alert-circle"
                    class="w-12 h-12 text-error mb-4"
                />
                <p class="text-lg font-semibold text-foreground mb-2">
                    User not found
                </p>
                <p class="text-sm text-muted mb-4">
                    The requested user could not be found.
                </p>
                <UButton
                    label="Back to Users"
                    variant="outline"
                    @click="navigateTo('/users')"
                />
            </div>
        </div>
    </div>
</template>
