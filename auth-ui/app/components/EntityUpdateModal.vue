<script setup lang="ts">
import type { EntityClass, Entity } from "~/types/entity";
import { useUpdateEntityMutation } from "~/queries/entities";
import { createEntitiesAPI } from "~/api/entities";

const props = defineProps<{
    entityId: string;
}>();

const open = defineModel<boolean>("open", { default: false });

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
                existingEntity.value = await api.fetchEntity(entityId as string);
            } catch (error) {
                console.error("Failed to fetch entity:", error);
            } finally {
                isLoadingEntity.value = false;
            }
        }
    },
    { immediate: true },
);

// Form state (only editable fields)
const state = reactive({
    display_name: "",
    description: "",
    status: "active" as "active" | "inactive" | "archived",
});

// Pre-populate form when entity data loads
watch(
    existingEntity,
    (entity) => {
        if (entity) {
            state.display_name = entity.display_name;
            state.description = entity.description || "";
            state.status = entity.status as "active" | "inactive" | "archived";
        }
    },
    { immediate: true },
);

// Status options
const statusOptions = [
    { label: "Active", value: "active" },
    { label: "Inactive", value: "inactive" },
    { label: "Archived", value: "archived" },
];

// Submit handler using mutation
const { mutateAsync: updateEntity, isPending } = useUpdateEntityMutation();

async function handleSubmit() {
    try {
        await updateEntity({
            entityId: props.entityId,
            data: {
                display_name: state.display_name,
                description: state.description || undefined,
                status: state.status,
            },
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
            <div v-if="isLoadingEntity" class="flex items-center justify-center py-12">
                <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
            </div>

            <div v-else class="space-y-4">
                <!-- Read-only info -->
                <div class="grid grid-cols-2 gap-4">
                    <div class="space-y-2">
                        <label class="block text-sm font-medium text-muted">Name</label>
                        <UInput
                            :model-value="existingEntity?.name"
                            disabled
                            icon="i-lucide-tag"
                        />
                        <p class="text-xs text-muted">Cannot be changed</p>
                    </div>
                    <div class="space-y-2">
                        <label class="block text-sm font-medium text-muted">Slug</label>
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
                        <label class="block text-sm font-medium text-muted">Class</label>
                        <UInput
                            :model-value="existingEntity?.entity_class"
                            disabled
                            icon="i-lucide-layers"
                        />
                    </div>
                    <div class="space-y-2">
                        <label class="block text-sm font-medium text-muted">Type</label>
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
                    <label class="block text-sm font-medium">Display Name</label>
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
                    <USelect
                        v-model="state.status"
                        :items="statusOptions"
                    />
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
                    :disabled="isPending"
                />
                <UButton
                    label="Save Changes"
                    icon="i-lucide-save"
                    :loading="isPending"
                    @click="handleSubmit"
                />
            </div>
        </template>
    </UModal>
</template>
