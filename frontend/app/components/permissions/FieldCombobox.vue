<template>
  <UPopover ref="popoverRef" v-model:open="isOpen">
    <UButton :variant="modelValue ? 'outline' : 'outline'" :color="modelValue ? 'primary' : 'neutral'" class="w-full justify-between" :disabled="disabled">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <UIcon :name="fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap'" class="w-4 h-4 text-muted-foreground shrink-0" />
        <span class="truncate">
          {{ modelValue || placeholder }}
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
                keys: ['value', 'label'],
              },
              resultLimit: 20,
            }"
            :ui="{ input: '[&>input]:h-8 [&>input]:text-sm' }"
            class="h-80"
            @update:model-value="handleSelect"
            v-model:search-term="searchTerm"
            @keydown.enter="handleEnter"
          />
          <!-- New badge positioned in the top-right corner of the input area -->
          <div v-if="isCreatingNew" class="absolute top-0.5 right-3 z-10 pointer-events-none">
            <UBadge label="New" color="success" variant="soft" size="xs" />
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

// State
const selectedValue = ref<any>(null);
const searchTerm = ref("");
const popoverRef = ref();
const isOpen = ref(false);

// Get unique custom values from existing permissions
const existingValues = computed(() => {
  const values = new Set<string>();
  
  // Only get values from custom (non-system) permissions
  let relevantPermissions = permissionsStore.permissions.filter(p => !p.is_system);
  
  // For action field, optionally filter by selected resource
  if (props.fieldType === 'action' && props.selectedResource) {
    relevantPermissions = relevantPermissions.filter(p => p.resource === props.selectedResource);
  }
  
  relevantPermissions.forEach(p => {
    if (props.fieldType === 'resource' && p.resource) {
      values.add(p.resource);
    } else if (props.fieldType === 'action' && p.action) {
      values.add(p.action);
    }
  });
  
  return Array.from(values).sort();
});

// Check if current input would create a new value
const isCreatingNew = computed(() => {
  if (!searchTerm.value) return false;
  const formattedInput = searchTerm.value.toLowerCase().replace(/[^a-zA-Z0-9_-]/g, '_');
  return !existingValues.value.includes(formattedInput);
});

// Computed command groups
const commandGroups = computed(() => {
  const groups: any[] = [];
  
  if (existingValues.value.length > 0) {
    // Filter based on search term
    const filtered = searchTerm.value 
      ? existingValues.value.filter(v => v.toLowerCase().includes(searchTerm.value.toLowerCase()))
      : existingValues.value;
    
    if (filtered.length > 0) {
      groups.push({
        id: "existing",
        label: `Existing ${props.fieldType}s`,
        items: filtered.map((value) => ({
          id: value,
          label: value,
          value: value,
          icon: props.fieldType === 'resource' ? 'i-lucide-box' : 'i-lucide-zap',
        })),
      });
    }
  }
  
  // Add common suggestions based on field type
  if (props.fieldType === 'resource' && (!searchTerm.value || searchTerm.value.length < 3)) {
    const commonResources = ['invoice', 'report', 'document', 'budget', 'expense', 'contract', 'purchase_order'];
    const suggestedResources = commonResources.filter(r => 
      !existingValues.value.includes(r) && 
      (!searchTerm.value || r.includes(searchTerm.value.toLowerCase()))
    );
    
    if (suggestedResources.length > 0) {
      groups.push({
        id: "suggested",
        label: "Common Resources",
        items: suggestedResources.map((resource) => ({
          id: resource,
          label: resource,
          value: resource,
          icon: 'i-lucide-lightbulb',
        })),
      });
    }
  } else if (props.fieldType === 'action' && (!searchTerm.value || searchTerm.value.length < 3)) {
    const commonActions = ['approve', 'submit', 'export', 'import', 'review', 'sign', 'publish', 'archive'];
    const suggestedActions = commonActions.filter(a => 
      !existingValues.value.includes(a) && 
      (!searchTerm.value || a.includes(searchTerm.value.toLowerCase()))
    );
    
    if (suggestedActions.length > 0) {
      groups.push({
        id: "suggested",
        label: "Common Actions",
        items: suggestedActions.map((action) => ({
          id: action,
          label: action,
          value: action,
          icon: 'i-lucide-lightbulb',
        })),
      });
    }
  }
  
  return groups;
});

// Handle selection
function handleSelect(item: any) {
  if (item && item.value) {
    emit("update:modelValue", item.value);
    searchTerm.value = item.value;
  }
  isOpen.value = false;
}

// Handle Enter key press
function handleEnter(event: KeyboardEvent) {
  if (searchTerm.value) {
    // Format the input (lowercase, replace non-alphanumeric with underscore)
    const formattedInput = searchTerm.value.toLowerCase().replace(/[^a-zA-Z0-9_-]/g, '_');
    emit("update:modelValue", formattedInput);
  } else if (selectedValue.value && selectedValue.value.value) {
    emit("update:modelValue", selectedValue.value.value);
  }
  
  isOpen.value = false;
}

// Handle OK button click
function handleOk() {
  if (searchTerm.value) {
    // Format the input (lowercase, replace non-alphanumeric with underscore)
    const formattedInput = searchTerm.value.toLowerCase().replace(/[^a-zA-Z0-9_-]/g, '_');
    emit("update:modelValue", formattedInput);
  } else if (selectedValue.value && selectedValue.value.value) {
    emit("update:modelValue", selectedValue.value.value);
  }
  
  isOpen.value = false;
}

// Handle Cancel button click
function handleCancel() {
  isOpen.value = false;
}

// Watch for external value changes
watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      selectedValue.value = {
        id: newValue,
        label: newValue,
        value: newValue,
      };
      searchTerm.value = newValue;
    } else {
      selectedValue.value = null;
      searchTerm.value = "";
    }
  },
  { immediate: true }
);
</script>