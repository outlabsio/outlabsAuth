<script setup lang="ts">
import * as z from "zod";
import type { FormSubmitEvent } from "@nuxt/ui";
import type { Entity } from "~/types/auth.types";

interface Props {
  entity?: Entity | null;
  mode: "create" | "edit";
  defaultParentId?: string | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  submit: [data: Partial<Entity>];
  cancel: [];
  delete: [];
}>();

// Schema
const schema = z.object({
  display_name: z.string().min(1, "Entity name is required"),
  description: z.string().optional(),
  entity_class: z.enum(["STRUCTURAL", "ACCESS_GROUP"]),
  entity_type: z.string().min(1, "Entity type is required"),
  parent_entity_id: z.string().optional(),
  status: z.enum(["active", "inactive"]),
  max_members: z.string().optional(),
});

type Schema = z.output<typeof schema>;

// State
const state = reactive<Partial<Schema>>({
  display_name: props.entity?.display_name || "",
  description: props.entity?.description || "",
  entity_class: props.entity?.entity_class || "STRUCTURAL",
  entity_type: props.entity?.entity_type || "",
  parent_entity_id: props.entity?.parent_entity_id || props.defaultParentId || "",
  status: (props.entity?.status as "active" | "inactive") || "active",
  max_members: props.entity?.max_members?.toString() || "",
});

const isLoading = ref(false);
const selectedClass = ref<"STRUCTURAL" | "ACCESS_GROUP">(state.entity_class || "STRUCTURAL");

// Computed for switch
const isActive = computed({
  get: () => state.status === "active",
  set: (value: boolean) => {
    state.status = value ? "active" : "inactive";
  },
});

// Stores
const entitiesStore = useEntitiesStore();
const authStore = useAuthStore();
const toast = useToast();

// Fetch all entities for parent selection
const { data: allEntities } = await useAsyncData(
  "all-entities",
  async () => {
    const response = await authStore.apiCall<{ items: Entity[] }>("/v1/entities?page_size=100");
    return response.items || [];
  },
  {
    lazy: true,
    default: () => [],
  }
);

// Fetch entity types for autocomplete
const { data: entityTypes } = await useAsyncData("entity-types", () => entitiesStore.fetchEntityTypes(), {
  lazy: true,
  default: () => [],
});

// Entity class tabs
const entityClassTabs = [
  {
    value: "STRUCTURAL",
    label: "Structural Entity",
    icon: "i-lucide-building",
    disabled: props.mode === "edit",
  },
  {
    value: "ACCESS_GROUP",
    label: "Access Group",
    icon: "i-lucide-users",
    disabled: props.mode === "edit",
  },
];

// Computed
const potentialParents = computed(() => {
  if (!allEntities.value) return [];

  let filtered = allEntities.value.filter((e) => e.entity_class === "STRUCTURAL" && e.status === "active" && (props.mode !== "edit" || e.id !== props.entity?.id));

  // If we have a default parent (creating within a context)
  if (props.defaultParentId && props.mode === "create") {
    const contextEntity = allEntities.value.find((e) => e.id === props.defaultParentId);
    if (contextEntity) {
      // Get the context entity and all its ancestors
      const allowedIds = new Set<string>([props.defaultParentId]);

      // Find all ancestors
      let current = contextEntity;
      while (current.parent_entity_id) {
        const parent = allEntities.value.find((e) => e.id === current.parent_entity_id);
        if (parent) {
          allowedIds.add(parent.id);
          current = parent;
        } else {
          break;
        }
      }

      filtered = filtered.filter((e) => allowedIds.has(e.id));
    }
  }

  return filtered;
});

const parentOptions = computed(() => {
  const options = [{ label: "No Parent (Top Level)", value: "" }];
  potentialParents.value.forEach((entity) => {
    options.push({
      label: entity.display_name || entity.name,
      value: entity.id,
    });
  });
  return options;
});

// Entity type options are now handled by the EntityTypeCombobox component

// Check if access group parent can't have structural children
const cannotHaveStructuralChildren = computed(() => {
  if (props.mode !== "edit" && state.parent_entity_id) {
    const parentEntity = potentialParents.value.find((p) => p.id === state.parent_entity_id);
    return parentEntity?.entity_class === "ACCESS_GROUP" && selectedClass.value === "STRUCTURAL";
  }
  return false;
});

// Generate system name from display name
const generateSystemName = (displayName: string) => {
  return displayName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
};

// Watch for entity changes
watch(
  () => props.entity,
  (newEntity) => {
    if (newEntity) {
      state.display_name = newEntity.display_name || newEntity.name;
      state.description = newEntity.description || "";
      state.entity_class = newEntity.entity_class;
      state.entity_type = newEntity.entity_type;
      state.parent_entity_id = newEntity.parent_entity_id || "";
      state.status = newEntity.status;
      state.max_members = newEntity.max_members?.toString() || "";
      selectedClass.value = newEntity.entity_class;
    }
  },
  { immediate: true }
);

// Watch for class changes
watch(selectedClass, (newClass) => {
  if (newClass !== state.entity_class) {
    state.entity_class = newClass;
    // Reset entity type when class changes
    state.entity_type = "";
  }
});

// Methods
async function onSubmit(event: FormSubmitEvent<Schema>) {
  isLoading.value = true;

  try {
    const data: any = {
      name: generateSystemName(event.data.display_name),
      display_name: event.data.display_name,
      description: event.data.description,
      entity_class: event.data.entity_class,
      entity_type: event.data.entity_type,
      status: event.data.status,
    };

    if (event.data.parent_entity_id) {
      data.parent_entity_id = event.data.parent_entity_id;
    }

    if (event.data.max_members) {
      data.max_members = parseInt(event.data.max_members);
    }

    emit("submit", data);
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <UForm :schema="schema" :state="state" @submit="onSubmit" class="space-y-8">
    <!-- Basic Information Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">Basic Information</h5>

      <!-- Entity Name -->
      <UFormField label="Entity Name" name="display_name" required class="w-full">
        <UInput v-model="state.display_name" placeholder="e.g., Acme Corporation, Engineering Team" size="lg" class="w-full" />
        <template #description>
          <span class="text-xs text-muted-foreground">A display name for this entity (system name will be generated automatically)</span>
        </template>
      </UFormField>

      <!-- Description -->
      <UFormField label="Description" name="description" class="w-full">
        <UTextarea v-model="state.description" placeholder="Describe the purpose and scope of this entity" :rows="3" class="w-full" />
      </UFormField>
    </div>

    <USeparator />

    <!-- Classification Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">Classification</h5>

      <!-- Entity Class -->
      <UFormField label="Entity Class" name="entity_class" class="w-full">
        <UTabs v-model="selectedClass" :content="false" :items="entityClassTabs" variant="pill" color="primary" class="w-full" />
        <div class="mt-2 text-xs text-muted-foreground">
          {{ selectedClass === "STRUCTURAL" ? "Organizational units in your hierarchy" : "Groups for managing permissions and access" }}
        </div>
      </UFormField>

      <!-- Entity Type and Parent in Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Entity Type -->
        <UFormField label="Entity Type" name="entity_type" required class="w-full">
          <template v-if="cannotHaveStructuralChildren">
            <div class="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-3 mb-3">
              <p class="text-sm text-red-600 dark:text-red-400">The selected parent entity cannot have structural children. Consider creating an access group instead.</p>
            </div>
          </template>

          <EntitiesEntityTypeCombobox
            v-model="state.entity_type"
            :entity-class="selectedClass"
            :platform-id="authStore.user?.platform_id"
            :disabled="cannotHaveStructuralChildren"
            :placeholder="selectedClass === 'STRUCTURAL' ? 'Select or type (e.g., department, division)...' : 'Select or type (e.g., admin_group, beta_testers)...'"
          />

          <template #description>
            <span class="text-xs text-muted-foreground">
              {{ selectedClass === "STRUCTURAL" ? "Examples: platform, organization, department, team" : "Examples: admin_group, viewer_group, project_team" }}
            </span>
          </template>
        </UFormField>

        <!-- Parent Entity -->
        <UFormField label="Parent Entity" name="parent_entity_id" class="w-full">
          <EntitiesParentEntitySelector
            v-model="state.parent_entity_id"
            :entities="allEntities"
            :context-entity-id="props.defaultParentId"
            :exclude-entity-id="props.entity?.id"
            :entity-class="selectedClass"
          />
          <template #description>
            <span class="text-xs text-muted-foreground"> Search and select a parent entity, or leave empty for top-level </span>
          </template>
        </UFormField>
      </div>
    </div>

    <!-- Configuration Section -->
    <div class="space-y-6">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">Configuration</h5>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Max Members (for access groups) -->
        <UFormField v-if="selectedClass === 'ACCESS_GROUP'" label="Maximum Members" name="max_members" class="w-full">
          <UInput v-model="state.max_members" type="number" placeholder="Leave empty for unlimited" class="w-full" />
          <template #description>
            <span class="text-xs text-muted-foreground">Optional limit on the number of members</span>
          </template>
        </UFormField>

        <!-- Status -->
        <UFormField label="Status" name="status" :class="{ 'md:col-span-2': selectedClass !== 'ACCESS_GROUP' }">
          <div class="flex items-center gap-3">
            <USwitch v-model="isActive" :color="isActive ? 'success' : 'neutral'" />
            <span class="text-sm text-muted-foreground">
              {{ isActive ? "Entity is operational and can be used" : "Entity is disabled and cannot be used" }}
            </span>
          </div>
        </UFormField>
      </div>
    </div>

    <!-- Danger Zone - Only show in edit mode -->
    <div v-if="mode === 'edit' && entity" class="space-y-6 w-full">
      <USeparator />

      <div class="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-6">
        <div class="flex items-center gap-3 mb-4">
          <UIcon name="i-lucide-alert-triangle" class="h-5 w-5 text-red-600 dark:text-red-400" />
          <h3 class="font-semibold text-red-600 dark:text-red-400">Archive Zone</h3>
        </div>

        <div class="space-y-4">
          <div>
            <h4 class="font-medium">Archive this entity</h4>
            <p class="text-sm text-muted-foreground mt-1">
              Archiving an entity will soft-delete it, removing it from active lists and revoking all memberships. Archived entities are not permanently deleted.
            </p>
          </div>

          <UButton color="error" @click="emit('delete')" class="w-full" icon="i-lucide-trash"> Archive Entity </UButton>
        </div>
      </div>
    </div>
  </UForm>
</template>
