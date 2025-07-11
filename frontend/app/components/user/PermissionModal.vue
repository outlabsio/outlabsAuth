<script setup lang="ts">
// Define Permission type
interface Permission {
  _id?: string;
  name: string;
  description: string;
}

// Define props for the component
const props = defineProps<{
  open: boolean;
  editMode: boolean;
  selectedPermission: Partial<Permission> | null;
  permissionType: "resource-set" | "custom";
  resourceSetName: string;
  resourceDescription: string;
  isLoading: boolean;
}>();

// Define emits for the component
const emit = defineEmits<{
  "update:open": [value: boolean];
  "update:selectedPermission": [value: Partial<Permission> | null];
  "update:permissionType": [value: "resource-set" | "custom"];
  "update:resourceSetName": [value: string];
  "update:resourceDescription": [value: string];
  save: [];
}>();

// Computed property to handle v-model for open state
const isOpen = computed({
  get: () => props.open,
  set: (value) => emit("update:open", value),
});

// Computed properties to handle v-model for form fields
const localPermissionType = computed({
  get: () => props.permissionType,
  set: (value) => emit("update:permissionType", value),
});

const localResourceSetName = computed({
  get: () => props.resourceSetName,
  set: (value) => emit("update:resourceSetName", value),
});

const localResourceDescription = computed({
  get: () => props.resourceDescription,
  set: (value) => emit("update:resourceDescription", value),
});

const localSelectedPermission = computed({
  get: () => props.selectedPermission || { name: "", description: "" },
  set: (value) => emit("update:selectedPermission", value),
});

// Computed property to determine if form can be saved
const canSave = computed(() => {
  if (localPermissionType.value === "resource-set") {
    return !!localResourceSetName.value;
  }
  return localSelectedPermission.value?.name && localSelectedPermission.value?.description;
});

// Handle save action
const handleSave = () => {
  emit("save");
};

// Handle cancel action
const closeModal = () => {
  isOpen.value = false;
};
</script>

<template>
  <UModal v-model:open="isOpen" :title="props.editMode ? 'Edit Permission' : 'Create New Permission'">
    <template #body>
      <div class="space-y-6">
        <div v-if="!props.editMode">
          <UTabs
            v-model="localPermissionType"
            :items="[
              {
                label: 'Resource Set',
                icon: 'i-lucide-layers',
                value: 'resource-set',
              },
              {
                label: 'Custom Permission',
                icon: 'i-lucide-key',
                value: 'custom',
              },
            ]"
            color="primary"
            variant="pill"
            class="w-full mb-4"
          />
        </div>

        <!-- Resource Set Permission - Create a complete permission set -->
        <div v-if="localPermissionType === 'resource-set'" class="space-y-5">
          <div class="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-4 rounded-md">
            <UFormGroup label="Resource Name" help="Will create a complete permission set">
              <UInput v-model="localResourceSetName" placeholder="e.g., products, users, etc." icon="i-lucide-layers" autofocus class="w-full" />
            </UFormGroup>

            <!-- Preview of permissions that will be created -->
            <div class="mt-4 space-y-3">
              <div class="font-semibold text-sm mb-2">Preview of permissions to be created:</div>

              <div class="flex items-center space-x-2 p-3 bg-primary/10 rounded-md border border-primary/30">
                <UIcon name="i-lucide-layers" class="h-5 w-5 text-primary" />
                <span class="font-mono">{{ localResourceSetName || "resource" }}:all</span>
                <UBadge class="ml-auto" size="xs" color="primary">ALL ACCESS</UBadge>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div class="flex items-center space-x-2 p-3 bg-white dark:bg-gray-700 rounded-md border border-gray-200 dark:border-gray-600">
                  <UIcon name="i-lucide-plus-circle" class="h-5 w-5 text-green-600" />
                  <span class="font-mono">{{ localResourceSetName || "resource" }}:create</span>
                </div>
                <div class="flex items-center space-x-2 p-3 bg-white dark:bg-gray-700 rounded-md border border-gray-200 dark:border-gray-600">
                  <UIcon name="i-lucide-eye" class="h-5 w-5 text-blue-600" />
                  <span class="font-mono">{{ localResourceSetName || "resource" }}:read</span>
                </div>
                <div class="flex items-center space-x-2 p-3 bg-white dark:bg-gray-700 rounded-md border border-gray-200 dark:border-gray-600">
                  <UIcon name="i-lucide-edit-2" class="h-5 w-5 text-amber-600" />
                  <span class="font-mono">{{ localResourceSetName || "resource" }}:update</span>
                </div>
                <div class="flex items-center space-x-2 p-3 bg-white dark:bg-gray-700 rounded-md border border-gray-200 dark:border-gray-600">
                  <UIcon name="i-lucide-trash" class="h-5 w-5 text-red-600" />
                  <span class="font-mono">{{ localResourceSetName || "resource" }}:delete</span>
                </div>
              </div>
            </div>
          </div>

          <div class="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-4 rounded-md">
            <UFormGroup label="Resource Description" help="Descriptions will be auto-generated, but you can provide a custom base description">
              <UTextarea v-model="localResourceDescription" placeholder="e.g., 'Products displayed in the store'" class="min-h-20 w-full" icon="i-lucide-text" />
            </UFormGroup>
          </div>
        </div>

        <!-- Custom Permission -->
        <div v-else-if="localSelectedPermission" class="space-y-5">
          <div class="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-4 rounded-md">
            <UFormGroup label="Permission Name" required help="Unique identifier for this permission">
              <UInput v-model="localSelectedPermission.name" placeholder="Enter permission name (e.g., 'reports:export')" icon="i-lucide-key" autofocus class="w-full" />
            </UFormGroup>

            <div class="mt-3 text-sm text-gray-500 dark:text-gray-400">
              <div class="flex items-center mb-2">
                <UIcon name="i-lucide-info" class="mr-2 text-primary" />
                <span>Recommended format: <code class="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">resource:action</code></span>
              </div>
              <div class="pl-6 space-y-1">
                <div class="flex items-center">
                  <span class="inline-block w-24 font-medium">Examples:</span>
                  <code class="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">reports:export</code>
                </div>
                <div class="flex items-center">
                  <span class="inline-block w-24"></span>
                  <code class="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">articles:publish</code>
                </div>
                <div class="flex items-center">
                  <span class="inline-block w-24"></span>
                  <code class="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">admin:override</code>
                </div>
              </div>
            </div>
          </div>

          <div class="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-4 rounded-md">
            <UFormGroup label="Description" required help="Explain what this permission grants access to">
              <UTextarea
                v-model="localSelectedPermission.description"
                placeholder="Enter a clear description of what this permission allows (e.g., 'Allows exporting reports to CSV/PDF')"
                class="min-h-24 w-full"
                icon="i-lucide-file-text"
              />
            </UFormGroup>

            <div class="mt-3 text-sm text-gray-500 dark:text-gray-400">
              <div class="flex items-start">
                <UIcon name="i-lucide-lightbulb" class="mt-0.5 mr-2 text-amber-500" />
                <div>
                  <p class="font-medium text-gray-700 dark:text-gray-300">Tips for good descriptions:</p>
                  <ul class="list-disc pl-5 mt-1 space-y-1">
                    <li>Be specific about what actions are allowed</li>
                    <li>Mention any limitations or conditions</li>
                    <li>Keep it concise but informative</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end w-full gap-3">
        <UButton label="Cancel" color="neutral" variant="soft" icon="i-lucide-x" :disabled="props.isLoading" @click="closeModal" />
        <UButton :label="props.editMode ? 'Update Permission' : 'Create Permission'" color="primary" icon="i-lucide-check" :loading="props.isLoading" :disabled="!canSave" @click="handleSave" />
      </div>
    </template>
  </UModal>
</template>
