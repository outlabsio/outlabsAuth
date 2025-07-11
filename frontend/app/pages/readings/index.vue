<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import { upperFirst } from "scule";
import { type Row } from "@tanstack/table-core";

// Define the Reading interface
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

interface Reading {
  id: string;
  user_id: string; // Required for user readings
  timestamp: string;
  category: string;
  type: "basic" | "advanced" | "oracle";
  data: ReadingData;
  llm_minimal_summary?: {
    summary?: string;
    status?: string;
  };
}

const UAvatar = resolveComponent("UAvatar");
const UButton = resolveComponent("UButton");
const UBadge = resolveComponent("UBadge");
const UIcon = resolveComponent("UIcon");
const UDropdownMenu = resolveComponent("UDropdownMenu");

const toast = useToast();
const table = useTemplateRef<any>("table");
const authStore = useAuthStore();

const columnFilters = ref([]);
const columnVisibility = ref();

const status = ref<"idle" | "pending" | "success" | "error">("idle");
const readings = ref<Reading[]>([]);
const totalReadings = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);

// Drawer state
const isReadingDrawerOpen = ref(false);
const selectedReading = ref<Reading | null>(null);

// Filter states
const readingTypeFilter = ref("all");
const searchQuery = ref("");

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

const getTypeColor = (type: string): "info" | "warning" | "primary" | "neutral" => {
  switch (type) {
    case "basic":
      return "info";
    case "advanced":
      return "warning";
    case "oracle":
      return "primary";
    default:
      return "neutral";
  }
};

const getHexagramLines = (number: number): ("solid" | "broken")[] => {
  const binary = (number - 1).toString(2).padStart(6, "0");
  return binary.split("").map((bit) => (bit === "1" ? "solid" : "broken"));
};

const getTossValue = (toss: number[]): string => {
  const sum = toss.reduce((a, b) => a + b, 0);
  switch (sum) {
    case 6:
      return "Old Yin";
    case 7:
      return "Young Yang";
    case 8:
      return "Young Yin";
    case 9:
      return "Old Yang";
    default:
      return "Unknown";
  }
};

// Function to open reading drawer
const openReadingDrawer = (reading: Reading) => {
  selectedReading.value = reading;
  isReadingDrawerOpen.value = true;
};

// Handle row click
const handleRowClick = (row: Row<Reading>) => {
  if (!row || !row.original) {
    console.error("Invalid row data:", row);
    toast.add({ title: "Error", description: "Could not open reading details.", color: "error" });
    return;
  }
  openReadingDrawer(row.original);
};

// Fetch only user readings with proper server-side pagination
const fetchReadings = async () => {
  status.value = "pending";
  try {
    const skip = (currentPage.value - 1) * pageSize.value;
    const limit = pageSize.value;

    const userParams = new URLSearchParams({
      limit: limit.toString(),
      skip: skip.toString(),
    });

    // Add server-side filtering if supported by the API
    if (readingTypeFilter.value !== "all") {
      userParams.append("reading_type", readingTypeFilter.value);
    }
    if (searchQuery.value) {
      userParams.append("search", searchQuery.value);
    }

    const userResponse = await authStore.apiCall<{ readings: Reading[]; total: number } | Reading[]>(`/admin/readings?${userParams}`);

    // Handle new API response format: {readings: [...], total: count}
    if (userResponse && typeof userResponse === "object" && "readings" in userResponse && "total" in userResponse) {
      readings.value = userResponse.readings;
      totalReadings.value = userResponse.total;
    } else if (Array.isArray(userResponse)) {
      // Fallback for old API format
      readings.value = userResponse;

      // If this is the first page or we don't have a total yet, get the total count
      if (currentPage.value === 1 || totalReadings.value === 0) {
        try {
          // Get total count without pagination
          const countParams = new URLSearchParams();
          if (readingTypeFilter.value !== "all") {
            countParams.append("reading_type", readingTypeFilter.value);
          }
          if (searchQuery.value) {
            countParams.append("search", searchQuery.value);
          }

          const allResponse = await authStore.apiCall<Reading[]>(`/admin/readings?${countParams}`);
          totalReadings.value = Array.isArray(allResponse) ? allResponse.length : 0;
        } catch (err) {
          console.error("Failed to get total count:", err);
          // Fallback: if we got a full page, assume there might be more
          totalReadings.value = userResponse.length === limit ? currentPage.value * limit + 1 : (currentPage.value - 1) * limit + userResponse.length;
        }
      }
    } else {
      console.error("Unexpected response format:", userResponse);
      readings.value = [];
      totalReadings.value = 0;
    }

    status.value = "success";
  } catch (err: any) {
    console.error("Error fetching user readings:", err);
    status.value = "error";
    readings.value = [];
    totalReadings.value = 0;
    toast.add({
      title: "Error Loading User Readings",
      description: err.message || "Could not load user readings.",
      color: "error",
    });
  }
};

// Define table columns (simplified for user readings)
const columns: TableColumn<Reading>[] = [
  {
    accessorKey: "timestamp",
    header: "Date",
    cell: ({ row }) => formatDate(row.original.timestamp),
  },
  {
    accessorKey: "user_id",
    header: "User",
    cell: ({ row }) => {
      return h(
        "div",
        {
          class: "flex items-center gap-2 cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-700 p-2 rounded-lg transition-colors group",
          onClick: (e: Event) => {
            e.stopPropagation(); // Prevent row click from opening reading drawer
            navigateTo(`/user/${row.original.user_id}`);
          },
        },
        [
          h(UIcon, {
            name: "i-lucide-user",
            class: "w-5 h-5 text-neutral-500 dark:text-neutral-400",
          }),
          h(
            "span",
            {
              class: "font-mono text-xs text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 group-hover:underline",
            },
            row.original.user_id?.slice(0, 8) + "..." || "Unknown"
          ),
        ]
      );
    },
  },
  {
    accessorKey: "type",
    header: "Type",
    cell: ({ row }) => {
      const type = row.original.type;
      const color = getTypeColor(type);
      const label = type.charAt(0).toUpperCase() + type.slice(1);
      return h(UBadge, {
        color: color,
        variant: "subtle",
        label: label,
        class: "capitalize",
      });
    },
  },
  {
    accessorKey: "data.ai_analysis",
    header: "AI Analysis",
    cell: ({ row }) => {
      const hasAiAnalysis =
        row.original.data?.ai_analysis &&
        (row.original.data.ai_analysis.initial_insight ||
          row.original.data.ai_analysis.current_situation ||
          row.original.data.ai_analysis.transformation ||
          row.original.data.ai_analysis.significant_lines ||
          row.original.data.ai_analysis.guidance);

      return h(UBadge, {
        color: hasAiAnalysis ? "success" : "neutral",
        variant: "subtle",
        label: "AI",
        class: "text-xs",
      });
    },
  },
  {
    accessorKey: "data.question",
    header: "Question",
    cell: ({ row }) => h("span", { class: "block max-w-xs truncate" }, row.original.data?.question || "No question"),
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
];

// Pagination and other handlers
const pagination = ref({
  pageIndex: 0,
  pageSize: 10,
});

// Simple pagination - watch currentPage changes
watch(currentPage, () => {
  pagination.value.pageIndex = currentPage.value - 1;
  fetchReadings();
});

// Remove all the complex watchers and use simple ones
watch([readingTypeFilter], () => {
  currentPage.value = 1;
  totalReadings.value = 0;
  fetchReadings();
});

const debouncedSearch = useDebounceFn(() => {
  currentPage.value = 1;
  totalReadings.value = 0;
  fetchReadings();
}, 300);

watch(searchQuery, () => {
  debouncedSearch();
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
    <div class="flex flex-wrap items-center justify-between gap-1.5 mb-6">
      <UInput v-model="searchQuery" class="max-w-sm" icon="i-lucide-search" placeholder="Search user readings..." />

      <div class="flex flex-wrap items-center gap-1.5">
        <USelect
          v-model="readingTypeFilter"
          :items="[
            { label: 'All Types', value: 'all' },
            { label: 'Basic', value: 'basic' },
            { label: 'Advanced', value: 'advanced' },
            { label: 'Oracle', value: 'oracle' },
          ]"
          :ui="{ trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200' }"
          placeholder="Filter type"
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
        tbody: '[&>tr]:last:[&>td]:border-b-0 [&>tr]:cursor-pointer',
        th: 'py-1 first:rounded-l-[calc(var(--ui-radius)*2)] last:rounded-r-[calc(var(--ui-radius)*2)] border-y border-(--ui-border) first:border-l last:border-r',
        td: 'border-b border-(--ui-border)',
      }"
      @select="handleRowClick"
    />

    <div class="flex items-center justify-between gap-3 border-t border-(--ui-border) pt-4 mt-auto">
      <div class="text-sm text-(--ui-text-muted)">
        Showing {{ (currentPage - 1) * pagination.pageSize + 1 }} - {{ Math.min(currentPage * pagination.pageSize, totalReadings) }} of {{ totalReadings }} user readings.
      </div>

      <div class="flex items-center gap-1.5">
        <UPagination v-model:page="currentPage" :items-per-page="pageSize" :total="totalReadings" />
      </div>
    </div>

    <!-- Reading Details Drawer -->
    <UDrawer
      v-model:open="isReadingDrawerOpen"
      direction="right"
      class="max-w-2xl"
      :ui="{
        content: 'w-full max-w-2xl',
      }"
    >
      <!-- Drawer Header -->
      <template #header v-if="selectedReading">
        <div class="flex justify-between items-center w-full">
          <div class="flex items-center space-x-3">
            <div class="flex items-center space-x-2">
              <UIcon name="i-lucide-book-open" class="h-6 w-6 text-primary" />
              <h3 class="text-xl font-bold">Reading Details</h3>
            </div>
            <UBadge :color="getTypeColor(selectedReading.type)" variant="subtle" :label="selectedReading.type.charAt(0).toUpperCase() + selectedReading.type.slice(1)" class="capitalize" />
            <UBadge color="primary" variant="subtle" label="User" />
          </div>
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" @click="isReadingDrawerOpen = false" />
        </div>
      </template>

      <!-- Drawer Content -->
      <template #body>
        <div v-if="selectedReading" class="p-6 space-y-8">
          <!-- Reading Info Card -->
          <div class="bg-gradient-to-br from-primary-50 to-blue-50 dark:from-primary-900/20 dark:to-blue-900/20 rounded-lg p-6">
            <div class="space-y-4">
              <!-- User Info -->
              <div class="flex items-center space-x-2 mb-3">
                <UAvatar :src="`https://avatars.dicebear.com/api/initials/${selectedReading.user_id}.svg`" size="sm" />
                <span class="text-sm font-medium text-primary-700 dark:text-primary-300"> User: {{ selectedReading.user_id.slice(0, 8) }}... </span>
              </div>

              <!-- Changing Lines Badge -->
              <div v-if="selectedReading.data.num_changing_lines && selectedReading.data.num_changing_lines > 0" class="flex justify-start">
                <div class="inline-flex items-center px-3 py-1 rounded-full bg-purple-100 dark:bg-purple-900/30 border border-purple-200 dark:border-purple-700/50">
                  <UIcon name="i-lucide-arrow-right-left" class="h-3 w-3 mr-1.5 text-purple-600 dark:text-purple-400" />
                  <span class="text-xs font-medium text-purple-700 dark:text-purple-300">
                    {{ selectedReading.data.num_changing_lines }} changing {{ selectedReading.data.num_changing_lines === 1 ? "line" : "lines" }}
                  </span>
                </div>
              </div>

              <div class="flex items-start justify-between">
                <div class="space-y-2">
                  <h4 class="text-lg font-semibold text-primary-900 dark:text-primary-100">
                    {{ selectedReading.data.question }}
                  </h4>
                  <p class="text-sm text-primary-700 dark:text-primary-300">
                    {{ formatDate(selectedReading.timestamp) }}
                  </p>
                </div>
                <UIcon name="i-lucide-sparkles" class="h-8 w-8 text-primary-500" />
              </div>

              <!-- LLM Minimal Summary -->
              <div v-if="selectedReading.llm_minimal_summary?.summary" class="mt-4">
                <div
                  class="relative overflow-hidden rounded-xl bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-blue-900/30 dark:via-indigo-900/30 dark:to-purple-900/30 p-4 shadow-lg"
                >
                  <div class="absolute inset-0 bg-white/10 dark:bg-white/5"></div>
                  <div class="relative">
                    <div class="flex items-start space-x-3">
                      <div class="flex-shrink-0">
                        <div class="w-7 h-7 rounded-full bg-blue-500/20 dark:bg-blue-400/20 flex items-center justify-center">
                          <UIcon name="i-lucide-brain" class="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
                        </div>
                      </div>
                      <div class="flex-1">
                        <p class="text-xs font-medium text-blue-800 dark:text-blue-200 mb-1">AI Summary</p>
                        <p class="text-sm leading-relaxed text-gray-700 dark:text-gray-200">
                          {{ selectedReading.llm_minimal_summary.summary }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Hexagrams -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Primary Hexagram -->
            <div class="group">
              <div
                class="relative overflow-hidden rounded-xl bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-blue-900/30 dark:via-indigo-900/30 dark:to-purple-900/30 p-6 shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-[1.02]"
              >
                <div class="absolute inset-0 bg-white/10 dark:bg-white/5"></div>
                <div class="relative">
                  <!-- Hexagram Layout -->
                  <div class="flex items-center">
                    <!-- Hexagram Visual Representation (left side, 2/3 space) -->
                    <div class="w-2/3 flex justify-center">
                      <div class="space-y-3">
                        <div v-for="(line, index) in getHexagramLines(selectedReading.data.primary_hexagram.number)" :key="index" class="flex justify-center">
                          <div :class="['h-3 bg-gray-800 dark:bg-gray-200 rounded-sm shadow-sm', line === 'solid' ? 'w-20' : 'w-8']" />
                          <div v-if="line === 'broken'" class="w-4" />
                          <div v-if="line === 'broken'" class="h-3 w-8 bg-gray-800 dark:bg-gray-200 rounded-sm shadow-sm" />
                        </div>
                      </div>
                    </div>

                    <!-- Number (right side, 1/3 space) -->
                    <div class="w-1/3 flex justify-center">
                      <div class="text-6xl font-thin text-blue-900 dark:text-blue-100">
                        {{ selectedReading.data.primary_hexagram.number }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Secondary Hexagram (if exists) -->
            <div v-if="selectedReading.data.secondary_hexagram" class="group">
              <div
                class="relative overflow-hidden rounded-xl bg-gradient-to-br from-emerald-50 via-green-50 to-teal-50 dark:from-emerald-900/30 dark:via-green-900/30 dark:to-teal-900/30 p-6 shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-[1.02]"
              >
                <div class="absolute inset-0 bg-white/10 dark:bg-white/5"></div>
                <div class="relative">
                  <!-- Hexagram Layout -->
                  <div class="flex items-center">
                    <!-- Hexagram Visual Representation (left side, 2/3 space) -->
                    <div class="w-2/3 flex justify-center">
                      <div class="space-y-3">
                        <div v-for="(line, index) in getHexagramLines(selectedReading.data.secondary_hexagram.number)" :key="index" class="flex justify-center">
                          <div :class="['h-3 bg-gray-800 dark:bg-gray-200 rounded-sm shadow-sm', line === 'solid' ? 'w-20' : 'w-8']" />
                          <div v-if="line === 'broken'" class="w-4" />
                          <div v-if="line === 'broken'" class="h-3 w-8 bg-gray-800 dark:bg-gray-200 rounded-sm shadow-sm" />
                        </div>
                      </div>
                    </div>

                    <!-- Number (right side, 1/3 space) -->
                    <div class="w-1/3 flex justify-center">
                      <div class="text-6xl font-thin text-emerald-900 dark:text-emerald-100">
                        {{ selectedReading.data.secondary_hexagram.number }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Coin Tosses Section -->
          <div v-if="selectedReading.data.coin_tosses" class="space-y-4">
            <h5 class="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center">
              <UIcon name="i-lucide-coins" class="h-5 w-5 mr-2 text-amber-500" />
              Coin Tosses
            </h5>

            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <div v-for="(toss, index) in selectedReading.data.coin_tosses" :key="index" class="text-center p-3 rounded-lg bg-primary-500/30">
                <div class="text-xs text-gray-500 mb-2">Line {{ index + 1 }}</div>
                <div class="flex justify-center space-x-1 mb-2">
                  <div
                    v-for="(coin, coinIndex) in toss"
                    :key="coinIndex"
                    :class="['w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold', coin === 3 ? 'bg-yellow-200 text-yellow-800' : 'bg-gray-200 text-gray-800']"
                  >
                    {{ coin === 3 ? "H" : "T" }}
                  </div>
                </div>
                <div class="text-sm font-medium">
                  {{ getTossValue(toss) }}
                </div>
              </div>
            </div>
          </div>

          <!-- AI Analysis Section -->
          <div v-if="selectedReading.data.ai_analysis" class="space-y-6">
            <h5 class="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center">
              <UIcon name="i-lucide-cpu" class="h-5 w-5 mr-2 text-purple-500" />
              AI Analysis
            </h5>

            <div class="space-y-6">
              <!-- Initial Insight -->
              <div v-if="selectedReading.data.ai_analysis.initial_insight" class="group">
                <div
                  class="relative overflow-hidden rounded-xl bg-gradient-to-br from-purple-50 via-pink-50 to-rose-50 dark:from-purple-900/30 dark:via-pink-900/30 dark:to-rose-900/30 p-6 shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-[1.02]"
                >
                  <div class="absolute inset-0 bg-white/10 dark:bg-white/5"></div>
                  <div class="relative">
                    <div class="flex items-center space-x-3 mb-4">
                      <div class="w-10 h-10 rounded-full bg-purple-500/20 dark:bg-purple-400/20 flex items-center justify-center">
                        <UIcon name="i-lucide-lightbulb" class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                      </div>
                      <h6 class="text-base font-semibold text-purple-800 dark:text-purple-200">Initial Insight</h6>
                    </div>
                    <p class="text-sm leading-relaxed text-gray-700 dark:text-gray-200">
                      {{ selectedReading.data.ai_analysis.initial_insight }}
                    </p>
                  </div>
                </div>
              </div>

              <!-- Current Situation -->
              <div v-if="selectedReading.data.ai_analysis.current_situation" class="group">
                <div
                  class="relative overflow-hidden rounded-xl bg-gradient-to-br from-blue-50 via-cyan-50 to-teal-50 dark:from-blue-900/30 dark:via-cyan-900/30 dark:to-teal-900/30 p-6 shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-[1.02]"
                >
                  <div class="absolute inset-0 bg-white/10 dark:bg-white/5"></div>
                  <div class="relative">
                    <div class="flex items-center space-x-3 mb-4">
                      <div class="w-10 h-10 rounded-full bg-blue-500/20 dark:bg-blue-400/20 flex items-center justify-center">
                        <UIcon name="i-lucide-compass" class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                      </div>
                      <h6 class="text-base font-semibold text-blue-800 dark:text-blue-200">Current Situation</h6>
                    </div>
                    <p class="text-sm leading-relaxed text-gray-700 dark:text-gray-200">
                      {{ selectedReading.data.ai_analysis.current_situation }}
                    </p>
                  </div>
                </div>
              </div>

              <!-- Transformation -->
              <div v-if="selectedReading.data.ai_analysis.transformation" class="group">
                <div
                  class="relative overflow-hidden rounded-xl bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50 dark:from-green-900/30 dark:via-emerald-900/30 dark:to-teal-900/30 p-6 shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-[1.02]"
                >
                  <div class="absolute inset-0 bg-white/10 dark:bg-white/5"></div>
                  <div class="relative">
                    <div class="flex items-center space-x-3 mb-4">
                      <div class="w-10 h-10 rounded-full bg-green-500/20 dark:bg-green-400/20 flex items-center justify-center">
                        <UIcon name="i-lucide-arrow-right-left" class="h-5 w-5 text-green-600 dark:text-green-400" />
                      </div>
                      <h6 class="text-base font-semibold text-green-800 dark:text-green-200">Transformation</h6>
                    </div>
                    <p class="text-sm leading-relaxed text-gray-700 dark:text-gray-200">
                      {{ selectedReading.data.ai_analysis.transformation }}
                    </p>
                  </div>
                </div>
              </div>

              <!-- Significant Lines -->
              <div v-if="selectedReading.data.ai_analysis.significant_lines" class="group">
                <div
                  class="relative overflow-hidden rounded-xl bg-gradient-to-br from-orange-50 via-amber-50 to-yellow-50 dark:from-orange-900/30 dark:via-amber-900/30 dark:to-yellow-900/30 p-6 shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-[1.02]"
                >
                  <div class="absolute inset-0 bg-white/10 dark:bg-white/5"></div>
                  <div class="relative">
                    <div class="flex items-center space-x-3 mb-4">
                      <div class="w-10 h-10 rounded-full bg-orange-500/20 dark:bg-orange-400/20 flex items-center justify-center">
                        <UIcon name="i-lucide-target" class="h-5 w-5 text-orange-600 dark:text-orange-400" />
                      </div>
                      <h6 class="text-base font-semibold text-orange-800 dark:text-orange-200">Significant Lines</h6>
                    </div>
                    <div class="text-sm leading-relaxed text-gray-700 dark:text-gray-200 whitespace-pre-wrap">
                      {{ selectedReading.data.ai_analysis.significant_lines }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- AI Guidance -->
              <div v-if="selectedReading.data.ai_analysis.guidance" class="group">
                <div
                  class="relative overflow-hidden rounded-xl bg-gradient-to-br from-indigo-50 via-purple-50 to-violet-50 dark:from-indigo-900/30 dark:via-purple-900/30 dark:to-violet-900/30 p-6 shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-[1.02]"
                >
                  <div class="absolute inset-0 bg-white/10 dark:bg-white/5"></div>
                  <div class="relative">
                    <div class="flex items-center space-x-3 mb-4">
                      <div class="w-10 h-10 rounded-full bg-indigo-500/20 dark:bg-indigo-400/20 flex items-center justify-center">
                        <UIcon name="i-lucide-map" class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <h6 class="text-base font-semibold text-indigo-800 dark:text-indigo-200">AI Guidance</h6>
                    </div>
                    <p class="text-sm leading-relaxed text-gray-700 dark:text-gray-200">
                      {{ selectedReading.data.ai_analysis.guidance }}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Traditional Interpretation Section -->
          <div v-if="selectedReading.data.interpretation" class="space-y-4">
            <h5 class="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center">
              <UIcon name="i-lucide-lightbulb" class="h-5 w-5 mr-2 text-yellow-500" />
              Traditional Interpretation
            </h5>

            <UCard class="bg-gradient-to-br from-yellow-50 to-orange-50 dark:from-yellow-900/20 dark:to-orange-900/20">
              <div class="prose dark:prose-invert max-w-none">
                <div v-if="selectedReading.data.interpretation.summary" class="mb-4">
                  <h6 class="text-sm font-semibold text-yellow-800 dark:text-yellow-200 mb-2">Summary</h6>
                  <p class="text-sm">{{ selectedReading.data.interpretation.summary }}</p>
                </div>

                <div v-if="selectedReading.data.interpretation.guidance" class="mb-4">
                  <h6 class="text-sm font-semibold text-yellow-800 dark:text-yellow-200 mb-2">Guidance</h6>
                  <p class="text-sm">{{ selectedReading.data.interpretation.guidance }}</p>
                </div>

                <div v-if="selectedReading.data.interpretation.detailed" class="mb-4">
                  <h6 class="text-sm font-semibold text-yellow-800 dark:text-yellow-200 mb-2">Detailed Analysis</h6>
                  <div class="text-sm whitespace-pre-wrap">{{ selectedReading.data.interpretation.detailed }}</div>
                </div>
              </div>
            </UCard>
          </div>
        </div>
      </template>
    </UDrawer>
  </div>
</template>
