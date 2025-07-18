<template>
  <div class="relative">
    <!-- Main Input -->
    <UInput
      v-model="inputValue"
      :name="fieldType"
      :placeholder="placeholder"
      :disabled="disabled"
      :icon="fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap'"
      @focus="handleFocus"
      @blur="handleBlur"
      @keydown="handleKeydown"
      autocomplete="off"
      :aria-expanded="showSuggestions"
      aria-haspopup="listbox"
      :aria-controls="`${fieldType}-suggestions`"
      :aria-activedescendant="highlightedIndex >= 0 ? `${fieldType}-option-${highlightedIndex}` : undefined"
    />
    
    <!-- Suggestions Dropdown -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      leave-active-class="transition-all duration-100 ease-in"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="showSuggestions && (filteredItems.length > 0 || showCreateOption)"
        :id="`${fieldType}-suggestions`"
        class="absolute z-50 w-full mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg max-h-60 overflow-auto"
        role="listbox"
      >
        <!-- Existing items -->
        <button
          v-for="(item, index) in filteredItems"
          :key="item.value"
          :id="`${fieldType}-option-${index}`"
          @mousedown.prevent="selectItem(item)"
          @mouseenter="highlightedIndex = index"
          class="w-full px-3 py-2 text-left text-sm transition-colors flex items-center gap-2"
          :class="{
            'bg-gray-100 dark:bg-gray-800': highlightedIndex === index,
            'hover:bg-gray-50 dark:hover:bg-gray-800/50': highlightedIndex !== index
          }"
          role="option"
          :aria-selected="storeValue === item.value"
        >
          <UIcon :name="item.icon" class="w-4 h-4 flex-shrink-0" />
          <span>{{ item.label }}</span>
        </button>
        
        <!-- Divider if both filtered items and create option -->
        <div v-if="filteredItems.length > 0 && showCreateOption" class="border-t border-gray-200 dark:border-gray-700" />
        
        <!-- Create new option -->
        <button
          v-if="showCreateOption"
          :id="`${fieldType}-option-create`"
          @mousedown.prevent="createItem"
          @mouseenter="highlightedIndex = filteredItems.length"
          class="w-full px-3 py-2 text-left text-sm transition-colors flex items-center gap-2"
          :class="{
            'bg-gray-100 dark:bg-gray-800': highlightedIndex === filteredItems.length,
            'hover:bg-gray-50 dark:hover:bg-gray-800/50': highlightedIndex !== filteredItems.length
          }"
          role="option"
        >
          <UIcon name="i-lucide-plus-circle" class="w-4 h-4 flex-shrink-0 text-primary-500" />
          <span>Create "<strong>{{ formattedInputValue }}</strong>"</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
interface Props {
  fieldType: 'resource' | 'action';
  selectedResource?: string;
  disabled?: boolean;
  placeholder?: string;
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: "Select or type...",
  disabled: false,
});

// Store
const permissionsStore = usePermissionsStore();

// State
const inputValue = ref('');
const showSuggestions = ref(false);
const highlightedIndex = ref(-1);
const isBlurring = ref(false);

// Direct binding to store form state
const storeValue = computed({
  get: () => {
    if (props.fieldType === 'resource') {
      return permissionsStore.formState.resource;
    } else {
      return permissionsStore.formState.action;
    }
  },
  set: (value: string) => {
    console.log(`[FieldCombobox ${props.fieldType}] Setting store value:`, value);
    permissionsStore.setFormField(props.fieldType, value);
  }
});

// Sync input with store value
watch(storeValue, (newVal) => {
  if (!isBlurring.value) {
    inputValue.value = newVal || '';
  }
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

// Build items list
const allItems = computed(() => {
  const items = [];
  
  // Add existing custom values with check icon
  existingValues.value.forEach(value => {
    items.push({
      label: value,
      value: value,
      icon: 'i-lucide-check-circle',
      type: 'existing'
    });
  });
  
  // Add common suggestions that aren't already used with lightbulb icon
  const unusedSuggestions = commonSuggestions.value.filter(s => 
    !existingValues.value.includes(s)
  );
  
  unusedSuggestions.forEach(value => {
    items.push({
      label: value,
      value: value,
      icon: 'i-lucide-lightbulb',
      type: 'suggestion'
    });
  });
  
  return items;
});

// Filter items based on input
const filteredItems = computed(() => {
  if (!inputValue.value) {
    return allItems.value;
  }
  
  const searchTerm = inputValue.value.toLowerCase();
  return allItems.value.filter(item => 
    item.label.toLowerCase().includes(searchTerm)
  );
});

// Format value
const formatValue = (value: string) => {
  if (!value) return '';
  return value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '_');
};

// Formatted input value for display
const formattedInputValue = computed(() => formatValue(inputValue.value));

// Show create option when input doesn't match any existing value
const showCreateOption = computed(() => {
  if (!inputValue.value) return false;
  const formatted = formatValue(inputValue.value);
  return !allItems.value.some(item => item.value === formatted);
});

// Handle focus
function handleFocus() {
  showSuggestions.value = true;
  highlightedIndex.value = -1;
}

// Handle blur
function handleBlur() {
  isBlurring.value = true;
  
  // Delay to allow click events to fire
  setTimeout(() => {
    showSuggestions.value = false;
    highlightedIndex.value = -1;
    
    // If input has value but doesn't match store, update store
    if (inputValue.value && inputValue.value !== storeValue.value) {
      const formatted = formatValue(inputValue.value);
      if (formatted) {
        // Check if this is a new value that needs to be created
        if (!existingValues.value.includes(formatted)) {
          createNewValue(formatted);
        } else {
          storeValue.value = formatted;
        }
      }
    }
    
    // Sync input with store value
    inputValue.value = storeValue.value || '';
    isBlurring.value = false;
  }, 200);
}

// Handle keyboard navigation
function handleKeydown(event: KeyboardEvent) {
  const totalOptions = filteredItems.value.length + (showCreateOption.value ? 1 : 0);
  
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault();
      if (!showSuggestions.value) {
        showSuggestions.value = true;
      }
      highlightedIndex.value = Math.min(highlightedIndex.value + 1, totalOptions - 1);
      break;
      
    case 'ArrowUp':
      event.preventDefault();
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, -1);
      break;
      
    case 'Enter':
      event.preventDefault();
      if (highlightedIndex.value >= 0 && highlightedIndex.value < filteredItems.value.length) {
        selectItem(filteredItems.value[highlightedIndex.value]);
      } else if (highlightedIndex.value === filteredItems.value.length && showCreateOption.value) {
        createItem();
      } else if (showCreateOption.value && inputValue.value) {
        createItem();
      }
      break;
      
    case 'Escape':
      event.preventDefault();
      showSuggestions.value = false;
      highlightedIndex.value = -1;
      inputValue.value = storeValue.value || '';
      break;
      
    case 'Tab':
      // Let default tab behavior happen, blur will handle the rest
      break;
  }
}

// Select an item
function selectItem(item: { label: string; value: string }) {
  console.log(`[FieldCombobox ${props.fieldType}] Selecting item:`, item);
  storeValue.value = item.value;
  inputValue.value = item.value;
  showSuggestions.value = false;
  highlightedIndex.value = -1;
  
  // Force validation update
  nextTick(() => {
    const inputEl = document.querySelector(`input[name="${props.fieldType}"]`) as HTMLInputElement;
    if (inputEl) {
      inputEl.dispatchEvent(new Event('input', { bubbles: true }));
      inputEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
}

// Create new item
function createItem() {
  const formatted = formatValue(inputValue.value);
  if (formatted) {
    console.log(`[FieldCombobox ${props.fieldType}] Creating item:`, formatted);
    createNewValue(formatted);
    inputValue.value = formatted;
    showSuggestions.value = false;
    highlightedIndex.value = -1;
  }
}

// Create new value in store
function createNewValue(value: string) {
  // Add to the store as a temporary custom permission
  if (props.fieldType === 'resource') {
    permissionsStore.addTemporaryCustomPermission(value);
  } else if (props.fieldType === 'action' && props.selectedResource) {
    permissionsStore.addTemporaryCustomPermission(props.selectedResource, value);
  }
  
  // Update the form field in the store
  storeValue.value = value;
  
  // Force validation update by triggering a DOM event
  nextTick(() => {
    const inputEl = document.querySelector(`input[name="${props.fieldType}"]`) as HTMLInputElement;
    if (inputEl) {
      inputEl.dispatchEvent(new Event('input', { bubbles: true }));
      inputEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  
  console.log(`[FieldCombobox ${props.fieldType}] Created and set value:`, value);
}
</script>