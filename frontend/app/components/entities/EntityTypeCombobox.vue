<template>
  <UPopover ref="popoverRef">
    <UButton :variant="selectedValue ? 'outline' : 'outline'" :color="selectedValue ? 'primary' : 'neutral'" class="w-full justify-between" :disabled="disabled">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <UIcon name="i-lucide-hash" class="w-4 h-4 text-muted-foreground shrink-0" />
        <span class="truncate">
          {{ selectedValue ? formatEntityTypeLabel(selectedValue.entity_type) : placeholder }}
        </span>
      </div>
      <UIcon name="i-lucide-chevrons-up-down" class="w-4 h-4 text-muted-foreground shrink-0 ml-2" />
    </UButton>

    <template #content>
      <div class="flex flex-col">
        <div class="relative">
          <UCommandPalette
            v-model="selectedValue"
            :groups="commandGroups"
            :placeholder="placeholder"
            :fuse="{
              fuseOptions: {
                includeMatches: true,
                threshold: 0.3,
                keys: ['entity_type', 'label'],
              },
              resultLimit: 20,
            }"
            :ui="{ input: '[&>input]:h-8 [&>input]:text-sm' }"
            class="h-80"
            @update:model-value="handleSelect"
            v-model:search-term="searchTerm"
            @keydown.enter="handleEnter"
          />
          <!-- New badge overlay -->
          <div v-if="isCreatingNew" class="absolute top-2 right-2 z-10 pointer-events-none">
            <UBadge label="New" color="primary" variant="solid" size="sm" />
          </div>
        </div>
        <div class="flex items-center justify-end gap-2 p-2 border-t border-gray-200 dark:border-gray-700">
          <UButton color="neutral" variant="ghost" size="xs" icon="i-lucide-x" @click="handleCancel"> Cancel </UButton>
          <UButton color="primary" variant="solid" size="xs" icon="i-lucide-check" @click="handleOk"> OK </UButton>
        </div>
      </div>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
interface EntityTypeSuggestion {
  entity_type: string;
  count: number;
  last_used?: string;
  is_predefined?: boolean;
}

interface Props {
  modelValue: string;
  entityClass?: "STRUCTURAL" | "ACCESS_GROUP";
  platformId?: string;
  disabled?: boolean;
  placeholder?: string;
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: "Select or type entity type...",
  disabled: false,
});

const emit = defineEmits<{
  "update:modelValue": [value: string];
}>();

// Store
const entitiesStore = useEntitiesStore();

// State
const selectedValue = ref<any>(null);
const searchTerm = ref("");
const popoverRef = ref();

// Fetch entity type suggestions
const { data: suggestions, pending } = await useLazyAsyncData(
  `entity-type-suggestions-${props.entityClass}-${props.platformId}`,
  () =>
    entitiesStore.fetchEntityTypeSuggestions({
      entityClass: props.entityClass,
      platformId: props.platformId,
      search: searchTerm.value,
    }),
  {
    default: () => ({ suggestions: [], total: 0 }),
    watch: [() => props.entityClass, () => props.platformId, searchTerm],
  }
);

// Check if current input would create a new entity type
const isCreatingNew = computed(() => {
  if (!searchTerm.value) return false;
  const formattedInput = searchTerm.value.toLowerCase().replace(/\s+/g, "_");
  return !suggestions.value?.suggestions.some((s) => s.entity_type === formattedInput);
});

// Computed command groups
const commandGroups = computed(() => {
  const groups: any[] = [];

  if (!suggestions.value?.suggestions) return groups;

  // Separate suggestions by type
  const predefinedSuggestions = suggestions.value.suggestions.filter((s) => s.is_predefined);
  const recentSuggestions = suggestions.value.suggestions.filter((s) => !s.is_predefined && s.count > 0);

  // Recently used types
  if (recentSuggestions.length > 0) {
    groups.push({
      id: "recent",
      label: "Recently Used",
      items: recentSuggestions.map((suggestion) => ({
        id: suggestion.entity_type,
        label: formatEntityTypeLabel(suggestion.entity_type),
        entity_type: suggestion.entity_type,
        suffix: `Used ${suggestion.count} time${suggestion.count !== 1 ? "s" : ""}`,
        icon: "i-lucide-clock",
      })),
    });
  }

  // Predefined/common types
  if (predefinedSuggestions.length > 0) {
    groups.push({
      id: "predefined",
      label: "Common Types",
      items: predefinedSuggestions.map((suggestion) => ({
        id: suggestion.entity_type,
        label: formatEntityTypeLabel(suggestion.entity_type),
        entity_type: suggestion.entity_type,
        suffix: suggestion.count > 0 ? `Used ${suggestion.count} time${suggestion.count !== 1 ? "s" : ""}` : undefined,
        icon: "i-lucide-star",
      })),
    });
  }

  return groups;
});

// Utility function to format entity type labels
function formatEntityTypeLabel(entityType: string): string {
  return entityType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Handle selection
function handleSelect(item: any) {
  if (item && item.entity_type) {
    emit("update:modelValue", item.entity_type);
    // Update search term to show the selected value
    searchTerm.value = formatEntityTypeLabel(item.entity_type);
  }
  // Close popover after selection
  if (popoverRef.value) {
    popoverRef.value.close?.();
  }
}

// Handle Enter key press
function handleEnter(event: KeyboardEvent) {
  if (searchTerm.value && isCreatingNew.value) {
    // If user typed something new, create new entity type
    const formattedInput = searchTerm.value.toLowerCase().replace(/\s+/g, "_");
    emit("update:modelValue", formattedInput);
  } else if (selectedValue.value && selectedValue.value.entity_type) {
    // If user selected an existing item
    emit("update:modelValue", selectedValue.value.entity_type);
  }

  // Close popover
  if (popoverRef.value) {
    popoverRef.value.close?.();
  }
}

// Handle OK button click
function handleOk() {
  if (searchTerm.value && isCreatingNew.value) {
    // If user typed something new, create new entity type
    const formattedInput = searchTerm.value.toLowerCase().replace(/\s+/g, "_");
    emit("update:modelValue", formattedInput);
  } else if (selectedValue.value && selectedValue.value.entity_type) {
    // If user selected an existing item
    emit("update:modelValue", selectedValue.value.entity_type);
  }

  // Close popover
  if (popoverRef.value) {
    popoverRef.value.close?.();
  }
}

// Handle Cancel button click
function handleCancel() {
  // Just close the popover without emitting any changes
  if (popoverRef.value) {
    popoverRef.value.close?.();
  }
}

// Watch for external value changes (when form resets or loads existing data)
watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      selectedValue.value = {
        id: newValue,
        label: formatEntityTypeLabel(newValue),
        entity_type: newValue,
      };
      // Update search term to show the selected value
      searchTerm.value = formatEntityTypeLabel(newValue);
    } else {
      selectedValue.value = null;
      searchTerm.value = "";
    }
  },
  { immediate: true }
);
</script>
