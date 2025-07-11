<template>
  <UPopover>
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
        v-model:search-term="inputValue"
      />
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
const inputValue = ref(props.modelValue || "");

// Watch for changes in modelValue prop
watch(
  () => props.modelValue,
  (newValue) => {
    inputValue.value = newValue || "";
  }
);

// Fetch entity type suggestions
const { data: suggestions, pending } = await useLazyAsyncData(
  `entity-type-suggestions-${props.entityClass}-${props.platformId}`,
  () =>
    entitiesStore.fetchEntityTypeSuggestions({
      entityClass: props.entityClass,
      platformId: props.platformId,
      search: inputValue.value,
    }),
  {
    default: () => ({ suggestions: [], total: 0 }),
    watch: [() => props.entityClass, () => props.platformId],
  }
);

// Computed command groups
const commandGroups = computed(() => {
  const groups: any[] = [];

  if (!suggestions.value?.suggestions) return groups;

  // Separate suggestions by type
  const predefinedSuggestions = suggestions.value.suggestions.filter((s) => s.is_predefined);
  const recentSuggestions = suggestions.value.suggestions.filter((s) => !s.is_predefined && s.count > 0);

  // Create new option if input doesn't match existing
  const formattedInput = inputValue.value ? inputValue.value.toLowerCase().replace(/\s+/g, "_") : "";
  const matchesExisting = suggestions.value.suggestions.some((s) => s.entity_type === formattedInput);

  if (inputValue.value && !matchesExisting) {
    groups.push({
      id: "create-new",
      label: "Create New",
      items: [
        {
          id: `create-${formattedInput}`,
          label: `Create "${formatEntityTypeLabel(formattedInput)}"`,
          entity_type: formattedInput,
          chip: { label: "New", color: "primary" },
          icon: "i-lucide-plus",
        },
      ],
    });
  }

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
  }
}

// Watch inputValue changes for auto-formatting
watch(inputValue, (newValue) => {
  if (newValue && typeof newValue === "string") {
    const formattedValue = newValue.toLowerCase().replace(/\s+/g, "_");
    emit("update:modelValue", formattedValue);
  }
});

// Watch for external value changes
watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      selectedValue.value = {
        id: newValue,
        label: formatEntityTypeLabel(newValue),
        entity_type: newValue,
      };
    } else {
      selectedValue.value = null;
    }
  },
  { immediate: true }
);

// Initialize input value
watchEffect(() => {
  if (props.modelValue && !inputValue.value) {
    inputValue.value = formatEntityTypeLabel(props.modelValue);
  }
});
</script>
