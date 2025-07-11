<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import { getPaginationRowModel, type Row } from "@tanstack/table-core";

// Import the InviteModal component
import InviteModal from "~/components/user/InviteModal.vue";

// Define Invite type from the store's interface
interface Invite {
  id: string;
  email: string;
  code: string;
  created_at: string;
  expires_at: string;
  is_used: boolean;
  is_revoked: boolean;
  invited_by: string;
}

const UButton = resolveComponent("UButton");
const UBadge = resolveComponent("UBadge");
const UDropdownMenu = resolveComponent("UDropdownMenu");

const toast = useToast();
const table = useTemplateRef<any>("table");
const invitationsStore = useInvitationsStore();

const columnFilters = ref([]);
const columnVisibility = ref();
const rowSelection = ref({});
const pagination = ref({
  pageIndex: 0,
  pageSize: 10,
});

const status = ref<"idle" | "pending" | "success" | "error">("idle");
const searchQuery = ref("");

// Watch for search query changes
watch(searchQuery, (newQuery) => {
  invitationsStore.setSearchQuery(newQuery);
});

// Watch for pagination changes
watch(
  pagination,
  async (newPagination) => {
    const skip = newPagination.pageIndex * newPagination.pageSize;
    const limit = newPagination.pageSize;
    await invitationsStore.fetchInvitations(skip, limit);
  },
  { deep: true }
);

// Initial data fetch
onMounted(async () => {
  status.value = "pending";
  try {
    await invitationsStore.fetchInvitations();
    status.value = "success";
  } catch (error) {
    status.value = "error";
    toast.add({
      title: "Error",
      description: "Failed to fetch invitations",
      color: "error",
    });
  }
});

// Invite modal state
const isInvitingOpen = ref(false);

// Get status based on invitation state
const getStatus = (invite: Invite): "pending" | "accepted" | "expired" => {
  if (invite.is_revoked) return "expired";
  if (invite.is_used) return "accepted";
  return "pending";
};

// Get status color based on invite status
const getStatusColor = (status: string) => {
  switch (status) {
    case "pending":
      return "warning";
    case "accepted":
      return "success";
    case "expired":
      return "error";
    default:
      return "neutral";
  }
};

// Format date
const formatDate = (dateString: string) => {
  return dateString ? new Date(dateString).toLocaleString() : "N/A";
};

// Define row action items
function getRowItems(row: Row<Invite>) {
  const status = getStatus(row.original);
  return [
    {
      type: "label",
      label: "Actions",
    },
    {
      label: "Resend invitation",
      icon: "i-lucide-mail",
      disabled: status !== "pending",
      async onSelect() {
        try {
          await invitationsStore.resendInvitation(row.original.id);
          toast.add({
            title: "Invitation resent",
            description: `Invitation has been resent to ${row.original.email}`,
            color: "success",
          });
        } catch (error: any) {
          toast.add({
            title: "Error",
            description: error.message || "Failed to resend invitation",
            color: "error",
          });
        }
      },
    },
    {
      type: "separator",
    },
    {
      label: "Revoke invitation",
      icon: "i-lucide-x",
      color: "error",
      disabled: status !== "pending",
      async onSelect() {
        try {
          await invitationsStore.revokeInvitation(row.original.id);
          toast.add({
            title: "Invitation revoked",
            description: `Invitation to ${row.original.email} has been revoked`,
            color: "success",
          });
        } catch (error: any) {
          toast.add({
            title: "Error",
            description: error.message || "Failed to revoke invitation",
            color: "error",
          });
        }
      },
    },
  ];
}

// Define table columns
const columns: TableColumn<Invite>[] = [
  {
    accessorKey: "email",
    header: "Email",
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = getStatus(row.original);
      const color = getStatusColor(status);
      return h(UBadge, { class: "capitalize", variant: "subtle", color }, () => status);
    },
  },
  {
    accessorKey: "created_at",
    header: "Created",
    cell: ({ row }) => formatDate(row.original.created_at),
  },
  {
    accessorKey: "expires_at",
    header: "Expires",
    cell: ({ row }) => formatDate(row.original.expires_at),
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
            content: {
              align: "end",
            },
            items: getRowItems(row),
          },
          () =>
            h(UButton, {
              icon: "i-lucide-ellipsis-vertical",
              color: "neutral",
              variant: "ghost",
              class: "ml-auto",
            })
        )
      );
    },
  },
];
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-1.5 mb-6">
      <UInput class="max-w-sm" icon="i-lucide-search" placeholder="Search invitations..." v-model="searchQuery" />
      <!-- Invite Modal Component -->
      <InviteModal v-model:open="isInvitingOpen" />
    </div>

    <UTable
      ref="table"
      v-model:column-filters="columnFilters"
      v-model:column-visibility="columnVisibility"
      v-model:row-selection="rowSelection"
      v-model:pagination="pagination"
      :pagination-options="{
        getPaginationRowModel: getPaginationRowModel(),
      }"
      class="shrink-0"
      :data="invitationsStore.invitations"
      :columns="columns"
      :loading="status === 'pending'"
      :ui="{
        base: 'table-fixed border-separate border-spacing-0',
        thead: '[&>tr]:bg-(--ui-bg-elevated)/50 [&>tr]:after:content-none',
        tbody: '[&>tr]:last:[&>td]:border-b-0',
        th: 'py-1 first:rounded-l-[calc(var(--ui-radius)*2)] last:rounded-r-[calc(var(--ui-radius)*2)] border-y border-(--ui-border) first:border-l last:border-r',
        td: 'border-b border-(--ui-border)',
      }"
    />

    <div class="flex items-center justify-between gap-3 border-t border-(--ui-border) pt-4 mt-auto">
      <div class="text-sm text-(--ui-text-muted)">
        {{ table?.tableApi?.getFilteredSelectedRowModel().rows.length || 0 }} of {{ table?.tableApi?.getFilteredRowModel().rows.length || 0 }} row(s) selected.
      </div>

      <div class="flex items-center gap-1.5">
        <UPagination
          :page="pagination.pageIndex + 1"
          :items-per-page="pagination.pageSize"
          :total="invitationsStore.totalInvitations"
          @update:page="(page: number) => pagination.pageIndex = page - 1"
        />
      </div>
    </div>
  </div>
</template>
