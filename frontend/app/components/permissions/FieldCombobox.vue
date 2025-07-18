<template>
  <UInputMenu
    :model-value="modelValue"
    @update:model-value="handleUpdate"
    v-model:search-term="searchTerm"
    v-model:open="isOpen"
    :items="items"
    :placeholder="placeholder"
    :disabled="disabled"
    :icon="fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap'"
    :create-item="true"
    @create="handleCreate"
  >
    <template #item-leading="{ item }">
      <UIcon :name="item.icon" class="w-4 h-4" />
    </template>
    
    <template #create-item-label="{ searchTerm: currentSearchTerm }">
      <span class="flex items-center gap-2">
        <UIcon name="i-lucide-plus-circle" class="w-4 h-4" />
        Create "<strong>{{ formatValue(currentSearchTerm || searchTerm) }}</strong>"
      </span>
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
  'update:modelValue': [value: string];
}>();

// Store
const permissionsStore = usePermissionsStore();

// Local state
const searchTerm = ref('');

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

// Build items list for UInputMenu
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
  
  console.log(`[FieldCombobox ${props.fieldType}] Items:`, allItems.length, 'items');
  return allItems;
});

// Format value
const formatValue = (value: string) => {
  if (!value) return '';
  return value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '_');
};

// Handle selection update
function handleUpdate(value: string | InputMenuItem) {
  console.log(`[FieldCombobox ${props.fieldType}] handleUpdate:`, value);
  
  // Handle both string and object values
  let selectedValue = '';
  if (typeof value === 'string') {
    selectedValue = value;
  } else if (value && typeof value === 'object' && 'value' in value) {
    selectedValue = value.value || '';
  }
  
  // Clear search term when selecting
  searchTerm.value = '';
  
  emit('update:modelValue', selectedValue);
}


// Track open state for forcing close after create
const isOpen = ref(false);

// Handle create new item
function handleCreate(value: string) {
  console.log(`[FieldCombobox ${props.fieldType}] handleCreate called with:`, value);
  
  const formattedValue = formatValue(value);
  console.log(`[FieldCombobox ${props.fieldType}] Formatted value:`, formattedValue);
  
  if (formattedValue) {
    // Add to the store as a temporary custom permission
    if (props.fieldType === 'resource') {
      permissionsStore.addTemporaryCustomPermission(formattedValue);
    } else if (props.fieldType === 'action' && props.selectedResource) {
      permissionsStore.addTemporaryCustomPermission(props.selectedResource, formattedValue);
    }
    
    // Clear search term to reset the input
    searchTerm.value = '';
    
    // Emit the formatted value
    emit('update:modelValue', formattedValue);
    
    // Force close the dropdown
    isOpen.value = false;
    
    console.log(`[FieldCombobox ${props.fieldType}] Created and emitted value:`, formattedValue);
  }
}
</script>