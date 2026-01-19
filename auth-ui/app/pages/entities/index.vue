<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import type { Entity } from "~/types/entity";
import { useQuery } from "@pinia/colada";
import { entitiesQueries, useDeleteEntityMutation } from "~/queries/entities";
import { UButton } from "#components";

const search = ref("");
const showCreateModal = ref(false);

// Reactive filters for query
const filters = computed(() => {
    const f: any = {};
    if (search.value) {
        f.search = search.value;
    }
    return f;
});

// Query entities with Pinia Colada
const queryOptions = entitiesQueries.list(filters.value, {
    page: 1,
    limit: 100,
});
const { data: entitiesData, isLoading, error } = useQuery(queryOptions);

// Mutations
const { mutate: deleteEntity } = useDeleteEntityMutation();

// Table columns
const columns: TableColumn<Entity>[] = [
    {
        accessorKey: "name",
        header: "Entity",
        cell: ({ row }) =>
            h("div", { class: "flex flex-col gap-1" }, [
                h("p", { class: "font-medium" }, row.original.name),
                h(
                    "p",
                    { class: "text-sm text-muted" },
                    row.original.entity_type,
                ),
            ]),
    },
    {
        accessorKey: "entity_class",
        header: "Class",
        cell: ({ row }) =>
            h("span", { class: "text-sm" }, row.original.entity_class),
    },
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
                    onClick: () => console.log("Edit entity:", row.original.id),
                }),
                h(UButton, {
                    icon: "i-lucide-trash-2",
                    color: "error",
                    variant: "ghost",
                    size: "xs",
                    onClick: async () => {
                        if (
                            confirm(
                                `Are you sure you want to delete entity "${row.original.name}"?`,
                            )
                        ) {
                            await deleteEntity({
                                entityId: row.original.id,
                                parentId: row.original.parent_entity_id,
                            });
                        }
                    },
                }),
            ]),
    },
];
</script>

<template>
    <UDashboardPanel id="entities">
        <template #header>
            <UDashboardNavbar title="Entities">
                <template #leading>
                    <UDashboardSidebarCollapse />
                </template>

                <template #right>
                    <UButton
                        icon="i-lucide-plus"
                        label="Create Entity"
                        color="primary"
                        @click="showCreateModal = true"
                    />
                </template>
            </UDashboardNavbar>

            <UDashboardToolbar>
                <template #left>
                    <UInput
                        v-model="search"
                        icon="i-lucide-search"
                        placeholder="Search entities..."
                        class="w-64"
                    />
                </template>

                <template #right>
                    <UButton
                        icon="i-lucide-filter"
                        color="neutral"
                        variant="ghost"
                        label="Filter"
                    />
                    <UButton
                        icon="i-lucide-download"
                        color="neutral"
                        variant="ghost"
                        label="Export"
                    />
                </template>
            </UDashboardToolbar>
        </template>

        <template #body>
            <UCard v-if="isLoading">
                <div class="flex items-center justify-center py-12">
                    <UIcon
                        name="i-lucide-loader-2"
                        class="w-8 h-8 animate-spin text-primary"
                    />
                </div>
            </UCard>

            <UCard v-else-if="error">
                <div
                    class="flex flex-col items-center justify-center py-12 gap-4"
                >
                    <UIcon
                        name="i-lucide-alert-circle"
                        class="w-12 h-12 text-error"
                    />
                    <p class="text-error">{{ error }}</p>
                </div>
            </UCard>

            <UTable v-else :columns="columns" :data="entitiesData?.items || []">
                <template #empty>
                    <div
                        class="flex flex-col items-center justify-center py-12 gap-4"
                    >
                        <UIcon
                            name="i-lucide-building"
                            class="w-12 h-12 text-muted"
                        />
                        <p class="text-muted">No entities found</p>
                        <UButton
                            icon="i-lucide-plus"
                            label="Create your first entity"
                            variant="outline"
                            @click="showCreateModal = true"
                        />
                    </div>
                </template>
            </UTable>

            <UPagination
                v-if="entitiesData && entitiesData.pages > 1"
                :model-value="entitiesData.page"
                :total="entitiesData.total"
                :page-size="entitiesData.limit"
            />
        </template>
    </UDashboardPanel>

    <!-- Create Entity Modal -->
    <EntityCreateModal v-model:open="showCreateModal" />
</template>
