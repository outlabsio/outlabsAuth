<template>
    <UDashboardPanel id="dashboard">
        <template #header>
            <UDashboardNavbar title="Dashboard" :ui="{ right: 'gap-3' }">
                <template #leading>
                    <UDashboardSidebarCollapse />
                </template>

                <template #right>
                    <UDropdownMenu :items="quickActions" :content="{ align: 'end' }">
                        <UButton
                            icon="i-lucide-plus"
                            trailing-icon="i-lucide-chevron-down"
                            size="md"
                            label="Quick Action"
                            class="rounded-full"
                        />
                    </UDropdownMenu>
                </template>
            </UDashboardNavbar>
        </template>

        <template #body>
            <div class="space-y-6">
                <!-- Welcome Section -->
                <div>
                    <h2 class="text-lg font-semibold text-highlighted mb-1">
                        Welcome back,
                        {{
                            authStore.currentUser?.full_name ||
                            authStore.currentUser?.email
                        }}
                    </h2>
                    <p class="text-sm text-muted">
                        Here's what's happening with your authentication system
                        today.
                    </p>
                </div>

                <!-- Stats Cards -->
                <div
                    class="grid grid-cols-1 gap-4"
                    :class="
                        authStore.isEnterpriseRBAC
                            ? 'md:grid-cols-3'
                            : 'md:grid-cols-2'
                    "
                >
                    <UCard>
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-sm text-muted mb-1">
                                    Total Users
                                </p>
                                <p class="text-3xl font-bold text-highlighted">
                                    {{ stats.users || 0 }}
                                </p>
                            </div>
                            <UIcon
                                name="i-lucide-users"
                                class="size-10 text-primary"
                            />
                        </div>
                    </UCard>

                    <UCard>
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-sm text-muted mb-1">
                                    Active Roles
                                </p>
                                <p class="text-3xl font-bold text-highlighted">
                                    {{ stats.roles || 0 }}
                                </p>
                            </div>
                            <UIcon
                                name="i-lucide-shield"
                                class="size-10 text-primary"
                            />
                        </div>
                    </UCard>

                    <!-- Entities card - EnterpriseRBAC only -->
                    <UCard v-if="authStore.isEnterpriseRBAC">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-sm text-muted mb-1">Entities</p>
                                <p class="text-3xl font-bold text-highlighted">
                                    {{ stats.entities || 0 }}
                                </p>
                            </div>
                            <UIcon
                                name="i-lucide-building"
                                class="size-10 text-primary"
                            />
                        </div>
                    </UCard>
                </div>

                <!-- Recent Activity Section -->
                <UCard>
                    <template #header>
                        <h3 class="text-base font-semibold text-highlighted">
                            Recent Activity
                        </h3>
                    </template>

                    <div class="space-y-3">
                        <p class="text-sm text-muted">
                            No recent activity to display.
                        </p>
                    </div>
                </UCard>

                <!-- Quick Actions -->
                <div
                    class="grid grid-cols-1 md:grid-cols-2 gap-4"
                    :class="
                        authStore.isEnterpriseRBAC
                            ? 'lg:grid-cols-4'
                            : 'lg:grid-cols-3'
                    "
                >
                    <UButton
                        to="/users"
                        color="neutral"
                        variant="outline"
                        block
                        size="lg"
                    >
                        <template #leading>
                            <UIcon name="i-lucide-user-plus" class="size-5" />
                        </template>
                        Add User
                    </UButton>

                    <UButton
                        to="/roles"
                        color="neutral"
                        variant="outline"
                        block
                        size="lg"
                    >
                        <template #leading>
                            <UIcon name="i-lucide-shield-plus" class="size-5" />
                        </template>
                        Create Role
                    </UButton>

                    <!-- New Entity button - EnterpriseRBAC only -->
                    <UButton
                        v-if="authStore.isEnterpriseRBAC"
                        to="/entities"
                        color="neutral"
                        variant="outline"
                        block
                        size="lg"
                    >
                        <template #leading>
                            <UIcon name="i-lucide-building-2" class="size-5" />
                        </template>
                        New Entity
                    </UButton>

                    <UButton
                        to="/api-keys"
                        color="neutral"
                        variant="outline"
                        block
                        size="lg"
                    >
                        <template #leading>
                            <UIcon name="i-lucide-key" class="size-5" />
                        </template>
                        Generate API Key
                    </UButton>
                </div>
            </div>
        </template>
    </UDashboardPanel>
</template>

<script setup lang="ts">
// Stores
const authStore = useAuthStore();
const contextStore = useContextStore();
const usersStore = useUsersStore();
const rolesStore = useRolesStore();
const entitiesStore = useEntitiesStore();

// Computed stats from stores
const stats = computed(() => ({
    users: usersStore.pagination.total,
    roles: rolesStore.pagination.total,
    entities: entitiesStore.pagination?.total || 0,
}));

const quickActions = computed(() => {
    const actions = [
        {
            label: "Add user",
            icon: "i-lucide-user-plus",
            onSelect: () => navigateTo("/users"),
        },
        {
            label: "Create role",
            icon: "i-lucide-shield-plus",
            onSelect: () => navigateTo("/roles"),
        },
        {
            label: "Generate API key",
            icon: "i-lucide-key",
            onSelect: () => navigateTo("/api-keys"),
        },
    ];

    if (authStore.isEnterpriseRBAC) {
        actions.splice(2, 0, {
            label: "Create entity",
            icon: "i-lucide-building-2",
            onSelect: () => navigateTo("/entities"),
        });
    }

    return actions;
});

// Methods
const fetchStats = async () => {
    try {
        // Fetch counts from each store
        await Promise.all([
            usersStore.fetchUsers({}, { page: 1, limit: 1 }),
            rolesStore.fetchRoles({}, { page: 1, limit: 1 }),
            authStore.isEnterpriseRBAC
                ? entitiesStore.fetchEntities({}, { page: 1, limit: 1 })
                : Promise.resolve(),
        ]);
    } catch (error) {
        console.error("Failed to fetch stats:", error);
    }
};

// Watch for context changes
watch(
    () => contextStore.selectedEntity,
    () => {
        fetchStats();
    },
);

// Initialize
onMounted(async () => {
    await fetchStats();
});
</script>
