<template>
  <div>
    <div v-if="loading" class="space-y-2">
      <USkeleton v-for="i in 5" :key="i" class="h-12 w-full" />
    </div>
    <div v-else-if="error">
      <UAlert
        icon="i-lucide-alert-triangle"
        color="error"
        variant="subtle"
        title="Error Loading Transactions"
        :description="typeof error === 'string' ? error : error instanceof Error ? error.message : 'Could not load transactions.'"
      />
    </div>
    <div v-else-if="transactions.length > 0">
      <UTable
        :columns="columns"
        :data="transactions"
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
      <UIcon name="i-lucide-receipt" class="h-12 w-12 text-muted mx-auto mb-4" />
      <p class="text-lg font-medium">No Transactions Found</p>
      <p class="text-muted mt-1">This user has no payment history yet.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";

// Interface for combined payment data from API
interface PaymentTransaction {
  id: string;
  type: "event" | "intent";
  user_id: string;
  account_id: string;
  timestamp: string;
  amount: string | number; // Can be string or number from API
  currency: string;
  provider: string;
  event_type?: string; // For events
  status?: string; // For intents
  details?: {
    payment_intent_id?: string;
    provider_payment_id?: string;
    metadata?: {
      pack_type?: string;
      base_tokens?: number;
      bonus_tokens?: number;
      user_id?: string;
      [key: string]: any;
    };
    [key: string]: any;
  };
  payment_method_id?: string;
  token_amount?: number;
  transaction_type?: string;
}

// Interface for API response
interface PaymentTransactionsResponse {
  data: PaymentTransaction[];
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

// Helper function to get status/event color and label
const getStatusStyle = (transaction: PaymentTransaction) => {
  const status = transaction.event_type || transaction.status || "";

  if (status.includes("succeeded") || status.includes("success")) {
    return { color: "success" as const, label: "Success" };
  }
  if (status.includes("failed") || status.includes("error")) {
    return { color: "error" as const, label: "Failed" };
  }
  if (status.includes("pending") || status.includes("processing")) {
    return { color: "warning" as const, label: "Pending" };
  }
  if (status.includes("refunded")) {
    return { color: "info" as const, label: "Refunded" };
  }
  if (status.includes("cancelled")) {
    return { color: "neutral" as const, label: "Cancelled" };
  }

  return { color: "neutral" as const, label: status || "Unknown" };
};

// Helper function to get transaction type color
const getTypeColor = (type: string): "info" | "primary" => {
  return type === "event" ? "info" : "primary";
};

// Define table columns
const columns: TableColumn<PaymentTransaction>[] = [
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
    accessorKey: "type",
    header: "Type",
    cell: ({ row }) => {
      const UBadge = resolveComponent("UBadge");
      const color = getTypeColor(row.original.type);

      return h(UBadge, {
        color: color,
        variant: "soft",
        label: row.original.type,
        class: "capitalize text-xs",
      });
    },
  },
  {
    accessorKey: "amount",
    header: "Amount",
    cell: ({ row }) => {
      const amount = typeof row.original.amount === "string" ? parseFloat(row.original.amount) : row.original.amount;
      const currency = row.original.currency || "USD";

      if (!amount && amount !== 0) return h("span", { class: "text-muted" }, "-");

      const formatted = amount.toLocaleString(undefined, {
        style: "currency",
        currency: currency.toUpperCase(),
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });

      return h("span", { class: "font-medium text-primary" }, formatted);
    },
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const style = getStatusStyle(row.original);
      const UBadge = resolveComponent("UBadge");

      return h(UBadge, {
        color: style.color,
        variant: "subtle",
        label: style.label,
        class: "text-xs",
      });
    },
  },
  {
    accessorKey: "provider",
    header: "Provider",
    cell: ({ row }) => {
      const UIcon = resolveComponent("UIcon");
      const provider = row.original.provider || "unknown";

      const providerIcons: Record<string, string> = {
        stripe: "i-lucide-credit-card",
        paypal: "i-lucide-wallet",
        apple: "i-lucide-smartphone",
        google: "i-lucide-chrome",
      };

      return h("div", { class: "flex items-center space-x-2" }, [
        h(UIcon, {
          name: providerIcons[provider.toLowerCase()] || "i-lucide-building",
          class: "h-4 w-4 text-muted",
        }),
        h("span", { class: "text-sm capitalize" }, provider),
      ]);
    },
  },
  {
    accessorKey: "details",
    header: "Details",
    cell: ({ row }) => {
      const transaction = row.original;
      const parts: string[] = [];
      const secondaryParts: string[] = [];

      // Check for pack information in metadata
      if (transaction.details?.metadata?.pack_type) {
        const metadata = transaction.details.metadata;
        const packType = metadata.pack_type!.charAt(0).toUpperCase() + metadata.pack_type!.slice(1);
        parts.push(`${packType} Pack`);

        // Add token information
        if (metadata.base_tokens) {
          const tokenInfo = metadata.bonus_tokens ? `${metadata.base_tokens} + ${metadata.bonus_tokens} tokens` : `${metadata.base_tokens} tokens`;
          parts.push(tokenInfo);
        }
      }

      // Fallback to existing logic if no pack metadata
      if (parts.length === 0) {
        if (transaction.token_amount) {
          parts.push(`${transaction.token_amount} tokens`);
        }

        if (transaction.transaction_type) {
          parts.push(transaction.transaction_type.replace("_", " "));
        }
      }

      // Add payment method info to secondary line
      if (transaction.payment_method_id) {
        secondaryParts.push(`Method: ${transaction.payment_method_id.slice(-4)}`);
      }

      // Add provider payment ID if available
      if (transaction.details?.provider_payment_id) {
        secondaryParts.push(`Payment: ${transaction.details.provider_payment_id.slice(-8)}`);
      } else {
        secondaryParts.push(`ID: ${transaction.id.slice(-8)}`);
      }

      const mainText = parts.length > 0 ? parts.join(" • ") : "Payment transaction";
      const subText = secondaryParts.join(" • ");

      return h("div", { class: "max-w-xs" }, [h("div", { class: "text-sm text-gray-900 dark:text-gray-100 truncate" }, mainText), h("div", { class: "text-xs text-muted mt-1 truncate" }, subText)]);
    },
  },
];

const route = useRoute();
const toast = useToast();
const authStore = useAuthStore();

const userId = computed(() => route.params.user_id as string);
const loading = ref(false);
const error = ref<any | null>(null);
const transactions = ref<PaymentTransaction[]>([]);

// Fetch payment transactions for the user using admin API
async function fetchTransactions(id: string) {
  loading.value = true;
  error.value = null;
  console.log(`Fetching payment transactions for user ID: ${id}`);

  try {
    const response = await authStore.apiCall<PaymentTransactionsResponse>(`/admin/users/${id}/payments`);
    transactions.value = response.data || [];
  } catch (err: any) {
    console.error("Error fetching payment transactions:", err);
    error.value = err;
    transactions.value = [];
    toast.add({
      title: "Error Loading Transactions",
      description: err.message || "Could not load payment transactions.",
      color: "error",
    });
  } finally {
    loading.value = false;
  }
}

// Fetch data on mount
onMounted(() => {
  if (userId.value) {
    fetchTransactions(userId.value);
  }
});

// Watch for route changes
watch(
  () => route.params.user_id,
  (newId) => {
    if (newId && typeof newId === "string") {
      fetchTransactions(newId);
    } else {
      transactions.value = [];
      error.value = new Error("Invalid User ID");
    }
  },
  { immediate: false }
);
</script>
