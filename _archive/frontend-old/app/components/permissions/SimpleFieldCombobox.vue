<template>
  <div class="relative">
    <!-- Main Input -->
    <UInput
      :model-value="modelValue"
      @update:model-value="handleInput"
      :placeholder="placeholder"
      :disabled="disabled"
      :icon="fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap'"
      @focus="showSuggestions = true"
      @blur="handleBlur"
      autocomplete="off"
    />
    
    <!-- Suggestions Popover -->
    <div
      v-if="showSuggestions && (filteredItems.length > 0 || (searchValue && showCreateOption))"
      class="absolute z-50 w-full mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg max-h-60 overflow-auto"
    >
      <!-- Existing items -->
      <button
        v-for="item in filteredItems"
        :key="item.value"
        type="button"
        @mousedown.prevent="selectItem(item.value)"
        class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-2"
      >
        <UIcon :name="item.icon" class="w-4 h-4 flex-shrink-0" />
        <span>{{ item.label }}</span>
      </button>
      
      <!-- Create option -->
      <button
        v-if="searchValue && showCreateOption"
        type="button"
        @mousedown.prevent="createItem"
        class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-2 border-t border-gray-200 dark:border-gray-700"
      >
        <UIcon name="i-lucide-plus-circle" class="w-4 h-4 flex-shrink-0 text-primary-500" />
        <span>Create "<strong>{{ formatValue(searchValue) }}</strong>"</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
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

// State
const showSuggestions = ref(false);
const searchValue = ref('');

// Track the search value based on model value changes
watch(() => props.modelValue, (newVal) => {
  searchValue.value = newVal || '';
}, { immediate: true });

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

// Build all items
const allItems = computed(() => {
  const items = [];
  
  // Add existing custom values
  existingValues.value.forEach(value => {
    items.push({
      label: value,
      value: value,
      icon: 'i-lucide-check-circle',
    });
  });
  
  // Add common suggestions not already used
  commonSuggestions.value
    .filter(s => !existingValues.value.includes(s))
    .forEach(value => {
      items.push({
        label: value,
        value: value,
        icon: 'i-lucide-lightbulb',
      });
    });
  
  return items;
});

// Filter items
const filteredItems = computed(() => {
  if (!searchValue.value) return allItems.value;
  
  const term = searchValue.value.toLowerCase();
  return allItems.value.filter(item => 
    item.label.toLowerCase().includes(term)
  );
});

// Show create option
const showCreateOption = computed(() => {
  if (!searchValue.value) return false;
  const formatted = formatValue(searchValue.value);
  return formatted && !existingValues.value.includes(formatted);
});

// Format value
const formatValue = (value: string) => {
  if (!value) return '';
  return value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '_');
};

// Handle input
function handleInput(value: string) {
  searchValue.value = value;
  emit('update:modelValue', value);
}

// Handle blur
function handleBlur() {
  setTimeout(() => {
    showSuggestions.value = false;
    
    // Format and validate on blur
    if (searchValue.value) {
      const formatted = formatValue(searchValue.value);
      if (formatted && formatted !== props.modelValue) {
        // Create if new
        if (!existingValues.value.includes(formatted)) {
          if (props.fieldType === 'resource') {
            permissionsStore.addTemporaryCustomPermission(formatted);
          } else if (props.fieldType === 'action' && props.selectedResource) {
            permissionsStore.addTemporaryCustomPermission(props.selectedResource, formatted);
          }
        }
        emit('update:modelValue', formatted);
      }
    }
  }, 200);
}

// Select item
function selectItem(value: string) {
  emit('update:modelValue', value);
  showSuggestions.value = false;
}

// Create item
function createItem() {
  const formatted = formatValue(searchValue.value);
  if (formatted) {
    if (props.fieldType === 'resource') {
      permissionsStore.addTemporaryCustomPermission(formatted);
    } else if (props.fieldType === 'action' && props.selectedResource) {
      permissionsStore.addTemporaryCustomPermission(props.selectedResource, formatted);
    }
    emit('update:modelValue', formatted);
    showSuggestions.value = false;
  }
}
</script>