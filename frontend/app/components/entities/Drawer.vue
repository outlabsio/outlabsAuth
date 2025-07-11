<template>
  <UDrawer
    v-model:open="open"
    direction="right"
    :ui="{
      content: 'w-full max-w-2xl',
      header: 'sticky top-0 z-10',
      body: 'overflow-y-auto',
    }"
  >
    <!-- Header -->
    <template #header>
      <div class="flex justify-between items-center w-full">
        <h3 class="text-xl font-bold">
          {{ mode === "create" ? "Create Entity" : mode === "edit" ? "Edit Entity" : "Entity Details" }}
        </h3>
      </div>
    </template>

    <!-- Body -->
    <template #body>
      <div class="p-4">
        <!-- View Mode -->
        <div v-if="mode === 'view' && entity" class="space-y-6">
          <!-- Entity Header -->
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-3">
              <UIcon :name="entity.entity_class === 'STRUCTURAL' ? 'i-lucide-building' : 'i-lucide-users'" class="h-8 w-8 text-primary" />
              <div>
                <h2 class="text-2xl font-bold">{{ entity.display_name || entity.name }}</h2>
                <p class="text-sm text-gray-600 dark:text-gray-400">
                  {{ entity.entity_type.replace(/_/g, " ") }}
                </p>
              </div>
            </div>
            <UBadge :color="entity.status === 'active' ? 'success' : 'neutral'" variant="subtle">
              {{ entity.status }}
            </UBadge>
          </div>

          <!-- Entity Details -->
          <div class="grid grid-cols-1 gap-4">
            <div>
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">System Name</h4>
              <p class="mt-1">{{ entity.name }}</p>
            </div>

            <div v-if="entity.description">
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Description</h4>
              <p class="mt-1">{{ entity.description }}</p>
            </div>

            <div>
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Entity Class</h4>
              <p class="mt-1">{{ entity.entity_class }}</p>
            </div>

            <div>
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Created</h4>
              <p class="mt-1">{{ new Date(entity.created_at).toLocaleString() }}</p>
            </div>

            <div v-if="entity.updated_at">
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Updated</h4>
              <p class="mt-1">{{ new Date(entity.updated_at).toLocaleString() }}</p>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-3 pt-4 border-t">
            <UButton @click="startEdit" icon="i-lucide-edit"> Edit Entity </UButton>
          </div>
        </div>

        <!-- Create/Edit Mode -->
        <div v-else-if="mode === 'create' || mode === 'edit'">
          <EntitiesForm ref="formRef" :entity="entity" :mode="mode" :default-parent-id="defaultParentId" @submit="handleSubmit" @cancel="handleCancel" @delete="confirmDelete" />
        </div>
      </div>
    </template>

    <!-- Footer for Create/Edit Mode -->
    <template v-if="mode === 'create' || mode === 'edit'" #footer>
      <div class="flex flex-col sm:flex-row gap-3 w-full">
        <UButton @click="handleCancel" color="neutral" variant="outline" class="justify-center flex-1"> Cancel </UButton>
        <UButton @click="submitForm" :loading="isSubmitting" color="primary" class="justify-center flex-1">
          {{ mode === "create" ? "Create Entity" : "Update Entity" }}
        </UButton>
      </div>
    </template>
  </UDrawer>

  <!-- Delete Confirmation Modal -->
  <UModal v-model:open="showDeleteDialog" title="Are you absolutely sure?">
    <template #body>
      <div class="space-y-4">
        <p class="text-sm">
          This will archive the entity
          <span class="font-semibold"> {{ entity?.display_name || entity?.name }}</span> and:
        </p>

        <ul class="list-disc list-inside space-y-1 text-sm text-muted-foreground">
          <li>Remove it from all active lists</li>
          <li>Revoke all user memberships in this entity</li>
          <li>Disable all permissions assigned to this entity</li>
          <li v-if="hasChildren" class="text-red-600 dark:text-red-400 font-semibold">Archive all child entities and their data</li>
        </ul>

        <!-- Warning for entities with children -->
        <div v-if="hasChildren" class="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 space-y-3">
          <div class="flex items-start gap-2">
            <UIcon name="i-lucide-alert-triangle" class="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5" />
            <div class="space-y-1">
              <p class="font-semibold text-red-600 dark:text-red-400">Warning: This entity has child entities!</p>
              <p class="text-sm">Deleting this entity will require cascading deletion of all its children. This operation cannot be undone.</p>
            </div>
          </div>

          <div class="flex items-center space-x-2">
            <UCheckbox v-model="enableCascade" label="I understand and want to archive all child entities" />
          </div>
        </div>

        <p v-else class="text-sm text-muted-foreground">The entity will be archived and removed from active views.</p>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-3">
        <UButton color="neutral" variant="outline" label="Cancel" @click="showDeleteDialog = false" />
        <UButton color="error" label="Archive Entity" :loading="isDeleting" :disabled="hasChildren && !enableCascade" @click="deleteEntity" />
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { Entity } from "~/types/auth.types";

interface Props {
  entity?: Entity | null;
  mode?: "view" | "create" | "edit";
  defaultParentId?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  mode: "view",
  defaultParentId: null,
});

const emit = defineEmits<{
  created: [entity: Entity];
  updated: [entity: Entity];
  deleted: [id: string];
}>();

// State
const open = defineModel<boolean>("open", { default: false });
const currentMode = ref(props.mode);
const toast = useToast();
const entitiesStore = useEntitiesStore();
const authStore = useAuthStore();
const isDeleting = ref(false);
const hasChildren = ref(false);
const enableCascade = ref(false);
const isSubmitting = ref(false);
const formRef = ref();

// Watch for prop changes
watch(
  () => props.mode,
  (newMode) => {
    currentMode.value = newMode;
  }
);

watch(
  () => props.entity,
  (newEntity) => {
    if (newEntity && currentMode.value === "view") {
      // Entity changed, ensure we're in view mode
      currentMode.value = "view";
    }
  }
);

// Computed
const mode = computed(() => currentMode.value);
const entity = computed(() => props.entity);

// Methods
const startEdit = () => {
  currentMode.value = "edit";
};

const handleCancel = () => {
  if (props.mode === "create") {
    open.value = false;
  } else {
    currentMode.value = "view";
  }
};

const handleSubmit = async (data: Partial<Entity>) => {
  isSubmitting.value = true;
  try {
    if (mode.value === "create") {
      const newEntity = await entitiesStore.createEntity(data);
      toast.add({
        title: "Success",
        description: "Entity created successfully",
        color: "success",
      });
      emit("created", newEntity);
      open.value = false;
    } else if (mode.value === "edit" && entity.value) {
      const updatedEntity = await entitiesStore.updateEntity(entity.value.id, data);
      toast.add({
        title: "Success",
        description: "Entity updated successfully",
        color: "success",
      });
      emit("updated", updatedEntity);
      currentMode.value = "view";
    }
  } catch (error: any) {
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || "Operation failed",
      color: "error",
    });
  } finally {
    isSubmitting.value = false;
  }
};

const submitForm = () => {
  // Trigger form submission
  if (formRef.value) {
    formRef.value.$el.dispatchEvent(new Event("submit", { bubbles: true }));
  }
};

const showDeleteDialog = ref(false);

const confirmDelete = async () => {
  if (!entity.value) return;

  // Check if entity has children
  try {
    const response = await authStore.apiCall<{ total: number }>(`/v1/entities/?parent_entity_id=${entity.value.id}&status=active`);
    hasChildren.value = response.total > 0;
  } catch (error) {
    // If error checking children, assume no children
    hasChildren.value = false;
  }

  showDeleteDialog.value = true;
};

const deleteEntity = async () => {
  if (!entity.value) return;

  isDeleting.value = true;
  try {
    // Add cascade parameter if entity has children
    const url = hasChildren.value && enableCascade.value ? `/v1/entities/${entity.value.id}?cascade=true` : `/v1/entities/${entity.value.id}`;

    await authStore.apiCall(url, { method: "DELETE" });

    toast.add({
      title: "Success",
      description: "Entity archived successfully",
      color: "success",
    });
    emit("deleted", entity.value.id);
    showDeleteDialog.value = false;
    open.value = false;
  } catch (error: any) {
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || "Failed to archive entity",
      color: "error",
    });
    showDeleteDialog.value = false;
  } finally {
    isDeleting.value = false;
    enableCascade.value = false; // Reset cascade state
  }
};
</script>
