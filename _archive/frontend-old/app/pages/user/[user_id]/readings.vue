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
        title="Error Loading Readings"
        :description="typeof error === 'string' ? error : error instanceof Error ? error.message : 'Could not load user readings.'"
      />
    </div>
    <div v-else-if="readings.length > 0">
      <UTable
        :columns="columns"
        :data="readings"
        :loading="loading"
        :ui="{
          thead: '[&>tr]:bg-(--ui-bg-elevated)/50 [&>tr]:after:content-none',
          tbody: '[&>tr]:last:[&>td]:border-b-0 [&>tr]:cursor-pointer [&>tr]:hover:bg-gray-50 dark:[&>tr]:hover:bg-gray-800/50',
          th: 'py-1 border-y border-(--ui-border) first:border-l last:border-r',
          td: 'border-b border-(--ui-border) whitespace-nowrap',
        }"
        @select="(row) => openReadingDrawer(row.original)"
      />
      <!-- Add UPagination here if needed later -->
    </div>
    <div v-else class="text-center py-12">
      <UIcon name="i-lucide-book-open" class="h-12 w-12 text-muted mx-auto mb-4" />
      <p class="text-lg font-medium">No Readings Found</p>
      <p class="text-muted mt-1">This user hasn't performed any readings yet.</p>
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
              <!-- Changing Lines Badge (moved here) -->
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

              <!-- LLM Minimal Summary (moved here) -->
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

<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";

// Interface based on API response structure
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
  user_id: string;
  timestamp: string;
  category: string;
  type: "basic" | "advanced" | "oracle";
  data: ReadingData;
  llm_minimal_summary?: {
    summary?: string;
    status?: string;
  };
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

// Helper function to get type color
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

// Helper function to get hexagram lines (simplified representation)
const getHexagramLines = (number: number): ("solid" | "broken")[] => {
  // This is a simplified representation - you may want to implement actual hexagram lookup
  const binary = (number - 1).toString(2).padStart(6, "0");
  return binary.split("").map((bit) => (bit === "1" ? "solid" : "broken"));
};

// Helper function to get toss value
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

// Define table columns
const columns: TableColumn<Reading>[] = [
  {
    accessorKey: "timestamp",
    header: "Date",
    cell: ({ row }) => h("span", formatDate(row.original.timestamp)),
  },
  {
    accessorKey: "type",
    header: "Type",
    cell: ({ row }) => {
      const type = row.original.type;
      const color = getTypeColor(type);
      const label = type.charAt(0).toUpperCase() + type.slice(1);
      const UBadge = resolveComponent("UBadge");
      return h(UBadge, {
        color: color,
        variant: "subtle",
        label: label,
        class: "capitalize",
      });
    },
  },
  {
    accessorKey: "data.question",
    header: "Question",
    cell: ({ row }) => h("span", { class: "block max-w-xs truncate" }, row.original.data.question),
  },
  {
    id: "hexagrams",
    header: "Hexagrams",
    cell: ({ row }) => {
      let hexString = row.original.data.primary_hexagram.number.toString();
      if (row.original.data.secondary_hexagram) {
        hexString += ` → ${row.original.data.secondary_hexagram.number}`;
      }
      return h("span", hexString);
    },
  },
];

const route = useRoute();
const toast = useToast();
const authStore = useAuthStore();

const userId = computed(() => route.params.user_id as string);
const loading = ref(false);
const error = ref<any | null>(null);
const readings = ref<Reading[]>([]);

// Drawer state
const isReadingDrawerOpen = ref(false);
const selectedReading = ref<Reading | null>(null);

// Function to open reading drawer
const openReadingDrawer = (reading: Reading) => {
  selectedReading.value = reading;
  isReadingDrawerOpen.value = true;
};

// Fetch readings for the user
async function fetchReadings(id: string) {
  loading.value = true;
  error.value = null;
  console.log(`Fetching readings for user ID: ${id}`);

  try {
    const response = await authStore.apiCall<Reading[]>(`/admin/users/${id}/readings`);
    readings.value = Array.isArray(response) ? response : [];
  } catch (err: any) {
    console.error("Error fetching readings:", err);
    error.value = err;
    readings.value = [];
    toast.add({
      title: "Error Loading Readings",
      description: err.message || "Could not load readings.",
      color: "error",
    });
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  if (userId.value) {
    fetchReadings(userId.value);
  }
});

// Watch for route changes
watch(
  () => route.params.user_id,
  (newId) => {
    if (newId && typeof newId === "string") {
      fetchReadings(newId);
    } else {
      readings.value = [];
      error.value = new Error("Invalid User ID");
    }
  },
  { immediate: false }
);
</script>
