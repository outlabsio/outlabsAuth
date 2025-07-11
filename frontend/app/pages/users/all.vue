<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import { upperFirst } from "scule";
import { getPaginationRowModel, type Row } from "@tanstack/table-core";
import { defineAsyncComponent } from "vue";

// Define the User type directly based on users.store.ts
interface User {
  id: string;
  _id?: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  name: string;
  is_team_member: boolean;
  last_login: string;
  created_at: string;
  permissions: string[];
}

const UAvatar = resolveComponent("UAvatar");
const UButton = resolveComponent("UButton");
const UBadge = resolveComponent("UBadge");
const UDropdownMenu = resolveComponent("UDropdownMenu");

const toast = useToast();
const table = useTemplateRef<any>("table");
const usersStore = useUsersStore();

const columnFilters = ref([
  {
    id: "email",
    value: "",
  },
]);
const columnVisibility = ref();

// Get users and totalUsers as reactive refs
const { users, totalUsers, currentPage } = storeToRefs(usersStore);

const status = ref<"idle" | "pending" | "success" | "error">("idle");
const searchQuery = ref("");

const editModalOpen = ref(false);
const permissionsModalOpen = ref(false);
const selectedUser = ref<User | null>(null);

const router = useRouter();

// Initial fetch
onMounted(async () => {
  status.value = "pending";
  await usersStore.fetchUsers();
  status.value = "success";
});

// Set search query and reset to first page
const setSearchQuery = (query: string) => {
  usersStore.setSearchQuery(query);
  currentPage.value = 1; // Reset to first page when searching
};

const handleRowClick = (row: Row<User>) => {
  if (!row || !row.original || !row.original.id) {
    console.error("Invalid row data for navigation:", row);
    toast.add({ title: "Error", description: "Could not navigate to user page.", color: "error" });
    return;
  }
  router.push(`/user/${row.original.id}`);
};

const columns: TableColumn<User>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => {
      return h("div", { class: "flex items-center gap-3" }, [
        h(UAvatar, {
          src: `https://avatars.dicebear.com/api/initials/${row.original.name}.svg`,
          size: "sm",
        }),
        h("div", undefined, [h("p", { class: "font-medium text-(--ui-text-highlighted)" }, row.original.name)]),
      ]);
    },
  },
  {
    accessorKey: "email",
    header: ({ column }) => {
      const isSorted = column.getIsSorted();

      return h(UButton, {
        color: "neutral",
        variant: "ghost",
        label: "Email",
        icon: isSorted ? (isSorted === "asc" ? "i-lucide-arrow-up-narrow-wide" : "i-lucide-arrow-down-wide-narrow") : "i-lucide-arrow-up-down",
        class: "-mx-2.5",
        onClick: () => column.toggleSorting(column.getIsSorted() === "asc"),
      });
    },
  },
  {
    accessorKey: "userType",
    header: "User Type",
    cell: ({ row }) => {
      const type = usersStore.getUserType(row.original);
      const color = usersStore.getUserTypeBadgeColor(row.original);
      return h(UBadge, { class: "capitalize", variant: "subtle", style: `--color: ${color}` }, () => type);
    },
  },
  {
    accessorKey: "is_active",
    header: "Status",
    filterFn: "equals",
    cell: ({ row }) => {
      const color = row.original.is_active ? "success" : "error";
      return h(UBadge, { class: "capitalize", variant: "subtle", color }, () => (row.original.is_active ? "Active" : "Inactive"));
    },
  },
  {
    accessorKey: "is_verified",
    header: "Verified",
    cell: ({ row }) => {
      const color = row.original.is_verified ? "success" : "warning";
      return h(UBadge, { class: "capitalize", variant: "subtle", color }, () => (row.original.is_verified ? "Verified" : "Unverified"));
    },
  },
  {
    accessorKey: "created_at",
    header: "Created At",
    cell: ({ row }) => usersStore.formatDate(row.original.created_at || ""),
  },
  {
    accessorKey: "last_login",
    header: "Last Login",
    cell: ({ row }) => usersStore.formatDate(row.original.last_login || ""),
  },
];

const statusFilter = ref("all");

watch(
  () => statusFilter.value,
  (newVal) => {
    if (!table?.value?.tableApi) return;

    const statusColumn = table.value.tableApi.getColumn("is_active");
    if (!statusColumn) return;

    if (newVal === "all") {
      statusColumn.setFilterValue(undefined);
    } else {
      const isActive = newVal === "active";
      statusColumn.setFilterValue(isActive);
    }
  }
);

const pagination = ref({
  pageIndex: 0,
  pageSize: 10,
});

// Watch currentPage changes to fetch new data (similar to anonymous.vue)
watch(currentPage, (newPage) => {
  console.log("Current page changed to:", newPage);
  // Update the pagination ref to keep it in sync
  pagination.value.pageIndex = newPage - 1;
  // Fetch users for the new page
  usersStore.fetchUsers();
});

// Watch search query changes
watch(searchQuery, (newQuery) => {
  setSearchQuery(newQuery);
});

// Fix type issues with table column parameters
type TableApiColumn = {
  id: string;
  getCanHide: () => boolean;
  getIsVisible: () => boolean;
  toggleVisibility: (value: boolean) => void;
};
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-1.5 mb-6">
      <UInput v-model="searchQuery" class="max-w-sm" icon="i-lucide-search" placeholder="Search users..." />

      <div class="flex flex-wrap items-center gap-1.5">
        <USelect
          v-model="statusFilter"
          :items="[
            { label: 'All', value: 'all' },
            { label: 'Active', value: 'active' },
            { label: 'Inactive', value: 'inactive' },
          ]"
          :ui="{ trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200' }"
          placeholder="Filter status"
          class="min-w-28"
        />
        <UDropdownMenu
          :items="
            table?.tableApi
              ?.getAllColumns()
              .filter((column: TableApiColumn) => column.getCanHide())
              .map((column: TableApiColumn) => ({
                label: upperFirst(column.id),
                type: 'checkbox' as const,
                checked: column.getIsVisible(),
                onUpdateChecked(checked: boolean) {
                  table?.tableApi?.getColumn(column.id)?.toggleVisibility(!!checked)
                },
                onSelect(e?: Event) {
                  e?.preventDefault()
                }
              }))
          "
          :content="{ align: 'end' }"
        >
          <UButton label="Display" color="neutral" variant="outline" trailing-icon="i-lucide-settings-2" />
        </UDropdownMenu>
      </div>
    </div>

    <UTable
      ref="table"
      v-model:column-filters="columnFilters"
      v-model:column-visibility="columnVisibility"
      v-model:pagination="pagination"
      :pagination-options="{
        getPaginationRowModel: getPaginationRowModel(),
      }"
      class="shrink-0"
      :data="users"
      :columns="columns"
      :loading="status === 'pending'"
      :ui="{
        base: 'table-fixed border-separate border-spacing-0',
        thead: '[&>tr]:bg-(--ui-bg-elevated)/50 [&>tr]:after:content-none',
        tbody: '[&>tr]:last:[&>td]:border-b-0 [&>tr]:cursor-pointer',
        th: 'py-1 first:rounded-l-[calc(var(--ui-radius)*2)] last:rounded-r-[calc(var(--ui-radius)*2)] border-y border-(--ui-border) first:border-l last:border-r',
        td: 'border-b border-(--ui-border)',
      }"
      @sorted="usersStore.sortUsers($event.column, $event.direction)"
      @select="handleRowClick"
    />

    <div class="flex items-center justify-between gap-3 border-t border-(--ui-border) pt-4 mt-auto">
      <div class="text-sm text-(--ui-text-muted)">
        Showing {{ (currentPage - 1) * pagination.pageSize + 1 }} - {{ Math.min(currentPage * pagination.pageSize, totalUsers) }} of {{ totalUsers }} users.
      </div>

      <div class="flex items-center gap-1.5">
        <UPagination v-model:page="currentPage" :items-per-page="pagination.pageSize" :total="totalUsers" />
      </div>
    </div>

    <!-- Add modal components at the end of the template -->
    <UsersEditModal v-model:open="editModalOpen" :user="selectedUser" @update="usersStore.fetchUsers()" />
    <UsersPermissionsModal v-model:open="permissionsModalOpen" :user="selectedUser" />
  </div>
</template>
