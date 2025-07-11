<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import { upperFirst } from "scule";

// Define the Reading interface for anonymous readings
interface ReadingData {
  question: string;
  coin_tosses?: number[][];
  primary_hexagram: {
    number: number;
    name?: string;
    chinese_name?: string;
  };
  secondary_hexagram?: {
    number: number;
    name?: string;
    chinese_name?: string;
  } | null;
  num_changing_lines?: number;
  interpretation?: {
    summary?: string;
    guidance?: string;
    detailed?: string;
  };
  ai_analysis?: {
    initial_insight?: string;
    current_situation?: string;
    transformation?: string;
    significant_lines?: string;
    guidance?: string;
  };
}

interface AnonymousReading {
  id: string;
  timestamp: string;
  category: string;
  type: "basic" | "advanced" | "oracle";
  data: ReadingData;
}

const UButton = resolveComponent("UButton");
const UBadge = resolveComponent("UBadge");
const UDropdownMenu = resolveComponent("UDropdownMenu");

const toast = useToast();
const table = useTemplateRef<any>("table");
const authStore = useAuthStore();

const columnFilters = ref([]);
const columnVisibility = ref();

const status = ref<"idle" | "pending" | "success" | "error">("idle");
const readings = ref<AnonymousReading[]>([]);
const totalReadings = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);

// Helper functions
const formatDate = (dateString: string): string => {
  if (!dateString) return "-";
  try {
    return new Date(dateString).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (e) {
    return "Invalid Date";
  }
};

// Fetch only anonymous readings
const fetchReadings = async () => {
  status.value = "pending";
  try {
    const skip = (currentPage.value - 1) * pageSize.value;
    const limit = pageSize.value;

    const anonParams = new URLSearchParams({
      limit: limit.toString(),
      skip: skip.toString(),
    });

    const anonResponse = await authStore.apiCall<{ readings: AnonymousReading[]; total: number } | AnonymousReading[]>(`/admin/anonymous-readings?${anonParams}`);

    // Handle new API response format: {readings: [...], total: count}
    if (anonResponse && typeof anonResponse === "object" && "readings" in anonResponse && "total" in anonResponse) {
      readings.value = anonResponse.readings;
      totalReadings.value = anonResponse.total;
    } else if (Array.isArray(anonResponse)) {
      // Fallback for old API format
      readings.value = anonResponse;

      // If this is the first page or we don't have a total yet, get the total count
      if (currentPage.value === 1 || totalReadings.value === 0) {
        try {
          const allResponse = await authStore.apiCall<AnonymousReading[]>(`/admin/anonymous-readings`);
          totalReadings.value = Array.isArray(allResponse) ? allResponse.length : 0;
        } catch (err) {
          console.error("Failed to get total count:", err);
          // Fallback: if we got a full page, assume there might be more
          totalReadings.value = anonResponse.length === limit ? currentPage.value * limit + 1 : (currentPage.value - 1) * limit + anonResponse.length;
        }
      }
    } else {
      console.error("Unexpected response format:", anonResponse);
      readings.value = [];
      totalReadings.value = 0;
    }

    status.value = "success";
  } catch (err: any) {
    console.error("Error fetching anonymous readings:", err);
    status.value = "error";
    readings.value = [];
    totalReadings.value = 0;
    toast.add({
      title: "Error Loading Anonymous Readings",
      description: err.message || "Could not load anonymous readings.",
      color: "error",
    });
  }
};

// Define table columns for anonymous readings
const columns: TableColumn<AnonymousReading>[] = [
  {
    accessorKey: "timestamp",
    header: "Date",
    cell: ({ row }) => formatDate(row.original.timestamp),
  },
  {
    accessorKey: "data.question",
    header: "Question",
    cell: ({ row }) => h("span", { class: "block" }, row.original.data?.question || "No question"),
  },
  {
    id: "hexagrams",
    header: "Hexagrams",
    cell: ({ row }) => {
      let hexString = row.original.data?.primary_hexagram?.number?.toString() || "?";
      if (row.original.data?.secondary_hexagram) {
        hexString += ` → ${row.original.data.secondary_hexagram.number}`;
      }
      return h("span", { class: "font-mono" }, hexString);
    },
  },
  {
    accessorKey: "data.num_changing_lines",
    header: "Lines",
    cell: ({ row }) => {
      const changingLines = row.original.data?.num_changing_lines || 0;
      if (changingLines === 0) {
        return h("span", { class: "text-gray-400" }, "None");
      }
      return h("span", changingLines.toString());
    },
  },
];

// Pagination and handlers
const pagination = ref({
  pageIndex: 0,
  pageSize: 10,
});

// Simple pagination - watch currentPage changes
watch(currentPage, () => {
  console.log("Current page changed to:", currentPage.value);
  pagination.value.pageIndex = currentPage.value - 1;
  fetchReadings();
});

onMounted(() => {
  fetchReadings();
});

type TableApiColumn = {
  id: string;
  getCanHide: () => boolean;
  getIsVisible: () => boolean;
  toggleVisibility: (value: boolean) => void;
};
</script>

<template>
  <div class="-mt-6">
    <UTable
      ref="table"
      v-model:column-filters="columnFilters"
      v-model:column-visibility="columnVisibility"
      v-model:pagination="pagination"
      :pagination-options="{
        manualPagination: true,
        pageCount: Math.ceil(totalReadings / pagination.pageSize),
      }"
      class="shrink-0"
      :data="readings"
      :columns="columns"
      :loading="status === 'pending'"
      sticky
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
        Showing {{ (currentPage - 1) * pagination.pageSize + 1 }} - {{ Math.min(currentPage * pagination.pageSize, totalReadings) }} of {{ totalReadings }} anonymous readings.
      </div>

      <div class="flex items-center gap-1.5">
        <UPagination v-model:page="currentPage" :items-per-page="pageSize" :total="totalReadings" />
      </div>
    </div>
  </div>
</template>
