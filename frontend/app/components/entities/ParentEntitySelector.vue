<template>
  <div class="w-full">
    <UPopover ref="popoverRef">
      <UButton :variant="selectedEntity ? 'outline' : 'outline'" :color="selectedEntity ? 'primary' : 'neutral'" class="w-full justify-between">
        <div class="flex items-center gap-2 min-w-0 flex-1">
          <UIcon name="i-lucide-building" class="w-4 h-4 text-muted-foreground shrink-0" />
          <span class="truncate">
            {{ selectedEntity ? selectedEntity.display_name || selectedEntity.name : "Search for parent entity..." }}
          </span>
        </div>
        <UIcon name="i-lucide-chevrons-up-down" class="w-4 h-4 text-muted-foreground shrink-0 ml-2" />
      </UButton>

      <template #content>
        <div class="flex flex-col">
          <UCommandPalette
            v-model="selectedEntity"
            :groups="commandGroups"
            placeholder="Search for parent entity..."
            :fuse="{
              fuseOptions: {
                includeMatches: true,
                threshold: 0.3,
                keys: ['display_name', 'name', 'entity_type', 'description'],
              },
              resultLimit: 20,
            }"
            :ui="{ input: '[&>input]:h-8 [&>input]:text-sm' }"
            class="h-80"
            @update:model-value="onSelect"
            v-model:search-term="searchTerm"
            @keydown.enter="handleEnter"
          />
          <div class="flex items-center justify-end gap-2 p-2 border-t border-gray-200 dark:border-gray-700">
            <UButton color="neutral" variant="ghost" size="xs" icon="i-lucide-x" @click="handleCancel"> Cancel </UButton>
            <UButton color="primary" variant="solid" size="xs" icon="i-lucide-check" @click="handleOk"> OK </UButton>
          </div>
        </div>
      </template>
    </UPopover>

    <!-- Selected Entity Display -->
    <div v-if="selectedEntity && selectedEntity.value" class="mt-2 p-2 bg-elevated rounded-md border">
      <div class="flex items-center gap-2">
        <UIcon :name="selectedEntity.entity_class === 'STRUCTURAL' ? 'i-lucide-building' : 'i-lucide-users'" class="w-4 h-4" />
        <span class="font-medium">{{ selectedEntity.display_name || selectedEntity.name }}</span>
        <UBadge :label="selectedEntity.entity_type" variant="subtle" size="sm" />
        <UButton icon="i-lucide-x" size="xs" color="neutral" variant="ghost" @click="clearSelection" class="ml-auto" />
      </div>

      <!-- Entity Path Breadcrumb -->
      <div v-if="entityPath.length > 0" class="mt-1">
        <UBreadcrumb :items="entityPath" class="text-xs" />
      </div>
    </div>

    <!-- No Parent Option -->
    <div class="mt-2">
      <UButton
        :variant="!selectedEntity?.value ? 'soft' : 'ghost'"
        :color="!selectedEntity?.value ? 'primary' : 'neutral'"
        size="sm"
        icon="i-lucide-minus"
        label="No Parent (Top Level)"
        @click="selectNoParent"
        class="w-full justify-start"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Entity } from "~/types/auth.types";

interface Props {
  entities: Entity[];
  modelValue?: string;
  contextEntityId?: string | null;
  excludeEntityId?: string | null;
  entityClass?: "STRUCTURAL" | "ACCESS_GROUP";
}

const props = defineProps<Props>();
const emit = defineEmits<{
  "update:modelValue": [value: string];
}>();

interface CommandItem extends Entity {
  label: string;
  value: string;
  suffix?: string;
  icon?: string;
}

const selectedEntity = ref<CommandItem | null>(null);
const searchTerm = ref("");
const popoverRef = ref();

// Stores
const contextStore = useContextStore();

// Determine the effective context entity ID
const effectiveContextEntityId = computed(() => {
  // If explicit context is provided, use it
  if (props.contextEntityId) {
    return props.contextEntityId;
  }

  // Otherwise, use the current selected organization from context store
  if (!contextStore.isSystemContext && contextStore.selectedOrganization) {
    return contextStore.selectedOrganization.id;
  }

  return null;
});

// Build entity hierarchy
const entityMap = computed(() => {
  const map = new Map<string, Entity>();
  props.entities.forEach((entity) => {
    map.set(entity.id, entity);
  });
  return map;
});

// Get entity path for breadcrumbs
const getEntityPath = (entity: Entity): { label: string; to?: string }[] => {
  const path: { label: string; to?: string }[] = [];
  let current = entity;

  while (current) {
    path.unshift({
      label: current.display_name || current.name,
      to: `/entities/${current.id}`,
    });

    if (current.parent_entity_id) {
      const parent = entityMap.value.get(current.parent_entity_id);
      if (parent) {
        current = parent;
      } else {
        break;
      }
    } else {
      break;
    }
  }

  return path;
};

const entityPath = computed(() => {
  if (!selectedEntity.value) return [];
  return getEntityPath(selectedEntity.value);
});

// Filter entities for potential parents
const potentialParents = computed(() => {
  let filtered = props.entities.filter((entity) => {
    // Must be structural for hierarchy
    if (entity.entity_class !== "STRUCTURAL") return false;

    // Must be active
    if (entity.status !== "active") return false;

    // Can't select self as parent
    if (props.excludeEntityId && entity.id === props.excludeEntityId) return false;

    return true;
  });

  // If we have a context entity (creating within a specific entity)
  if (effectiveContextEntityId.value) {
    const contextEntity = entityMap.value.get(effectiveContextEntityId.value);
    if (contextEntity) {
      const allowedIds = new Set<string>([effectiveContextEntityId.value]);

      // Add all ancestors
      let current = contextEntity;
      while (current.parent_entity_id) {
        const parent = entityMap.value.get(current.parent_entity_id);
        if (parent) {
          allowedIds.add(parent.id);
          current = parent;
        } else {
          break;
        }
      }

      filtered = filtered.filter((entity) => allowedIds.has(entity.id));
    }
  }

  return filtered;
});

// Build command palette groups
const commandGroups = computed(() => {
  const groups: any[] = [];

  // Group by hierarchy level
  const rootEntities = potentialParents.value.filter((e) => !e.parent_entity_id);
  const childEntities = potentialParents.value.filter((e) => e.parent_entity_id);

  if (rootEntities.length > 0) {
    groups.push({
      id: "root",
      label: "Top Level Entities",
      items: rootEntities.map((entity) => ({
        ...entity,
        label: entity.display_name || entity.name,
        suffix: entity.entity_type,
        icon: "i-lucide-building",
        description: entity.description,
        value: entity.id,
      })),
    });
  }

  if (childEntities.length > 0) {
    // Group children by parent
    const childrenByParent = new Map<string, Entity[]>();
    childEntities.forEach((entity) => {
      if (entity.parent_entity_id) {
        if (!childrenByParent.has(entity.parent_entity_id)) {
          childrenByParent.set(entity.parent_entity_id, []);
        }
        childrenByParent.get(entity.parent_entity_id)!.push(entity);
      }
    });

    childrenByParent.forEach((children, parentId) => {
      const parent = entityMap.value.get(parentId);
      if (parent) {
        groups.push({
          id: `children-${parentId}`,
          label: `Under ${parent.display_name || parent.name}`,
          items: children.map((entity) => ({
            ...entity,
            label: entity.display_name || entity.name,
            suffix: entity.entity_type,
            icon: "i-lucide-building",
            description: entity.description,
            value: entity.id,
          })),
        });
      }
    });
  }

  return groups;
});

// Initialize selected entity
watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue && entityMap.value.has(newValue)) {
      const entity = entityMap.value.get(newValue)!;
      selectedEntity.value = {
        ...entity,
        label: entity.display_name || entity.name,
        value: entity.id,
        suffix: entity.entity_type,
        icon: "i-lucide-building",
      };
    } else {
      selectedEntity.value = null;
    }
  },
  { immediate: true }
);

function onSelect(item: any) {
  selectedEntity.value = item;
  emit("update:modelValue", item?.value || "");
  // Close popover after selection
  if (popoverRef.value) {
    popoverRef.value.close?.();
  }
}

// Handle Enter key press
function handleEnter(event: KeyboardEvent) {
  // Close popover when Enter is pressed
  if (popoverRef.value) {
    popoverRef.value.close?.();
  }
}

// Handle OK button click
function handleOk() {
  // Close popover when OK is clicked
  if (popoverRef.value) {
    popoverRef.value.close?.();
  }
}

// Handle Cancel button click
function handleCancel() {
  // Just close the popover without emitting any changes
  if (popoverRef.value) {
    popoverRef.value.close?.();
  }
}

function clearSelection() {
  selectedEntity.value = null;
  emit("update:modelValue", "");
}

function selectNoParent() {
  selectedEntity.value = null;
  emit("update:modelValue", "");
}
</script>
