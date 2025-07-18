<template>
  <UInputMenu
    v-model="selectedItem"
    :items="items"
    :placeholder="placeholder"
    :disabled="disabled"
    :icon="fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap'"
    :create-item="true"
    value-key="value"
    @create="handleCreate"
  >
    <template #item-leading="{ item }">
      <UIcon :name="item.icon" class="w-4 h-4" />
    </template>
    
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
  </UInputMenu>
</template>

<script setup lang="ts">
import type { InputMenuItem } from '@nuxt/ui'

interface Props {
  modelValue: string;
  fieldType: 'resource' | 'action';
  selectedResource?: string;
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

// Build items list
const items = computed<InputMenuItem[]>(() => {
  const allItems: InputMenuItem[] = [];
  
  // Add existing custom values with check icon
  existingValues.value.forEach(value => {
    allItems.push({
      label: value,
      value: value,
      icon: 'i-lucide-check-circle',
    });
  });
  
  // Add common suggestions that aren't already used with lightbulb icon
  const unusedSuggestions = commonSuggestions.value.filter(s => 
    !existingValues.value.includes(s)
  );
  
  unusedSuggestions.forEach(value => {
    allItems.push({
      label: value,
      value: value,
      icon: 'i-lucide-lightbulb',
    });
  });
  
  return allItems;
});

// The selected item - find it from items based on modelValue
const selectedItem = computed({
  get: () => {
    if (!props.modelValue) return undefined;
    // Find the item that matches the current modelValue
    return items.value.find(item => item.value === props.modelValue);
  },
  set: (item: InputMenuItem | undefined) => {
    // When an item is selected, emit just the value string
    emit("update:modelValue", item?.value || '');
  }
});

// Format value
const formatValue = (value: string) => {
  if (!value) return '';
  return value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '_');
};

// Handle create new item
function handleCreate(value: string) {
  const formattedValue = formatValue(value);
  emit("update:modelValue", formattedValue);
}
</script>