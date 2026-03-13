<script setup lang="ts">
import type { EntityClass, Entity } from "~/types/entity";
import { useUpdateEntityMutation } from "~/queries/entities";
import { createEntitiesAPI } from "~/api/entities";

const props = defineProps<{
    entityId: string;
}>();

const open = defineModel<boolean>("open", { default: false });

// Stores
const configStore = useConfigStore();

// Initialize config store for suggestions
onMounted(async () => {
    await configStore.fetchEntityTypeConfig();
});

// Fetch existing entity data when modal opens
const existingEntity = ref<Entity | null>(null);
const isLoadingEntity = ref(false);

watch(
    () => [open.value, props.entityId],
    async ([isOpen, entityId]) => {
        if (isOpen && entityId) {
            isLoadingEntity.value = true;
            try {
                const api = createEntitiesAPI();
                existingEntity.value = await api.fetchEntity(
                    entityId as string,
                );
            } catch (error) {
                console.error("Failed to fetch entity:", error);
            } finally {
                isLoadingEntity.value = false;
            }
        }
    },
    { immediate: true },
);

// Form state (editable fields)
const state = reactive({
    display_name: "",
    description: "",
    status: "active" as "active" | "inactive" | "archived",
    // Child type configuration (root entities only)
    allowed_child_types: [] as string[],
    allowed_child_classes: [] as string[],
});

// New child type input
const newChildType = ref("");

// Pre-populate form when entity data loads
watch(
    existingEntity,
    (entity) => {
        if (entity) {
            state.display_name = entity.display_name;
            state.description = entity.description || "";
            state.status = entity.status as "active" | "inactive" | "archived";
            state.allowed_child_types = entity.allowed_child_types || [];
            state.allowed_child_classes = entity.allowed_child_classes || [];
        }
    },
    { immediate: true },
);

// Check if this is a root entity (no parent)
const isRootEntity = computed(() => !existingEntity.value?.parent_entity_id);

// Suggestions for child types (exclude already added ones)
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

// Add child type (no remove - add-only mode per DD-052)
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

// Status options
const statusOptions = [
    { label: "Active", value: "active" },
    { label: "Inactive", value: "inactive" },
    { label: "Archived", value: "archived" },
];

// Submit handler using mutation
const { mutateAsync: updateEntity, isLoading: isSubmitting } = useUpdateEntityMutation();

async function handleSubmit() {
    try {
        // Build payload - include child type config only for root entities
        const payload: Record<string, any> = {
            display_name: state.display_name,
            description: state.description || undefined,
            status: state.status,
        };

        // Include child type configuration for root entities
        if (isRootEntity.value) {
            if (state.allowed_child_types.length > 0) {
                payload.allowed_child_types = state.allowed_child_types;
            }
            if (state.allowed_child_classes.length > 0) {
                payload.allowed_child_classes = state.allowed_child_classes;
            }
        }

        await updateEntity({
            entityId: props.entityId,
            data: payload,
        });
        // Close modal on success (mutation handles toast)
        open.value = false;
    } catch (error: any) {
        console.error("Failed to update entity:", error);
    }
}
</script>

<template>
    <UModal
        v-model:open="open"
        title="Edit Entity"
        description="Update entity details"
    >
        <template #body>
            <div
                v-if="isLoadingEntity"
                class="flex items-center justify-center py-12"
            >
                <UIcon
                    name="i-lucide-loader-2"
                    class="w-8 h-8 animate-spin text-primary"
                />
            </div>

            <div v-else class="space-y-4">
                <!-- Read-only info -->
                <div class="grid grid-cols-2 gap-4">
                    <div class="space-y-2">
                        <label class="block text-sm font-medium text-muted"
                            >Name</label
                        >
                        <UInput
                            :model-value="existingEntity?.name"
                            disabled
                            icon="i-lucide-tag"
                        />
                        <p class="text-xs text-muted">Cannot be changed</p>
                    </div>
                    <div class="space-y-2">
                        <label class="block text-sm font-medium text-muted"
                            >Slug</label
                        >
                        <UInput
                            :model-value="existingEntity?.slug"
                            disabled
                            icon="i-lucide-link"
                        />
                        <p class="text-xs text-muted">Cannot be changed</p>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div class="space-y-2">
                        <label class="block text-sm font-medium text-muted"
                            >Class</label
                        >
                        <UInput
                            :model-value="existingEntity?.entity_class"
                            disabled
                            icon="i-lucide-layers"
                        />
                    </div>
                    <div class="space-y-2">
                        <label class="block text-sm font-medium text-muted"
                            >Type</label
                        >
                        <UInput
                            :model-value="existingEntity?.entity_type"
                            disabled
                            icon="i-lucide-building"
                        />
                    </div>
                </div>

                <USeparator />

                <!-- Editable fields -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium"
                        >Display Name</label
                    >
                    <UInput
                        v-model="state.display_name"
                        placeholder="Human-readable name"
                        icon="i-lucide-type"
                    />
                </div>

                <div class="space-y-2">
                    <label class="block text-sm font-medium">Description</label>
                    <UTextarea
                        v-model="state.description"
                        placeholder="A brief description of this entity..."
                        :rows="3"
                    />
                </div>

                <div class="space-y-2">
                    <label class="block text-sm font-medium">Status</label>
                    <USelect v-model="state.status" :items="statusOptions" />
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
                            >Add only</UBadge
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
                                        Define what types of child entities can
                                        be created under this root entity.
                                    </p>
                                    <p class="text-sm text-muted">
                                        Leave empty to use system defaults. New
                                        types can be added but existing types
                                        cannot be removed.
                                    </p>
                                </div>
                            </template>
                        </UPopover>
                    </label>

                    <!-- Existing types (read-only display) -->
                    <div class="flex flex-wrap gap-2">
                        <UBadge
                            v-for="type in state.allowed_child_types"
                            :key="type"
                            color="primary"
                            variant="subtle"
                        >
                            {{ formatTypeName(type) }}
                        </UBadge>
                        <UBadge
                            v-if="state.allowed_child_types.length === 0"
                            color="neutral"
                            variant="subtle"
                        >
                            Using system defaults
                        </UBadge>
                    </div>

                    <!-- Add new type -->
                    <div class="flex gap-2">
                        <UInput
                            v-model="newChildType"
                            placeholder="Add new type..."
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

                    <!-- Suggestions -->
                    <div
                        v-if="childTypeSuggestions.length > 0"
                        class="flex flex-wrap gap-1"
                    >
                        <span class="text-xs text-muted mr-1"
                            >Suggestions:</span
                        >
                        <UButton
                            v-for="type in childTypeSuggestions.slice(0, 5)"
                            :key="type"
                            :label="formatTypeName(type)"
                            size="xs"
                            color="neutral"
                            variant="ghost"
                            @click="addSuggestedChildType(type)"
                        />
                    </div>

                    <p class="text-xs text-muted">
                        Types can be added but not removed. Contact support to
                        remove types.
                    </p>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex justify-end gap-2">
                <UButton
                    label="Cancel"
                    color="neutral"
                    variant="outline"
                    @click="open = false"
                    :disabled="isSubmitting"
                />
                <UButton
                    label="Save Changes"
                    icon="i-lucide-save"
                    :loading="isSubmitting"
                    @click="handleSubmit"
                />
            </div>
        </template>
    </UModal>
</template>
