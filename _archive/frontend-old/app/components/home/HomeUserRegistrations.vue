<script setup lang="ts">
import { format, parseISO } from "date-fns";
import { VisXYContainer, VisStackedBar, VisAxis, VisCrosshair, VisTooltip } from "@unovis/vue";
import type { Period, Range } from "~/types";
import type { UserRegistrationStatsResponse } from "~/stores/stats.store";

const cardRef = useTemplateRef<HTMLElement | null>("cardRef");

const props = defineProps<{
  period: Period;
  range: Range;
}>();

type DataRecord = {
  date: Date;
  registrations: number;
  cumulative: number;
};

const { width } = useElementSize(cardRef);
const statsStore = useStatsStore();

// Use real API data for user registrations
const { data, pending, error } = await useAsyncData<DataRecord[]>(
  async () => {
    try {
      const response = await statsStore.getUserRegistrationStats(props.period, props.range);

      // Convert API response to chart data format
      return response.data_points.map((point) => ({
        date: parseISO(point.timestamp),
        registrations: point.registrations_in_interval,
        cumulative: point.cumulative_total_users_at_interval_end,
      }));
    } catch (err) {
      console.error("Failed to fetch user registration stats:", err);
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
const y = (d: DataRecord) => d.registrations;

const totalNewRegistrations = computed(() => data.value.reduce((acc: number, { registrations }) => acc + registrations, 0));

const currentTotalUsers = computed(() => {
  const lastDataPoint = data.value[data.value.length - 1];
  return lastDataPoint?.cumulative || 0;
});

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

const template = (d: DataRecord) => `${formatDate(d.date)}: ${formatNumber(d.registrations)} new registrations<br/>Total users: ${formatNumber(d.cumulative)}`;
</script>

<template>
  <UCard ref="cardRef" :ui="{ body: '!px-0 !pt-0 !pb-3' }">
    <template #header>
      <div>
        <p class="text-xs text-(--ui-text-muted) uppercase mb-1.5">User Registrations</p>
        <div class="flex items-center gap-4">
          <div>
            <p class="text-lg font-semibold text-(--ui-text-highlighted)">
              {{ formatNumber(totalNewRegistrations) }}
            </p>
            <p class="text-xs text-(--ui-text-muted)">New users this period</p>
          </div>
          <div>
            <p class="text-lg font-semibold text-(--ui-text-highlighted)">
              {{ formatNumber(currentTotalUsers) }}
            </p>
            <p class="text-xs text-(--ui-text-muted)">Total users</p>
          </div>
        </div>
        <div v-if="pending" class="text-xs text-(--ui-text-muted) mt-1">Loading...</div>
        <div v-if="error" class="text-xs text-red-500 mt-1">Failed to load data</div>
      </div>
    </template>

    <VisXYContainer :data="data" :padding="{ top: 40 }" class="h-96" :width="width">
      <VisStackedBar :x="x" :y="y" color="var(--ui-primary)" />

      <VisAxis type="x" :x="x" :tick-format="xTicks" />

      <VisAxis type="y" :tick-format="formatNumber" />

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
