<script setup lang="ts">
import type { EntityClass, Entity } from "~/types/entity";
import { useQuery } from "@pinia/colada";
import { entitiesQueries, useCreateEntityMutation } from "~/queries/entities";

const props = defineProps<{
    parentEntityId?: string;
}>();

const open = defineModel<boolean>("open", { default: false });

// Stores
const configStore = useConfigStore();

// Fetch all entities for parent selection dropdown
const { data: entitiesData, refetch: refetchEntities } = useQuery(
    entitiesQueries.list({}, { page: 1, limit: 500 }),
);

const { mutateAsync: createEntity, isLoading: isSubmitting } = useCreateEntityMutation();

// Form state
const state = reactive({
    name: "",
    display_name: "",
    slug: "",
    description: "",
    entity_class: "structural" as EntityClass,
    entity_type: "",
    parent_entity_id: undefined as string | undefined,
    // For root entities: configure allowed child types
    allowed_child_types: [] as string[],
});

// New child type input
const newChildType = ref("");

// Initialize config store
onMounted(async () => {
    await configStore.fetchEntityTypeConfig();
});

// Track if user has manually edited the slug
const slugManuallyEdited = ref(false);

// Auto-generate slug and display_name from name
watch(
    () => state.name,
    (newName) => {
        if (newName) {
            // Auto-set display_name to match name
            state.display_name = newName;
            // Auto-generate slug unless user has manually edited it
            if (!slugManuallyEdited.value) {
                state.slug = newName
                    .toLowerCase()
                    .replace(/\s+/g, "-")
                    .replace(/[^a-z0-9-]/g, "");
            }
        }
    },
);

// Mark slug as manually edited when user types in it directly
const onSlugInput = () => {
    slugManuallyEdited.value = true;
};

// Set parent entity when modal opens with a parent context
// Also refetch entities to get latest allowed_child_types
watch(open, async (isOpen) => {
    if (isOpen) {
        // Refetch to get latest entity data (including updated allowed_child_types)
        await refetchEntities();
        if (props.parentEntityId) {
            state.parent_entity_id = props.parentEntityId;
        }
    }
});

// Check if creating a root entity (no parent)
const isRootEntity = computed(() => !state.parent_entity_id);

// Get selected parent entity
const selectedParentEntity = computed((): Entity | undefined => {
    if (!state.parent_entity_id) return undefined;
    return entitiesData.value?.items?.find(
        (e) => e.id === state.parent_entity_id,
    );
});

// Get root entity for current selection (for child type lookup)
const rootEntity = computed((): Entity | undefined => {
    if (isRootEntity.value) return undefined;

    const entities = entitiesData.value?.items || [];
    let current = selectedParentEntity.value;

    // Walk up the tree to find root
    while (current?.parent_entity_id) {
        current = entities.find((e) => e.id === current?.parent_entity_id);
    }

    return current;
});

// Entity type options - dynamic based on context
const entityTypes = computed(() => {
    if (isRootEntity.value) {
        // Root entity: use system-configured allowed root types
        return configStore.allowedRootTypes.map((type) => ({
            label: formatTypeName(type),
            value: type,
        }));
    }

    // Child entity: check root entity's allowed_child_types first
    const root = rootEntity.value;
    if (root?.allowed_child_types && root.allowed_child_types.length > 0) {
        // Filter by entity class
        const types = root.allowed_child_types;
        return types.map((type) => ({
            label: formatTypeName(type),
            value: type,
        }));
    }

    // Fallback to system defaults based on entity class
    if (state.entity_class === "structural") {
        return configStore.defaultStructuralChildTypes.map((type) => ({
            label: formatTypeName(type),
            value: type,
        }));
    } else {
        return configStore.defaultAccessGroupChildTypes.map((type) => ({
            label: formatTypeName(type),
            value: type,
        }));
    }
});

// Default child type suggestions for root entities
const childTypeSuggestions = computed(() => {
    return [
        ...configStore.defaultStructuralChildTypes,
        ...configStore.defaultAccessGroupChildTypes,
    ].filter((type) => !state.allowed_child_types.includes(type));
});

// Format type name for display
const formatTypeName = (type: string): string => {
    return type.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
};

// Add child type
const addChildType = () => {
    const type = newChildType.value.trim().toLowerCase().replace(/\s+/g, "_");
    if (type && !state.allowed_child_types.includes(type)) {
        state.allowed_child_types.push(type);
        newChildType.value = "";
    }
};

const addSuggestedChildType = (type: string) => {
    if (!state.allowed_child_types.includes(type)) {
        state.allowed_child_types.push(type);
    }
};

const removeChildType = (type: string) => {
    state.allowed_child_types = state.allowed_child_types.filter(
        (t) => t !== type,
    );
};

// Build indented parent options showing hierarchy
const parentOptions = computed(() => {
    const entities = entitiesData.value?.items || [];

    // Build a map for quick lookup
    const entityMap = new Map(entities.map((e) => [e.id, e]));

    // Calculate depth for each entity
    const getDepth = (entityId: string | undefined, depth = 0): number => {
        if (!entityId) return depth;
        const entity = entityMap.get(entityId);
        if (!entity?.parent_entity_id) return depth;
        return getDepth(entity.parent_entity_id, depth + 1);
    };

    // Sort entities by hierarchy (parents before children)
    const sortedEntities = [...entities].sort((a, b) => {
        const depthA = getDepth(a.id);
        const depthB = getDepth(b.id);
        if (depthA !== depthB) return depthA - depthB;
        return a.name.localeCompare(b.name);
    });

    return [
        { label: "None (Root Entity)", value: undefined },
        ...sortedEntities.map((e) => {
            const depth = getDepth(e.id);
            const indent = "  ".repeat(depth);
            const prefix = depth > 0 ? "└─ " : "";
            return {
                label: `${indent}${prefix}${e.display_name || e.name} (${e.entity_type})`,
                value: e.id,
            };
        }),
    ];
});

// Form validation
const isFormValid = computed(() => {
    return (
        state.name.trim() !== "" &&
        state.display_name.trim() !== "" &&
        state.slug.trim() !== "" &&
        state.entity_type !== ""
    );
});

// Submit handler
const showEntityHelp = ref(false);

async function handleSubmit() {
    try {
        // Build payload - include allowed_child_types only for root entities
        const payload = {
            name: state.name,
            display_name: state.display_name,
            slug: state.slug,
            description: state.description,
            entity_class: state.entity_class,
            entity_type: state.entity_type,
            parent_entity_id: state.parent_entity_id,
            ...(isRootEntity.value && state.allowed_child_types.length > 0
                ? { allowed_child_types: state.allowed_child_types }
                : {}),
        };

        await createEntity(payload);

        // Close modal and reset form (mutation handles toast)
        open.value = false;
        Object.assign(state, {
            name: "",
            display_name: "",
            slug: "",
            description: "",
            entity_class: "structural",
            entity_type: "",
            parent_entity_id: undefined,
            allowed_child_types: [],
        });
        newChildType.value = "";
        slugManuallyEdited.value = false;
    } catch (error: any) {
        // Error toast is handled by mutation's onError
        console.error("Failed to create entity:", error);
    }
}
</script>

<template>
    <UModal
        v-model:open="open"
        title="Create Entity"
        description="Create a new entity in your organization hierarchy"
        fullscreen
    >
        <template #body>
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
                <!-- Left Column: Basic Info & Hierarchy -->
                <div class="space-y-6">
                    <div class="space-y-4">
                        <h3
                            class="text-lg font-semibold flex items-center gap-2"
                        >
                            <UIcon name="i-lucide-info" class="w-5 h-5" />
                            Basic Information
                        </h3>

                        <!-- Name -->
                        <div class="space-y-2">
                            <label
                                class="block text-sm font-medium flex items-center gap-1.5"
                            >
                                Name
                                <UPopover>
                                    <UButton
                                        icon="i-lucide-help-circle"
                                        color="neutral"
                                        variant="ghost"
                                        size="xs"
                                        class="text-muted hover:text-highlighted"
                                    />
                                    <template #content>
                                        <div class="p-4 max-w-xs space-y-2">
                                            <h4 class="font-semibold text-sm">
                                                Entity Name
                                            </h4>
                                            <p class="text-sm text-muted">
                                                The primary identifier for this
                                                entity. This will be displayed
                                                throughout the system.
                                            </p>
                                            <div
                                                class="text-xs text-muted mt-2"
                                            >
                                                <p class="font-medium mb-1">
                                                    Examples:
                                                </p>
                                                <ul
                                                    class="list-disc list-inside pl-2 space-y-0.5"
                                                >
                                                    <li>
                                                        "Engineering Department"
                                                    </li>
                                                    <li>"Product Team"</li>
                                                    <li>
                                                        "Admin Access Group"
                                                    </li>
                                                </ul>
                                            </div>
                                        </div>
                                    </template>
                                </UPopover>
                            </label>
                            <UInput
                                v-model="state.name"
                                placeholder="Engineering Department"
                                icon="i-lucide-tag"
                            />
                        </div>

                        <!-- Slug -->
                        <div class="space-y-2">
                            <label
                                class="block text-sm font-medium flex items-center gap-1.5"
                            >
                                Slug
                                <UPopover>
                                    <UButton
                                        icon="i-lucide-help-circle"
                                        color="neutral"
                                        variant="ghost"
                                        size="xs"
                                        class="text-muted hover:text-highlighted"
                                    />
                                    <template #content>
                                        <div class="p-4 max-w-xs space-y-2">
                                            <h4 class="font-semibold text-sm">
                                                URL Slug
                                            </h4>
                                            <p class="text-sm text-muted">
                                                A URL-friendly identifier used
                                                in API endpoints and URLs.
                                                Auto-generated from the name but
                                                can be customized.
                                            </p>
                                            <div
                                                class="text-xs text-muted mt-2"
                                            >
                                                <p class="font-medium mb-1">
                                                    Format:
                                                </p>
                                                <p>
                                                    Lowercase letters, numbers,
                                                    and hyphens only
                                                </p>
                                            </div>
                                            <UAlert
                                                icon="i-lucide-lightbulb"
                                                color="info"
                                                variant="subtle"
                                                description="Auto-generated from Name, but you can customize it."
                                                class="mt-2"
                                            />
                                        </div>
                                    </template>
                                </UPopover>
                            </label>
                            <UInput
                                v-model="state.slug"
                                placeholder="engineering-department"
                                icon="i-lucide-link"
                                @input="onSlugInput"
                            />
                            <p class="text-xs text-muted">
                                URL-friendly identifier
                            </p>
                        </div>

                        <!-- Description -->
                        <div class="space-y-2 w-full">
                            <label class="block text-sm font-medium"
                                >Description</label
                            >
                            <UTextarea
                                v-model="state.description"
                                placeholder="A brief description of this entity..."
                                :rows="4"
                                class="w-full"
                            />
                        </div>
                    </div>

                    <hr class="border-default" />

                    <div class="space-y-4">
                        <h3
                            class="text-lg font-semibold flex items-center gap-2"
                        >
                            <UIcon name="i-lucide-git-branch" class="w-5 h-5" />
                            Hierarchy
                            <UPopover>
                                <UButton
                                    icon="i-lucide-help-circle"
                                    color="neutral"
                                    variant="ghost"
                                    size="xs"
                                />
                                <template #content>
                                    <div class="p-4 max-w-sm space-y-2">
                                        <h4 class="font-semibold text-sm">
                                            Entity Hierarchy
                                        </h4>
                                        <p class="text-sm text-muted">
                                            Entities can be organized in a tree
                                            structure. Child entities inherit
                                            permissions from their parents.
                                        </p>
                                        <div
                                            class="text-xs text-muted mt-2 space-y-1"
                                        >
                                            <p class="font-medium">Example:</p>
                                            <ul
                                                class="list-disc list-inside pl-2"
                                            >
                                                <li>Company (Root)</li>
                                                <li>
                                                    └─ Engineering Dept (Child)
                                                </li>
                                                <li>
                                                    &nbsp;&nbsp;&nbsp;&nbsp;└─
                                                    Backend Team (Grandchild)
                                                </li>
                                            </ul>
                                        </div>
                                    </div>
                                </template>
                            </UPopover>
                        </h3>

                        <!-- Parent Entity -->
                        <div class="space-y-2">
                            <label
                                class="block text-sm font-medium flex items-center gap-1.5"
                            >
                                Parent Entity
                                <UPopover>
                                    <UButton
                                        icon="i-lucide-help-circle"
                                        color="neutral"
                                        variant="ghost"
                                        size="xs"
                                        class="text-muted hover:text-highlighted"
                                    />
                                    <template #content>
                                        <div class="p-4 max-w-xs space-y-2">
                                            <h4 class="font-semibold text-sm">
                                                Parent Entity
                                            </h4>
                                            <p class="text-sm text-muted">
                                                Select a parent entity to create
                                                a hierarchical structure. Leave
                                                as "None" to create a root-level
                                                entity.
                                            </p>
                                            <UAlert
                                                icon="i-lucide-info"
                                                color="info"
                                                variant="subtle"
                                                description="Child entities inherit permissions from their parents in the tree structure."
                                                class="mt-2"
                                            />
                                        </div>
                                    </template>
                                </UPopover>
                            </label>
                            <USelect
                                v-model="state.parent_entity_id"
                                :items="parentOptions"
                                placeholder="None (Root Entity)"
                            />
                        </div>

                        <!-- Allowed Child Types (Root Entities Only) -->
                        <div
                            v-if="isRootEntity"
                            class="space-y-3 pt-4 border-t border-default"
                        >
                            <label
                                class="block text-sm font-medium flex items-center gap-1.5"
                            >
                                Allowed Child Types
                                <UBadge color="info" variant="subtle" size="xs"
                                    >Optional</UBadge
                                >
                                <UPopover>
                                    <UButton
                                        icon="i-lucide-help-circle"
                                        color="neutral"
                                        variant="ghost"
                                        size="xs"
                                        class="text-muted hover:text-highlighted"
                                    />
                                    <template #content>
                                        <div class="p-4 max-w-xs space-y-2">
                                            <h4 class="font-semibold text-sm">
                                                Allowed Child Types
                                            </h4>
                                            <p class="text-sm text-muted">
                                                Define what types of child
                                                entities can be created under
                                                this root entity.
                                            </p>
                                            <p class="text-sm text-muted">
                                                Leave empty to use system
                                                defaults.
                                            </p>
                                        </div>
                                    </template>
                                </UPopover>
                            </label>

                            <div class="flex flex-wrap gap-2">
                                <UBadge
                                    v-for="type in state.allowed_child_types"
                                    :key="type"
                                    color="primary"
                                    variant="subtle"
                                    class="pr-1"
                                >
                                    {{ formatTypeName(type) }}
                                    <UButton
                                        icon="i-lucide-x"
                                        color="primary"
                                        variant="ghost"
                                        size="xs"
                                        class="ml-1 -mr-1"
                                        @click="removeChildType(type)"
                                    />
                                </UBadge>
                                <UBadge
                                    v-if="
                                        state.allowed_child_types.length === 0
                                    "
                                    color="neutral"
                                    variant="subtle"
                                >
                                    Using system defaults
                                </UBadge>
                            </div>

                            <div class="flex gap-2">
                                <UInput
                                    v-model="newChildType"
                                    placeholder="Add custom type..."
                                    size="sm"
                                    class="flex-1"
                                    @keyup.enter="addChildType"
                                />
                                <UButton
                                    icon="i-lucide-plus"
                                    size="sm"
                                    @click="addChildType"
                                />
                            </div>

                            <div
                                v-if="childTypeSuggestions.length > 0"
                                class="flex flex-wrap gap-1"
                            >
                                <span class="text-xs text-muted mr-1"
                                    >Suggestions:</span
                                >
                                <UButton
                                    v-for="type in childTypeSuggestions.slice(
                                        0,
                                        5,
                                    )"
                                    :key="type"
                                    :label="formatTypeName(type)"
                                    size="xs"
                                    color="neutral"
                                    variant="ghost"
                                    @click="addSuggestedChildType(type)"
                                />
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Columns: Entity Class & Type -->
                <div class="lg:col-span-2 space-y-6">
                    <div>
                        <div class="flex items-center justify-between mb-4">
                            <h3
                                class="text-lg font-semibold flex items-center gap-2"
                            >
                                <UIcon name="i-lucide-layers" class="w-5 h-5" />
                                Entity Classification
                            </h3>
                            <UButton
                                label="Learn about entity types"
                                icon="i-lucide-book-open"
                                color="neutral"
                                variant="ghost"
                                size="xs"
                                @click="showEntityHelp = true"
                            />
                        </div>

                        <div class="space-y-6">
                            <!-- Entity Class -->
                            <div class="space-y-3">
                                <label
                                    class="block text-sm font-medium flex items-center gap-1.5"
                                >
                                    Entity Class
                                    <UPopover>
                                        <UButton
                                            icon="i-lucide-help-circle"
                                            color="neutral"
                                            variant="ghost"
                                            size="xs"
                                            class="text-muted hover:text-highlighted"
                                        />
                                        <template #content>
                                            <div class="p-4 max-w-sm space-y-2">
                                                <h4
                                                    class="font-semibold text-sm"
                                                >
                                                    Entity Classes
                                                </h4>
                                                <p class="text-sm text-muted">
                                                    There are two main types of
                                                    entities in OutlabsAuth:
                                                </p>
                                                <div class="space-y-2 mt-2">
                                                    <div>
                                                        <p
                                                            class="font-medium text-sm"
                                                        >
                                                            Structural
                                                        </p>
                                                        <p
                                                            class="text-xs text-muted"
                                                        >
                                                            Represents
                                                            organizational units
                                                            like departments,
                                                            teams, or projects.
                                                            These form the
                                                            hierarchy of your
                                                            organization.
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <p
                                                            class="font-medium text-sm"
                                                        >
                                                            Access Group
                                                        </p>
                                                        <p
                                                            class="text-xs text-muted"
                                                        >
                                                            Logical groupings
                                                            for permissions that
                                                            don't necessarily
                                                            follow the org
                                                            chart. Used for
                                                            cross-functional
                                                            access control.
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>
                                        </template>
                                    </UPopover>
                                </label>

                                <div class="grid grid-cols-2 gap-4">
                                    <UCard
                                        :class="[
                                            'cursor-pointer transition-all border-2',
                                            state.entity_class === 'structural'
                                                ? 'border-primary bg-primary/5'
                                                : 'border-default hover:border-primary/50',
                                        ]"
                                        @click="
                                            state.entity_class = 'structural';
                                            state.entity_type = '';
                                        "
                                    >
                                        <div
                                            class="flex flex-col items-center text-center space-y-2 p-2"
                                        >
                                            <UIcon
                                                name="i-lucide-sitemap"
                                                class="w-8 h-8"
                                                :class="
                                                    state.entity_class ===
                                                    'structural'
                                                        ? 'text-primary'
                                                        : 'text-muted'
                                                "
                                            />
                                            <div>
                                                <p
                                                    class="font-semibold text-sm"
                                                >
                                                    Structural
                                                </p>
                                                <p class="text-xs text-muted">
                                                    Organizational units
                                                </p>
                                            </div>
                                        </div>
                                    </UCard>

                                    <UCard
                                        :class="[
                                            'cursor-pointer transition-all border-2',
                                            state.entity_class ===
                                            'access_group'
                                                ? 'border-primary bg-primary/5'
                                                : 'border-default hover:border-primary/50',
                                        ]"
                                        @click="
                                            state.entity_class = 'access_group';
                                            state.entity_type = '';
                                        "
                                    >
                                        <div
                                            class="flex flex-col items-center text-center space-y-2 p-2"
                                        >
                                            <UIcon
                                                name="i-lucide-users"
                                                class="w-8 h-8"
                                                :class="
                                                    state.entity_class ===
                                                    'access_group'
                                                        ? 'text-primary'
                                                        : 'text-muted'
                                                "
                                            />
                                            <div>
                                                <p
                                                    class="font-semibold text-sm"
                                                >
                                                    Access Group
                                                </p>
                                                <p class="text-xs text-muted">
                                                    Permission groups
                                                </p>
                                            </div>
                                        </div>
                                    </UCard>
                                </div>
                            </div>

                            <!-- Entity Type -->
                            <div class="space-y-3">
                                <label
                                    class="block text-sm font-medium flex items-center gap-1.5"
                                >
                                    Entity Type
                                    <UPopover>
                                        <UButton
                                            icon="i-lucide-help-circle"
                                            color="neutral"
                                            variant="ghost"
                                            size="xs"
                                            class="text-muted hover:text-highlighted"
                                        />
                                        <template #content>
                                            <div class="p-4 max-w-xs space-y-2">
                                                <h4
                                                    class="font-semibold text-sm"
                                                >
                                                    Entity Type
                                                </h4>
                                                <p class="text-sm text-muted">
                                                    Specifies the specific type
                                                    of entity within the
                                                    selected class. This helps
                                                    organize and identify
                                                    entities in your system.
                                                </p>
                                                <UAlert
                                                    icon="i-lucide-info"
                                                    color="info"
                                                    variant="subtle"
                                                    description="Available types change based on the Entity Class you selected."
                                                    class="mt-2"
                                                />
                                            </div>
                                        </template>
                                    </UPopover>
                                </label>

                                <div class="grid grid-cols-2 gap-3">
                                    <UCard
                                        v-for="type in entityTypes"
                                        :key="type.value"
                                        :class="[
                                            'cursor-pointer transition-all border-2',
                                            state.entity_type === type.value
                                                ? 'border-primary bg-primary/5'
                                                : 'border-default hover:border-primary/50',
                                        ]"
                                        @click="state.entity_type = type.value"
                                    >
                                        <div
                                            class="flex items-center justify-center p-3"
                                        >
                                            <p
                                                class="font-medium text-sm"
                                                :class="
                                                    state.entity_type ===
                                                    type.value
                                                        ? 'text-primary'
                                                        : 'text-default'
                                                "
                                            >
                                                {{ type.label }}
                                            </p>
                                        </div>
                                    </UCard>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex items-center justify-between w-full">
                <div class="text-sm text-muted">
                    All fields are required except description
                </div>
                <div class="flex justify-end gap-2">
                    <UButton
                        label="Cancel"
                        color="neutral"
                        variant="outline"
                        @click="open = false"
                    :disabled="isSubmitting"
                    />
                    <UButton
                        label="Create Entity"
                        icon="i-lucide-plus"
                    :loading="isSubmitting"
                    :disabled="!isFormValid || isSubmitting"
                        @click="handleSubmit"
                    />
                </div>
            </div>
        </template>
    </UModal>

    <!-- Entity Help Slideover -->
    <USlideover v-model:open="showEntityHelp" title="Understanding Entities">
        <template #body>
            <div class="space-y-6">
                <div>
                    <h4 class="font-semibold mb-2">What are Entities?</h4>
                    <p class="text-sm text-muted">
                        Entities are the building blocks of your organization's
                        structure in OutlabsAuth. They represent organizational
                        units, teams, projects, or logical groupings for access
                        control.
                    </p>
                </div>

                <div>
                    <h4 class="font-semibold mb-2">Entity Classes</h4>
                    <div class="space-y-3">
                        <UCard>
                            <div class="space-y-2">
                                <div class="flex items-center gap-2">
                                    <UIcon
                                        name="i-lucide-sitemap"
                                        class="w-5 h-5 text-primary"
                                    />
                                    <h5 class="font-semibold text-sm">
                                        Structural Entities
                                    </h5>
                                </div>
                                <p class="text-sm text-muted">
                                    Represent your organization's hierarchy.
                                    These are concrete organizational units that
                                    form a tree structure.
                                </p>
                                <div class="text-xs text-muted">
                                    <p class="font-medium mb-1">
                                        Common types:
                                    </p>
                                    <ul
                                        class="list-disc list-inside pl-2 space-y-0.5"
                                    >
                                        <li>
                                            Organization - Top-level company or
                                            business unit
                                        </li>
                                        <li>
                                            Department - Functional areas like
                                            Engineering, Sales
                                        </li>
                                        <li>
                                            Team - Smaller groups within
                                            departments
                                        </li>
                                        <li>
                                            Division - Geographic or product
                                            divisions
                                        </li>
                                        <li>
                                            Project - Temporary project-based
                                            structures
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </UCard>

                        <UCard>
                            <div class="space-y-2">
                                <div class="flex items-center gap-2">
                                    <UIcon
                                        name="i-lucide-users"
                                        class="w-5 h-5 text-green-500"
                                    />
                                    <h5 class="font-semibold text-sm">
                                        Access Group Entities
                                    </h5>
                                </div>
                                <p class="text-sm text-muted">
                                    Logical groupings for permissions that don't
                                    follow the org chart. Perfect for
                                    cross-functional access control.
                                </p>
                                <div class="text-xs text-muted">
                                    <p class="font-medium mb-1">
                                        Common types:
                                    </p>
                                    <ul
                                        class="list-disc list-inside pl-2 space-y-0.5"
                                    >
                                        <li>
                                            Access Group - General permission
                                            groups
                                        </li>
                                        <li>
                                            Permission Group - Role-based access
                                            groupings
                                        </li>
                                        <li>
                                            Admin Group - Administrative access
                                            control
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </UCard>
                    </div>
                </div>

                <div>
                    <h4 class="font-semibold mb-2">Hierarchical Structure</h4>
                    <UAlert
                        icon="i-lucide-lightbulb"
                        color="info"
                        variant="subtle"
                        class="mb-3"
                    >
                        <template #title>Tree Permissions</template>
                        <template #description>
                            Entities can be nested to create a hierarchy. Child
                            entities inherit permissions from their parents,
                            making it easy to manage access at different levels
                            of your organization.
                        </template>
                    </UAlert>
                    <div class="bg-muted/30 p-4 rounded-lg text-xs font-mono">
                        <div>Acme Corp (Organization)</div>
                        <div class="ml-4">├─ Engineering (Department)</div>
                        <div class="ml-8">│ ├─ Backend Team (Team)</div>
                        <div class="ml-8">│ └─ Frontend Team (Team)</div>
                        <div class="ml-4">└─ Sales (Department)</div>
                        <div class="ml-8">
                            &nbsp;&nbsp;&nbsp;└─ Enterprise Team (Team)
                        </div>
                    </div>
                </div>

                <div>
                    <h4 class="font-semibold mb-2">Best Practices</h4>
                    <ul class="space-y-2 text-sm text-muted">
                        <li class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check-circle"
                                class="w-4 h-4 mt-0.5 text-success flex-shrink-0"
                            />
                            <span
                                >Use Structural entities for your org chart and
                                reporting structure</span
                            >
                        </li>
                        <li class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check-circle"
                                class="w-4 h-4 mt-0.5 text-success flex-shrink-0"
                            />
                            <span
                                >Use Access Groups for cross-functional
                                permissions that don't map to the org
                                structure</span
                            >
                        </li>
                        <li class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check-circle"
                                class="w-4 h-4 mt-0.5 text-success flex-shrink-0"
                            />
                            <span
                                >Keep your hierarchy shallow (3-5 levels) for
                                easier management</span
                            >
                        </li>
                        <li class="flex items-start gap-2">
                            <UIcon
                                name="i-lucide-check-circle"
                                class="w-4 h-4 mt-0.5 text-success flex-shrink-0"
                            />
                            <span
                                >Use clear, descriptive names that reflect the
                                entity's purpose</span
                            >
                        </li>
                    </ul>
                </div>
            </div>
        </template>
    </USlideover>
</template>
