<script setup lang="ts">
import type { Period, Range } from "~/types";
import type { UserSummaryStatsResponse } from "~/stores/stats.store";

const props = defineProps<{
  period: Period;
  range: Range;
}>();

interface StatCard {
  title: string;
  icon: string;
  value: string | number;
  loading?: boolean;
  error?: boolean;
}

const statsStore = useStatsStore();

const formatNumber = (value: number): string => {
  return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
};

const {
  data: stats,
  pending,
  error,
} = await useAsyncData<StatCard[]>(
  "user-activity-stats",
  async () => {
    try {
      const response = await statsStore.getUserActivitySummary();

      return [
        {
          title: "Total Users",
          icon: "i-lucide-users",
          value: formatNumber(response.total_users),
        },
        {
          title: "Daily Active",
          icon: "i-lucide-activity",
          value: formatNumber(response.daily_active_users),
        },
        {
          title: "Weekly Active",
          icon: "i-lucide-calendar-days",
          value: formatNumber(response.weekly_active_users),
        },
        {
          title: "Monthly Active",
          icon: "i-lucide-calendar",
          value: formatNumber(response.monthly_active_users),
        },
      ];
    } catch (err) {
      console.error("Failed to fetch user activity stats:", err);
      // Return placeholder cards on error
      return [
        {
          title: "Total Users",
          icon: "i-lucide-users",
          value: "—",
          error: true,
        },
        {
          title: "Daily Active",
          icon: "i-lucide-activity",
          value: "—",
          error: true,
        },
        {
          title: "Weekly Active",
          icon: "i-lucide-calendar-days",
          value: "—",
          error: true,
        },
        {
          title: "Monthly Active",
          icon: "i-lucide-calendar",
          value: "—",
          error: true,
        },
      ];
    }
  },
  {
    watch: [() => props.period, () => props.range],
    default: () => [],
  }
);
</script>

<template>
  <UPageGrid class="lg:grid-cols-4 gap-4 sm:gap-6 lg:gap-px">
    <UPageCard
      v-for="(stat, index) in stats"
      :key="index"
      :icon="stat.icon"
      :title="stat.title"
      variant="subtle"
      :ui="{
        container: 'gap-y-1.5',
        leading: 'p-2.5 rounded-full bg-(--ui-primary)/10 ring ring-inset ring-(--ui-primary)/25',
        title: 'font-normal text-(--ui-text-muted) text-xs uppercase',
      }"
      class="lg:rounded-none first:rounded-l-[calc(var(--ui-radius)*2)] last:rounded-r-[calc(var(--ui-radius)*2)] hover:z-1"
    >
      <div class="flex items-center gap-2">
        <span class="text-2xl font-semibold" :class="stat.error ? 'text-(--ui-text-muted)' : 'text-(--ui-text-highlighted)'">
          {{ pending ? "Loading..." : stat.value }}
        </span>

        <div v-if="error && !pending" class="text-xs text-red-500">Error</div>
      </div>
    </UPageCard>
  </UPageGrid>
</template>
