<script setup lang="ts">
import { eachDayOfInterval, eachWeekOfInterval, eachMonthOfInterval, format, parseISO } from "date-fns";
import { VisXYContainer, VisLine, VisAxis, VisArea, VisCrosshair, VisTooltip } from "@unovis/vue";
import type { Period, Range } from "~/types";
import type { AnonymousReadingsStatsResponse } from "~/stores/stats.store";

const cardRef = useTemplateRef<HTMLElement | null>("cardRef");

const props = defineProps<{
  period: Period;
  range: Range;
}>();

type DataRecord = {
  date: Date;
  count: number;
};

const { width } = useElementSize(cardRef);
const statsStore = useStatsStore();

// Use real API data instead of mock data
const { data, pending, error } = await useAsyncData<DataRecord[]>(
  async () => {
    try {
      const response = await statsStore.getAnonymousReadingsStats(props.period, props.range);

      // Convert API response to chart data format
      return response.data_points.map((point) => ({
        date: parseISO(point.timestamp),
        count: point.count,
      }));
    } catch (err) {
      console.error("Failed to fetch anonymous readings stats:", err);
      // Return empty array on error
      return [];
    }
  },
  {
    watch: [() => props.period, () => props.range],
    default: () => [],
  }
);

const x = (_: DataRecord, i: number) => i;
const y = (d: DataRecord) => d.count;

const total = computed(() => data.value.reduce((acc: number, { count }) => acc + count, 0));

const formatNumber = new Intl.NumberFormat("en", { maximumFractionDigits: 0 }).format;

const formatDate = (date: Date): string => {
  return {
    daily: format(date, "d MMM"),
    weekly: format(date, "d MMM"),
    monthly: format(date, "MMM yyy"),
  }[props.period];
};

const xTicks = (i: number) => {
  if (i === 0 || i === data.value.length - 1 || !data.value[i]) {
    return "";
  }

  return formatDate(data.value[i].date);
};

const template = (d: DataRecord) => `${formatDate(d.date)}: ${formatNumber(d.count)} readings`;
</script>

<template>
  <UCard ref="cardRef" :ui="{ body: '!px-0 !pt-0 !pb-3' }">
    <template #header>
      <div>
        <p class="text-xs text-(--ui-text-muted) uppercase mb-1.5">Anonymous Readings</p>
        <p class="text-3xl text-(--ui-text-highlighted) font-semibold">
          {{ formatNumber(total) }}
        </p>
        <div v-if="pending" class="text-xs text-(--ui-text-muted) mt-1">Loading...</div>
        <div v-if="error" class="text-xs text-red-500 mt-1">Failed to load data</div>
      </div>
    </template>

    <VisXYContainer :data="data" :padding="{ top: 40 }" class="h-96" :width="width">
      <VisLine :x="x" :y="y" color="var(--ui-primary)" />
      <VisArea :x="x" :y="y" color="var(--ui-primary)" :opacity="0.1" />

      <VisAxis type="x" :x="x" :tick-format="xTicks" />

      <VisCrosshair color="var(--ui-primary)" :template="template" />

      <VisTooltip />
    </VisXYContainer>
  </UCard>
</template>

<style scoped>
.unovis-xy-container {
  --vis-crosshair-line-stroke-color: var(--ui-primary);
  --vis-crosshair-circle-stroke-color: var(--ui-bg);

  --vis-axis-grid-color: var(--ui-border);
  --vis-axis-tick-color: var(--ui-border);
  --vis-axis-tick-label-color: var(--ui-text-dimmed);

  --vis-tooltip-background-color: var(--ui-bg);
  --vis-tooltip-border-color: var(--ui-border);
  --vis-tooltip-text-color: var(--ui-text-highlighted);
}
</style>
