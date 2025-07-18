<template>
  <USelectMenu
    :model-value="selectedItem"
    @update:model-value="handleSelect"
    :search-input="{
      placeholder: searchPlaceholder,
      icon: fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap'
    }"
    :items="items"
    :searchable="searchFunction"
    class="w-full"
    :disabled="disabled"
    value-attribute="value"
    option-attribute="label"
    :popper="{ placement: 'bottom-start' }"
  >
    <template #empty>
      <div class="flex flex-col items-center justify-center py-6 px-4 gap-3">
        <UIcon :name="fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap'" class="w-8 h-8 text-gray-400" />
        <p class="text-sm text-gray-500">
          No {{ fieldType }}s found
        </p>
        <p class="text-xs text-gray-400">
          Type to create a new {{ fieldType }}
        </p>
      </div>
    </template>

    <template #option="{ option }">
      <div class="flex items-center gap-2">
        <UIcon :name="option.icon" class="w-4 h-4" />
        <span>{{ option.label }}</span>
        <UBadge v-if="option.isNew" label="New" color="success" variant="soft" size="xs" class="ml-auto" />
      </div>
    </template>
  </USelectMenu>
</template>

<script setup lang="ts">
interface Props {
  modelValue: string;
  fieldType: 'resource' | 'action';
  selectedResource?: string; // For action field, to filter by resource
  disabled?: boolean;
  placeholder?: string;
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: "Select or type...",
  disabled: false,
});

const emit = defineEmits<{
  "update:modelValue": [value: string];
}>();

// Store
const permissionsStore = usePermissionsStore();

// Computed
const searchPlaceholder = computed(() => 
  props.placeholder || `Search or create ${props.fieldType}...`
);

// Get existing values
const existingValues = computed(() => {
  if (props.fieldType === 'resource') {
    return permissionsStore.customResources || [];
  } else {
    return permissionsStore.customActions(props.selectedResource) || [];
  }
});

// Get common suggestions
const commonSuggestions = computed(() => {
  if (props.fieldType === 'resource') {
    return permissionsStore.commonResourceSuggestions || [];
  } else {
    return permissionsStore.commonActionSuggestions || [];
  }
});

// Custom search function that includes ability to create new items
const searchFunction = (items: any[], query: string) => {
  const search = query.toLowerCase().trim();
  
  if (!search) {
    return items;
  }
  
  // Filter existing items
  let filtered = items.filter(item => 
    item.label.toLowerCase().includes(search) || 
    item.value.toLowerCase().includes(search)
  );
  
  // Format the search query (lowercase, replace spaces with underscores)
  const formattedValue = search.replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '_');
  
  // Check if this would be a new value
  const existsInItems = items.some(item => item.value === formattedValue);
  
  // Add "create new" option if it doesn't exist
  if (!existsInItems && formattedValue) {
    filtered.unshift({
      label: formattedValue,
      value: formattedValue,
      icon: 'i-lucide-plus-circle',
      isNew: true
    });
  }
  
  return filtered;
};

// Build items list
const items = computed(() => {
  const allItems: any[] = [];
  
  // Add existing custom values
  if (existingValues.value.length > 0) {
    existingValues.value.forEach(value => {
      allItems.push({
        label: value,
        value: value,
        icon: 'i-lucide-check-circle',
      });
    });
  }
  
  // Add common suggestions that aren't already used
  const unusedSuggestions = commonSuggestions.value.filter(s => 
    !existingValues.value.includes(s)
  );
  
  if (unusedSuggestions.length > 0) {
    unusedSuggestions.forEach(value => {
      allItems.push({
        label: value,
        value: value,
        icon: 'i-lucide-lightbulb',
      });
    });
  }
  
  return allItems;
});

// Current selected item
const selectedItem = computed(() => {
  if (!props.modelValue) return null;
  
  // Find in items or create a new one
  const existing = items.value.find(item => item.value === props.modelValue);
  if (existing) return existing;
  
  // Return a custom item for the current value
  return {
    label: props.modelValue,
    value: props.modelValue,
    icon: props.fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap'
  };
});

// Handle selection
function handleSelect(item: any) {
  if (item && item.value) {
    emit("update:modelValue", item.value);
  }
}
</script>