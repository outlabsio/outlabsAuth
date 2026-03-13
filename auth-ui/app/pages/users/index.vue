<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import type { Row } from "@tanstack/table-core";
import { getPaginationRowModel } from "@tanstack/table-core";
import type { User } from "~/types/auth";
import { useQuery } from "@pinia/colada";
import {
    usersQueries,
    useDeleteUserMutation,
    useUpdateUserStatusMutation,
} from "~/queries/users";

definePageMeta({
    layout: "default",
});

const UAvatar = resolveComponent("UAvatar");
const UButton = resolveComponent("UButton");
const UBadge = resolveComponent("UBadge");
const UDropdownMenu = resolveComponent("UDropdownMenu");
const UCheckbox = resolveComponent("UCheckbox");

const toast = useToast();
const table = useTemplateRef("table");

// State
const search = ref("");
const statusFilter = ref<"all" | "active" | "suspended" | "banned">("all");
const showCreateModal = ref(false);
const columnFilters = ref([{ id: "email", value: "" }]);
const columnVisibility = ref();
const rowSelection = ref({});
const pagination = ref({
    pageIndex: 0,
    pageSize: 20,
});
const showUserActionConfirm = ref(false);
const pendingAction = ref<"ban" | "delete" | null>(null);
const pendingUser = ref<User | null>(null);
const isConfirmingUserAction = ref(false);

// Reset to page 1 when filters change
watch([search, statusFilter], () => {
    pagination.value.pageIndex = 0;
});

// Reactive filters and params for query
const filters = computed(() => {
    const f: any = {};

    if (search.value) {
        f.search = search.value;
    }

    if (statusFilter.value !== "all") {
        f.status = statusFilter.value;
    }

    return f;
});

const params = computed(() => ({
    page: pagination.value.pageIndex + 1,
    limit: pagination.value.pageSize,
}));

// Query users with Pinia Colada (auto-fetches and auto-refetches when filters/params change)
const {
    data: usersData,
    isLoading,
    error,
} = useQuery(() => usersQueries.list(filters.value, params.value));

const usersErrorMessage = computed(() => {
    if (!error.value) {
        return "";
    }
    return error.value instanceof Error ? error.value.message : String(error.value);
});

// Mutations
const { mutate: deleteUser } = useDeleteUserMutation();
const { mutate: updateUserStatus } = useUpdateUserStatusMutation();

const userActionConfirmMeta = computed(() => {
    const name =
        pendingUser.value?.first_name ||
        pendingUser.value?.full_name ||
        pendingUser.value?.email ||
        "this user";

    if (pendingAction.value === "ban") {
        return {
            title: "Ban user?",
            description: `The user '${name}' will be blocked from signing in until an admin reactivates the account.`,
            confirmLabel: "Ban user",
            confirmColor: "error",
        };
    }

    return {
        title: "Delete user?",
        description: `This will permanently delete '${name}'.`,
        confirmLabel: "Delete user",
        confirmColor: "error",
    };
});

function requestUserAction(action: "ban" | "delete", user: User) {
    pendingAction.value = action;
    pendingUser.value = user;
    showUserActionConfirm.value = true;
}

function resetUserActionState() {
    if (isConfirmingUserAction.value) {
        return;
    }
    showUserActionConfirm.value = false;
    pendingAction.value = null;
    pendingUser.value = null;
}

async function confirmUserAction() {
    if (!pendingAction.value || !pendingUser.value) {
        return;
    }

    isConfirmingUserAction.value = true;

    try {
        if (pendingAction.value === "ban") {
            await updateUserStatus({
                userId: pendingUser.value.id,
                status: "banned",
            });
        } else {
            // Uses optimistic update mutation - UI updates instantly
            await deleteUser(pendingUser.value.id);
        }

        showUserActionConfirm.value = false;
        pendingAction.value = null;
        pendingUser.value = null;
    } catch {
        toast.add({
            title: "Error",
            description:
                pendingAction.value === "ban"
                    ? "Failed to ban user."
                    : "Failed to delete user.",
            color: "error",
        });
    } finally {
        isConfirmingUserAction.value = false;
    }
}

watch(showUserActionConfirm, (isOpen) => {
    if (!isOpen && !isConfirmingUserAction.value) {
        pendingAction.value = null;
        pendingUser.value = null;
    }
});

// Get row action items
function getRowItems(row: Row<User>) {
    return [
        {
            type: "label",
            label: "Actions",
        },
        {
            label: "View details",
            icon: "i-lucide-eye",
            onSelect() {
                navigateTo(`/users/${row.original.id}`);
            },
        },
        {
            label: "Edit user",
            icon: "i-lucide-pencil",
            onSelect() {
                navigateTo(`/users/${row.original.id}`);
            },
        },
        {
            type: "separator",
        },
        // Status actions based on current user status
        ...(row.original.status === "active"
            ? [
                  {
                      label: "Suspend user",
                      icon: "i-lucide-pause-circle",
                      onSelect: async () => {
                          try {
                              await updateUserStatus({
                                  userId: row.original.id,
                                  status: "suspended",
                              });
                          } catch {
                              toast.add({
                                  title: "Error",
                                  description: "Failed to suspend user.",
                                  color: "error",
                              });
                          }
                      },
                  },
                  {
                      label: "Ban user",
                      icon: "i-lucide-ban",
                      color: "error",
                      onSelect: () => {
                          requestUserAction("ban", row.original);
                      },
                  },
              ]
            : [
                  {
                      label: "Activate user",
                      icon: "i-lucide-user-check",
                      onSelect: async () => {
                          try {
                              await updateUserStatus({
                                  userId: row.original.id,
                                  status: "active",
                              });
                          } catch {
                              toast.add({
                                  title: "Error",
                                  description: "Failed to activate user.",
                                  color: "error",
                              });
                          }
                      },
                  },
              ]),
        {
            type: "separator",
        },
        {
            label: "Delete user",
            icon: "i-lucide-trash",
            color: "error",
            onSelect: () => {
                requestUserAction("delete", row.original);
            },
        },
    ];
}

// Table columns
const columns: TableColumn<User>[] = [
    {
        id: "select",
        header: ({ table }) =>
            h(UCheckbox, {
                modelValue: table.getIsSomePageRowsSelected()
                    ? "indeterminate"
                    : table.getIsAllPageRowsSelected(),
                "onUpdate:modelValue": (value: boolean | "indeterminate") =>
                    table.toggleAllPageRowsSelected(!!value),
                ariaLabel: "Select all",
            }),
        cell: ({ row }) =>
            h(UCheckbox, {
                modelValue: row.getIsSelected(),
                "onUpdate:modelValue": (value: boolean | "indeterminate") =>
                    row.toggleSelected(!!value),
                ariaLabel: "Select row",
            }),
    },
    {
        accessorKey: "first_name",
        header: "User",
        cell: ({ row }) => {
            const displayName =
                row.original.first_name && row.original.last_name
                    ? `${row.original.first_name} ${row.original.last_name}`
                    : row.original.first_name || row.original.email;
            const avatarUrl =
                row.original.avatar_url ||
                `https://api.dicebear.com/7.x/avataaars/svg?seed=${row.original.email}`;

            return h("div", { class: "flex items-center gap-3" }, [
                h(UAvatar, {
                    src: avatarUrl,
                    alt: displayName,
                    size: "lg",
                }),
                h("div", undefined, [
                    h(
                        "p",
                        { class: "font-medium text-highlighted" },
                        displayName,
                    ),
                    h("p", { class: "text-sm text-muted" }, row.original.email),
                ]),
            ]);
        },
    },
    {
        accessorKey: "email",
        header: "Email",
        cell: ({ row }) => h("span", { class: "text-sm" }, row.original.email),
    },
    {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => {
            const statusColors: Record<string, string> = {
                active: "success",
                suspended: "warning",
                banned: "error",
                deleted: "neutral",
            };
            const color = statusColors[row.original.status] || "neutral";
            const label =
                row.original.status.charAt(0).toUpperCase() +
                row.original.status.slice(1);

            return h(UBadge, { variant: "subtle", color }, () => label);
        },
    },
    {
        accessorKey: "is_superuser",
        header: "Role",
        cell: ({ row }) => {
            if (row.original.is_superuser) {
                return h(
                    UBadge,
                    { variant: "subtle", color: "primary" },
                    () => "Superuser",
                );
            }
            return h(
                "span",
                { class: "text-sm text-muted" },
                "User",
            );
        },
    },
    {
        id: "actions",
        cell: ({ row }) => {
            return h(
                "div",
                { class: "text-right" },
                h(
                    UDropdownMenu,
                    {
                        content: { align: "end" },
                        items: getRowItems(row),
                    },
                    () =>
                        h(UButton, {
                            icon: "i-lucide-ellipsis-vertical",
                            color: "neutral",
                            variant: "ghost",
                            class: "ml-auto",
                        }),
                ),
            );
        },
    },
];
</script>

<template>
    <UDashboardPanel id="users">
        <!-- Default slot for edge-to-edge table -->
        <div class="flex flex-col flex-1 min-h-0">
            <!-- Header -->
            <UDashboardNavbar title="Users">
                <template #leading>
                    <UDashboardSidebarCollapse />
                </template>

                <template #right>
                    <UButton
                        label="Create User"
                        icon="i-lucide-user-plus"
                        color="primary"
                        @click="showCreateModal = true"
                    />
                </template>
            </UDashboardNavbar>

            <!-- Toolbar -->
            <div
                class="flex flex-wrap items-center justify-between gap-1.5 px-4 py-3 border-b border-default"
            >
                <UInput
                    v-model="search"
                    class="max-w-sm"
                    icon="i-lucide-search"
                    placeholder="Search users..."
                />

                <div class="flex flex-wrap items-center gap-1.5">
                    <USelect
                        v-model="statusFilter"
                        :items="[
                            { label: 'All', value: 'all' },
                            { label: 'Active', value: 'active' },
                            { label: 'Suspended', value: 'suspended' },
                            { label: 'Banned', value: 'banned' },
                        ]"
                        :ui="{
                            trailingIcon:
                                'group-data-[state=open]:rotate-180 transition-transform duration-200',
                        }"
                        placeholder="Filter status"
                        class="min-w-28"
                    />
                </div>
            </div>

            <!-- Table -->
            <UAlert
                v-if="usersErrorMessage"
                color="error"
                variant="subtle"
                icon="i-lucide-alert-circle"
                title="Unable to load users"
                :description="usersErrorMessage"
                class="m-4"
            />

            <UTable
                ref="table"
                v-model:column-filters="columnFilters"
                v-model:column-visibility="columnVisibility"
                v-model:row-selection="rowSelection"
                v-model:pagination="pagination"
                sticky
                :pagination-options="{
                    getPaginationRowModel: getPaginationRowModel(),
                }"
                class="flex-1"
                :data="usersData?.items || []"
                :columns="columns"
                :loading="isLoading"
            />

            <!-- Pagination -->
            <div
                class="flex items-center justify-between gap-3 px-4 py-3 border-t border-default"
            >
                <div class="text-sm text-muted">
                    Showing {{ usersData?.items?.length || 0 }} of
                    {{ usersData?.total || 0 }} users
                </div>

                <div class="flex items-center gap-1.5">
                    <UPagination
                        v-if="
                            usersData && usersData.total > pagination.pageSize
                        "
                        :model-value="pagination.pageIndex + 1"
                        :items-per-page="pagination.pageSize"
                        :total="usersData.total"
                        @update:model-value="
                            (p: number) => {
                                pagination.pageIndex = p - 1;
                            }
                        "
                    />
                </div>
            </div>
        </div>
    </UDashboardPanel>

    <!-- Create User Modal -->
    <UserCreateModal v-model:open="showCreateModal" />

    <ConfirmActionModal
        v-model:open="showUserActionConfirm"
        :title="userActionConfirmMeta.title"
        :description="userActionConfirmMeta.description"
        :confirm-label="userActionConfirmMeta.confirmLabel"
        :confirm-color="userActionConfirmMeta.confirmColor"
        :loading="isConfirmingUserAction"
        @confirm="confirmUserAction"
        @cancel="resetUserActionState"
    />
</template>
