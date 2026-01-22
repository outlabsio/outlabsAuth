<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import type { Role } from "~/types/role";
import { useQuery } from "@pinia/colada";
import { rolesQueries, useDeleteRoleMutation } from "~/queries/roles";
import { entitiesQueries } from "~/queries/entities";

// Resolve components for use in cell renderers
const UButton = resolveComponent("UButton");
const UBadge = resolveComponent("UBadge");

const authStore = useAuthStore();
const isEnterpriseRBAC = computed(() => authStore.isEnterpriseRBAC);

const search = ref("");
const scopeFilter = ref<"all" | "global" | "organization">("all");
const orgFilter = ref<string | undefined>(undefined);
const showCreateModal = ref(false);
const showEditModal = ref(false);
const selectedRoleId = ref("");

// Fetch root entities for filter dropdown (EnterpriseRBAC only)
const { data: entitiesData } = useQuery(
    entitiesQueries.list({ root_only: true }, { page: 1, limit: 100 }),
);

const rootEntityOptions = computed(() => {
    const entities = entitiesData.value?.items || [];
    return [
        { label: "All Organizations", value: undefined },
        ...entities.map((e) => ({
            label: e.display_name || e.name,
            value: e.id,
        })),
    ];
});

const scopeFilterOptions = [
    { label: "All Roles", value: "all" },
    { label: "Global Only", value: "global" },
    { label: "Organization-specific", value: "organization" },
];

function openEditModal(roleId: string) {
    selectedRoleId.value = roleId;
    showEditModal.value = true;
}

// Reset org filter when scope changes
watch(scopeFilter, (newScope) => {
    if (newScope !== "organization") {
        orgFilter.value = undefined;
    }
});

// Reactive filters for query
const filters = computed(() => {
    const f: any = {};
    if (search.value) {
        f.search = search.value;
    }
    // Note: Backend would need to support these filters
    // For now we'll filter client-side
    return f;
});

// Client-side filtering for scope (until backend supports it)
const filteredRoles = computed(() => {
    let roles = rolesData.value?.items || [];

    // Filter by scope
    if (scopeFilter.value === "global") {
        roles = roles.filter((r) => r.is_global && !r.root_entity_id);
    } else if (scopeFilter.value === "organization") {
        roles = roles.filter((r) => !r.is_global || r.root_entity_id);

        // Further filter by specific organization
        if (orgFilter.value) {
            roles = roles.filter((r) => r.root_entity_id === orgFilter.value);
        }
    }

    return roles;
});

// Query roles with Pinia Colada (auto-fetches and auto-refetches when search changes)
const {
    data: rolesData,
    isLoading,
    error,
} = useQuery(() => rolesQueries.list(filters.value, { page: 1, limit: 100 }));

// Mutations
const { mutate: deleteRole } = useDeleteRoleMutation();

// Table columns - computed to handle EnterpriseRBAC vs SimpleRBAC
const columns = computed((): TableColumn<Role>[] => {
    const baseColumns: TableColumn<Role>[] = [
        {
            accessorKey: "name",
            header: "Role",
            cell: ({ row }) =>
                h("div", { class: "flex flex-col gap-1" }, [
                    h(
                        "p",
                        { class: "font-medium" },
                        row.original.display_name || row.original.name,
                    ),
                    h("p", { class: "text-sm text-muted" }, row.original.name),
                ]),
        },
        {
            accessorKey: "permissions",
            header: "Permissions",
            cell: ({ row }) => {
                const count = row.original.permissions?.length || 0;
                return h("div", { class: "flex items-center gap-2" }, [
                    h(
                        "span",
                        { class: "text-sm" },
                        `${count} permission${count !== 1 ? "s" : ""}`,
                    ),
                    h(
                        UBadge,
                        {
                            color: count > 0 ? "primary" : "neutral",
                            variant: "subtle",
                            size: "xs",
                        },
                        () => count,
                    ),
                ]);
            },
        },
    ];

    // Add Scope column for EnterpriseRBAC
    if (isEnterpriseRBAC.value) {
        baseColumns.push({
            accessorKey: "root_entity_id",
            header: "Scope",
            cell: ({ row }) => {
                if (row.original.is_global && !row.original.root_entity_id) {
                    return h(
                        UBadge,
                        {
                            color: "info",
                            variant: "subtle",
                        },
                        () => "Global",
                    );
                }
                if (row.original.root_entity_name) {
                    return h(
                        UBadge,
                        {
                            color: "neutral",
                            variant: "subtle",
                        },
                        () => row.original.root_entity_name,
                    );
                }
                return h("span", { class: "text-muted text-sm" }, "Scoped");
            },
        });
    }

    baseColumns.push(
        {
            accessorKey: "description",
            header: "Description",
            cell: ({ row }) =>
                h(
                    "span",
                    { class: "text-sm text-muted truncate max-w-md" },
                    row.original.description || "-",
                ),
        },
        {
            id: "actions",
            header: "Actions",
            cell: ({ row }) =>
                h("div", { class: "flex items-center gap-2" }, [
                    h(UButton, {
                        icon: "i-lucide-pencil",
                        color: "neutral",
                        variant: "ghost",
                        size: "xs",
                        onClick: () => openEditModal(row.original.id),
                    }),
                    h(UButton, {
                        icon: "i-lucide-trash-2",
                        color: "error",
                        variant: "ghost",
                        size: "xs",
                        onClick: async () => {
                            if (
                                confirm(
                                    `Are you sure you want to delete role "${row.original.display_name || row.original.name}"?`,
                                )
                            ) {
                                await deleteRole(row.original.id);
                            }
                        },
                    }),
                ]),
        },
    );

    return baseColumns;
});
</script>

<template>
    <UDashboardPanel id="roles">
        <!-- Default slot for edge-to-edge table -->
        <div class="flex flex-col flex-1 min-h-0">
            <!-- Header -->
            <UDashboardNavbar title="Roles">
                <template #leading>
                    <UDashboardSidebarCollapse />
                </template>

                <template #right>
                    <UButton
                        icon="i-lucide-plus"
                        label="Create Role"
                        color="primary"
                        @click="showCreateModal = true"
                    />
                </template>
            </UDashboardNavbar>

            <!-- Toolbar -->
            <div
                class="flex items-center justify-between gap-2 px-4 py-3 border-b border-default"
            >
                <div class="flex items-center gap-2">
                    <UInput
                        v-model="search"
                        icon="i-lucide-search"
                        placeholder="Search roles..."
                        class="w-64"
                    />

                    <!-- Scope filter (EnterpriseRBAC only) -->
                    <template v-if="isEnterpriseRBAC">
                        <USelect
                            v-model="scopeFilter"
                            :items="scopeFilterOptions"
                            class="w-48"
                        />
                        <USelect
                            v-if="scopeFilter === 'organization'"
                            v-model="orgFilter"
                            :items="rootEntityOptions"
                            placeholder="All Organizations"
                            class="w-48"
                        />
                    </template>
                </div>

                <div class="flex items-center gap-2">
                    <UButton
                        icon="i-lucide-download"
                        color="neutral"
                        variant="ghost"
                        label="Export"
                    />
                </div>
            </div>

            <!-- Loading State -->
            <div
                v-if="isLoading"
                class="flex-1 flex items-center justify-center"
            >
                <UIcon
                    name="i-lucide-loader-2"
                    class="w-8 h-8 animate-spin text-primary"
                />
            </div>

            <!-- Error State -->
            <div
                v-else-if="error"
                class="flex-1 flex flex-col items-center justify-center gap-4"
            >
                <UIcon
                    name="i-lucide-alert-circle"
                    class="w-12 h-12 text-error"
                />
                <p class="text-error">{{ error }}</p>
            </div>

            <!-- Table -->
            <UTable
                v-else
                sticky
                class="flex-1"
                :columns="columns"
                :data="filteredRoles"
            >
                <template #empty>
                    <div
                        class="flex flex-col items-center justify-center py-12 gap-4"
                    >
                        <UIcon
                            name="i-lucide-shield"
                            class="w-12 h-12 text-muted"
                        />
                        <p class="text-muted">No roles found</p>
                        <UButton
                            icon="i-lucide-plus"
                            label="Create your first role"
                            variant="outline"
                            @click="showCreateModal = true"
                        />
                    </div>
                </template>
            </UTable>

            <!-- Pagination -->
            <div
                v-if="rolesData && rolesData.pages > 1"
                class="px-4 py-3 border-t border-default"
            >
                <UPagination
                    :model-value="rolesData.page"
                    :total="rolesData.total"
                    :page-size="rolesData.limit"
                />
            </div>
        </div>
    </UDashboardPanel>

    <!-- Create Role Modal -->
    <RoleCreateModal v-model:open="showCreateModal" />

    <!-- Edit Role Modal -->
    <RoleUpdateModal
        v-if="selectedRoleId"
        v-model:open="showEditModal"
        :role-id="selectedRoleId"
    />
</template>
