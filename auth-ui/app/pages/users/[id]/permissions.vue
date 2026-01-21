<script setup lang="ts">
/**
 * Permissions Tab
 * Display user's effective permissions from roles + direct assignments
 * Uses UTable for better display of large permission lists
 */

import { h, resolveComponent } from "vue";
import type { TableColumn } from "@nuxt/ui";
import type { User } from "~/types/auth";
import type { UserPermissionSource } from "~/stores/user.store";

const UBadge = resolveComponent("UBadge");

const props = defineProps<{
    user: User;
}>();

const userStore = useUserStore();

// User's effective permissions
const userPermissions = computed(() => userStore.userPermissions);

// Group permissions by source for summary
const permissionsFromRoles = computed(() =>
    userPermissions.value.filter((p) => p.source === "role"),
);

const directPermissions = computed(() =>
    userPermissions.value.filter((p) => p.source === "direct"),
);

// Search filter
const globalFilter = ref("");

// Table columns
const columns: TableColumn<UserPermissionSource>[] = [
    {
        accessorKey: "permission.name",
        header: "Permission",
        cell: ({ row }) => {
            const perm = row.original.permission;
            return h("div", { class: "flex flex-col" }, [
                h(
                    "span",
                    { class: "font-medium text-foreground" },
                    perm.display_name || perm.name,
                ),
                perm.description
                    ? h(
                          "span",
                          { class: "text-xs text-muted truncate max-w-xs" },
                          perm.description,
                      )
                    : null,
            ]);
        },
    },
    {
        accessorKey: "permission.resource",
        header: "Resource",
        cell: ({ row }) =>
            h(
                "code",
                { class: "px-2 py-1 bg-muted rounded text-xs" },
                row.original.permission.resource,
            ),
    },
    {
        accessorKey: "permission.action",
        header: "Action",
        cell: ({ row }) =>
            h(
                "code",
                { class: "px-2 py-1 bg-muted rounded text-xs" },
                row.original.permission.action,
            ),
    },
    {
        accessorKey: "source",
        header: "Source",
        cell: ({ row }) => {
            const source = row.original.source;
            const sourceName = row.original.source_name;
            const color = source === "role" ? "primary" : "success";
            const label = source === "role" ? sourceName || "Role" : "Direct";

            return h(
                UBadge,
                { color, variant: "subtle", class: "capitalize" },
                () => label,
            );
        },
    },
    {
        accessorKey: "permission.is_active",
        header: "Status",
        meta: {
            class: {
                th: "text-center",
                td: "text-center",
            },
        },
        cell: ({ row }) => {
            const isActive = row.original.permission.is_active;
            return h(
                UBadge,
                {
                    color: isActive ? "success" : "neutral",
                    variant: "subtle",
                },
                () => (isActive ? "Active" : "Inactive"),
            );
        },
    },
];

// Fetch permissions on mount
onMounted(async () => {
    await userStore.fetchUserPermissions(props.user.id);
});
</script>

<template>
    <div class="flex flex-col gap-4">
        <!-- Header -->
        <div class="flex items-center justify-between">
            <div>
                <h3 class="text-lg font-semibold text-foreground">
                    Effective Permissions
                </h3>
                <p class="text-sm text-muted">
                    All permissions from assigned roles + direct permissions
                </p>
            </div>
            <UBadge color="primary" variant="subtle">
                {{ userPermissions.length }}
                {{ userPermissions.length === 1 ? "permission" : "permissions" }}
            </UBadge>
        </div>

        <!-- Summary Cards -->
        <div class="grid grid-cols-2 gap-4">
            <div class="flex items-center gap-3 p-4 bg-primary/5 rounded-lg">
                <div
                    class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center"
                >
                    <UIcon name="i-lucide-shield" class="w-5 h-5 text-primary" />
                </div>
                <div>
                    <p class="text-2xl font-bold text-primary">
                        {{ permissionsFromRoles.length }}
                    </p>
                    <p class="text-xs text-muted">From Roles</p>
                </div>
            </div>
            <div class="flex items-center gap-3 p-4 bg-success/5 rounded-lg">
                <div
                    class="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center"
                >
                    <UIcon name="i-lucide-key" class="w-5 h-5 text-success" />
                </div>
                <div>
                    <p class="text-2xl font-bold text-success">
                        {{ directPermissions.length }}
                    </p>
                    <p class="text-xs text-muted">Direct</p>
                </div>
            </div>
        </div>

        <!-- Search -->
        <div class="flex items-center gap-3">
            <UInput
                v-model="globalFilter"
                icon="i-lucide-search"
                placeholder="Search permissions..."
                class="max-w-sm"
            />
        </div>

        <!-- Loading State -->
        <div
            v-if="userStore.state.isLoadingPermissions"
            class="text-center py-12"
        >
            <UIcon
                name="i-lucide-loader-2"
                class="w-8 h-8 animate-spin text-primary mb-2"
            />
            <p class="text-sm text-muted">Loading permissions...</p>
        </div>

        <!-- Empty State -->
        <div
            v-else-if="userPermissions.length === 0"
            class="text-center py-12 border border-dashed border-default rounded-lg"
        >
            <UIcon name="i-lucide-lock-open" class="w-12 h-12 text-muted mb-4" />
            <p class="text-sm font-medium text-foreground mb-1">
                No permissions
            </p>
            <p class="text-xs text-muted">
                This user has no permissions assigned
            </p>
        </div>

        <!-- Permissions Table -->
        <UTable
            v-else
            v-model:global-filter="globalFilter"
            :data="userPermissions"
            :columns="columns"
            class="border border-default rounded-lg"
        />
    </div>
</template>
