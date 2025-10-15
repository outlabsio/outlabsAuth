<template>
  <div>
    <div v-if="loading" class="space-y-2">
      <USkeleton v-for="i in 8" :key="i" class="h-12 w-full" />
    </div>
    <div v-else-if="error">
      <UAlert
        icon="i-lucide-alert-triangle"
        color="error"
        variant="subtle"
        title="Error Loading Activity"
        :description="typeof error === 'string' ? error : error instanceof Error ? error.message : 'Could not load token activity.'"
      />
    </div>
    <div v-else-if="tokenEvents.length > 0">
      <UTable
        :columns="columns"
        :data="tokenEvents"
        :loading="loading"
        :ui="{
          thead: '[&>tr]:bg-(--ui-bg-elevated)/50 [&>tr]:after:content-none',
          tbody: '[&>tr]:last:[&>td]:border-b-0 [&>tr]:hover:bg-gray-50 dark:[&>tr]:hover:bg-gray-800/50',
          th: 'py-3 px-4 border-y border-(--ui-border) first:border-l last:border-r text-sm font-semibold',
          td: 'py-3 px-4 border-b border-(--ui-border) whitespace-nowrap',
        }"
      />
      <!-- Add UPagination here if needed later -->
    </div>
    <div v-else class="text-center py-12">
      <UIcon name="i-lucide-history" class="h-12 w-12 text-muted mx-auto mb-4" />
      <p class="text-lg font-medium">No Token Activity Found</p>
      <p class="text-muted mt-1">This user has no token transaction history yet.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";

// Interface for token events from API
interface TokenEvent {
  id: string;
  user_id: string;
  account_id: string;
  operation_type: string;
  category: string;
  timestamp: string;
  token_amount: number;
  balance_after: number;
  description?: string;
  product_id?: string;
  product_cost?: number;
  source?: string;
  payment_intent_id?: string;
  provider_transaction_id?: string;
  provider?: string;
  admin_user_id?: string;
  reason?: string;
  details?: Record<string, any>;
}

// Interface for API response
interface TokenEventsResponse {
  events: TokenEvent[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
}

// Helper function to format date
const formatDate = (dateString: string): string => {
  if (!dateString) return "-";
  try {
    return new Date(dateString).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (e) {
    return "Invalid Date";
  }
};

// Helper function to get operation type color and label
const getOperationStyle = (opType: string) => {
  // Clean up the label to be more concise
  let label = opType;

  if (opType.startsWith("token.")) {
    label = opType.replace("token.", "");
    return {
      color: "success" as const,
      label: label.replace("_", " "),
    };
  }
  if (opType.startsWith("debit.")) {
    label = opType.replace("debit.", "");
    // Further clean up reading operations
    if (label.startsWith("reading.")) {
      label = label.replace("reading.", "");
    }
    return {
      color: "warning" as const,
      label: label.replace("_", " "),
    };
  }
  if (opType.startsWith("system.")) {
    label = opType.replace("system.", "");
    return {
      color: "info" as const,
      label: label.replace("_", " "),
    };
  }
  return {
    color: "neutral" as const,
    label: label.replace("_", " "),
  };
};

// Helper function to get category color
const getCategoryColor = (category: string): "success" | "warning" | "info" | "primary" | "neutral" => {
  switch (category) {
    case "purchase":
      return "success";
    case "reading":
      return "warning";
    case "reward":
      return "primary";
    case "admin":
      return "info";
    default:
      return "neutral";
  }
};

// Helper function to format details
const formatDetails = (event: TokenEvent): string => {
  const parts: string[] = [];

  if (event.product_id) {
    parts.push(`Product: ${event.product_id}`);
  }

  if (event.product_cost) {
    parts.push(`Cost: ${event.product_cost} tokens`);
  }

  if (event.provider) {
    parts.push(`Provider: ${event.provider}`);
  }

  if (event.reason) {
    parts.push(`Reason: ${event.reason}`);
  }

  if (event.details && typeof event.details === "object") {
    const detailEntries = Object.entries(event.details);
    detailEntries.forEach(([key, value]) => {
      if (value && key !== "reading_id") {
        parts.push(`${key.replace("_", " ")}: ${value}`);
      }
    });
  }

  return parts.length > 0 ? parts.join(" • ") : event.description || "-";
};

// Define enhanced table columns
const columns: TableColumn<TokenEvent>[] = [
  {
    accessorKey: "timestamp",
    header: "Date & Time",
    cell: ({ row }) => {
      return h("div", { class: "space-y-1" }, [
        h("div", { class: "text-sm font-medium" }, formatDate(row.original.timestamp).split(", ")[0]),
        h("div", { class: "text-xs text-muted" }, formatDate(row.original.timestamp).split(", ")[1] || ""),
      ]);
    },
  },
  {
    accessorKey: "operation_type",
    header: "Operation",
    cell: ({ row }) => {
      const opType = row.original.operation_type;
      const style = getOperationStyle(opType);

      const UBadge = resolveComponent("UBadge");

      return h(UBadge, {
        color: style.color,
        variant: "subtle",
        label: style.label,
        class: "text-xs capitalize",
      });
    },
  },
  {
    accessorKey: "token_amount",
    header: "Tokens",
    cell: ({ row }) => {
      const amount = row.original.token_amount;
      const isPositive = amount > 0;
      const isNegative = amount < 0;
      const colorClass = isPositive ? "text-success" : isNegative ? "text-error" : "text-muted";
      const sign = isPositive ? "+" : "";

      return h("span", { class: `text-sm font-semibold ${colorClass}` }, `${sign}${amount}`);
    },
  },
  {
    accessorKey: "balance_after",
    header: "Balance",
    cell: ({ row }) => {
      return h("div", { class: "text-center" }, [h("span", { class: "text-sm font-medium text-primary" }, row.original.balance_after), h("div", { class: "text-xs text-muted" }, "tokens")]);
    },
  },
  {
    accessorKey: "category",
    header: "Category",
    cell: ({ row }) => {
      const UBadge = resolveComponent("UBadge");
      const color = getCategoryColor(row.original.category);

      return h(UBadge, {
        color: color,
        variant: "soft",
        label: row.original.category,
        class: "capitalize text-xs",
      });
    },
  },
  {
    accessorKey: "source",
    header: "Source",
    cell: ({ row }) => {
      const UIcon = resolveComponent("UIcon");
      const source = row.original.source || "unknown";

      const sourceIcons: Record<string, string> = {
        payment: "i-lucide-credit-card",
        admin: "i-lucide-shield",
        system: "i-lucide-cpu",
        achievement: "i-lucide-trophy",
        promo_code: "i-lucide-ticket",
        referral: "i-lucide-users",
        auto_topup: "i-lucide-repeat",
        compensation: "i-lucide-gift",
        milestone: "i-lucide-target",
      };

      return h("div", { class: "flex items-center space-x-2" }, [
        h(UIcon, {
          name: sourceIcons[source] || "i-lucide-circle",
          class: "h-4 w-4 text-muted",
        }),
        h("span", { class: "text-sm capitalize" }, source),
      ]);
    },
  },
  {
    accessorKey: "description",
    header: "Details",
    cell: ({ row }) => {
      const details = formatDetails(row.original);

      return h("div", { class: "max-w-xs" }, [
        h("div", { class: "text-sm text-gray-900 dark:text-gray-100 truncate" }, row.original.description || "Token transaction"),
        h("div", { class: "text-xs text-muted mt-1 line-clamp-2" }, details !== (row.original.description || "-") ? details : ""),
      ]);
    },
  },
];

const route = useRoute();
const toast = useToast();
const authStore = useAuthStore();

const userId = computed(() => route.params.user_id as string);
const loading = ref(false);
const error = ref<any | null>(null);
const tokenEvents = ref<TokenEvent[]>([]);

// Fetch token events for the user using admin API
async function fetchTokenEvents(id: string) {
  loading.value = true;
  error.value = null;
  console.log(`Fetching token events for user ID: ${id}`);

  try {
    const response = await authStore.apiCall<TokenEventsResponse>(`/users/${id}/token-events`);
    tokenEvents.value = response.events || [];
  } catch (err: any) {
    console.error("Error fetching token events:", err);
    error.value = err;
    tokenEvents.value = [];
    toast.add({
      title: "Error Loading Token Activity",
      description: err.message || "Could not load token events.",
      color: "error",
    });
  } finally {
    loading.value = false;
  }
}

// Fetch data on mount
onMounted(() => {
  if (userId.value) {
    fetchTokenEvents(userId.value);
  }
});

// Watch for route changes
watch(
  () => route.params.user_id,
  (newId) => {
    if (newId && typeof newId === "string") {
      fetchTokenEvents(newId);
    } else {
      tokenEvents.value = [];
      error.value = new Error("Invalid User ID");
    }
  },
  { immediate: false }
);
</script>
