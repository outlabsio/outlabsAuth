<template>
  <UDrawer
    v-model:open="open"
    direction="right"
    handle-only
    :ui="{
      content: 'w-full max-w-6xl',
      header: 'sticky top-0 z-10',
      body: 'overflow-y-auto',
    }"
  >
    <!-- This should be empty as the trigger is external -->

    <!-- Header -->
    <template #header v-if="palace">
      <div class="flex justify-between items-center w-full">
        <div class="flex items-center">
          <div class="text-4xl mr-3">{{ palace.ruling_trigram_symbol }}</div>
          <div>
            <h3 class="text-xl font-bold">{{ palace.palace_name }}</h3>
            <p class="text-sm text-muted">{{ palace.palace_identifier }} Palace • #{{ palace.palace_number }}</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <UBadge :color="getElementColor(palace.palace_identifier)" size="sm">
            {{ palace.element_name }}
          </UBadge>
        </div>
      </div>
    </template>

    <!-- Body -->
    <template #body>
      <div v-if="palace" class="p-4">
        <!-- Palace visual representation -->
        <div class="flex items-center justify-center mb-8">
          <div class="text-center">
            <div class="text-8xl mb-2">{{ palace.ruling_trigram_symbol }}</div>
            <div class="space-y-2">
              <UBadge :color="getElementColor(palace.palace_identifier)" size="lg">
                {{ palace.element_name }}
              </UBadge>
              <div class="text-sm text-muted">{{ palace.ruling_trigram_name }}</div>
            </div>
          </div>
        </div>

        <!-- Tabs for organizing enhanced palace content -->
        <UTabs
          :items="[
            {
              label: 'Overview',
              slot: 'overview',
              icon: 'i-lucide-eye',
            },
            {
              label: 'Hexagram Sequence',
              slot: 'hexagrams',
              icon: 'i-lucide-layers',
            },
            {
              label: 'Najia Assignments',
              slot: 'najia',
              icon: 'i-lucide-compass',
            },
            {
              label: 'Translation Keys',
              slot: 'keys',
              icon: 'i-lucide-key',
            },
          ]"
          class="w-full"
        >
          <!-- Overview Tab -->
          <template #overview>
            <PalacesOverview />
          </template>

          <!-- Hexagram Sequence Tab -->
          <template #hexagrams>
            <PalacesHexagramSequence />
          </template>

          <!-- Najia Assignments Tab -->
          <template #najia>
            <PalacesNajiaAssignments />
          </template>

          <!-- Translation Keys Tab -->
          <template #keys>
            <PalacesPalaceTranslationKeys />
          </template>
        </UTabs>
      </div>
    </template>
  </UDrawer>
</template>

<script setup lang="ts">
import { PalacesOverview } from "#components";
import type { EnhancedPalace } from "~/stores/palaces.store";

interface Props {
  palace: EnhancedPalace | null;
}

defineProps<Props>();

// Use v-model for the open state
const open = defineModel<boolean>("open", { default: false });

// Helper function for element colors using Nuxt UI 3 color system
const getElementColor = (identifier: string): "error" | "primary" | "neutral" | "secondary" | "success" | "info" | "warning" => {
  const colorMap: Record<string, "error" | "primary" | "neutral" | "secondary" | "success" | "info" | "warning"> = {
    qian: "neutral",
    li: "error",
    dui: "primary",
    zhen: "success",
    xun: "info",
    kan: "primary",
    gen: "warning",
    kun: "warning",
  };
  return colorMap[identifier] || "neutral";
};
</script>
