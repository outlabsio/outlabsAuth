<script setup lang="ts">
/**
 * Entities Tab
 * Manage user's entity memberships (EnterpriseRBAC only)
 * Shows which entities a user belongs to and allows adding/removing memberships
 */

import type { User } from "~/types/auth";
import type { Entity } from "~/types/entity";
import { entitiesQueries } from "~/queries/entities";

const props = defineProps<{
    user: User;
}>();

const userStore = useUserStore();
const toast = useToast();

// User's current entity memberships
const userMemberships = computed(() => userStore.userMemberships);
const isLoadingMemberships = computed(() => userStore.isLoadingMemberships);

// Fetch all available entities
const { data: allEntitiesData, isLoading: isLoadingEntities } = useQuery(
    entitiesQueries.list({}, { page: 1, limit: 100 }),
);

// Map entity IDs to entity objects for display
const entitiesMap = computed(() => {
    const map = new Map<string, Entity>();
    if (allEntitiesData.value?.items) {
        for (const entity of allEntitiesData.value.items) {
            map.set(entity.id, entity);
        }
    }
    return map;
});

// Enriched memberships with entity details
const enrichedMemberships = computed(() => {
    return userMemberships.value
        .map((membership) => ({
            ...membership,
            entity: entitiesMap.value.get(membership.entity_id),
        }))
        .filter((m) => m.entity); // Filter out memberships for deleted entities
});

// Available entities (exclude already joined)
const availableEntities = computed(() => {
    if (!allEntitiesData.value?.items) return [];
    const joinedEntityIds = new Set(
        userMemberships.value.map((m) => m.entity_id),
    );
    return allEntitiesData.value.items.filter(
        (entity) => !joinedEntityIds.has(entity.id),
    );
});

// Selected entity for adding
const selectedEntityId = ref("");

// Add to entity handler
async function handleAddToEntity() {
    if (!selectedEntityId.value) {
        toast.add({
            title: "No entity selected",
            description: "Please select an entity to add the user to",
            color: "warning",
        });
        return;
    }

    const success = await userStore.addToEntity(
        props.user.id,
        selectedEntityId.value,
    );

    if (success) {
        selectedEntityId.value = "";
    }
}

// Remove from entity handler
async function handleRemoveFromEntity(entityId: string) {
    const entity = entitiesMap.value.get(entityId);
    const entityName = entity?.display_name || entity?.name || "this entity";

    const confirmed = confirm(
        `Are you sure you want to remove this user from "${entityName}"?`,
    );

    if (confirmed) {
        await userStore.removeFromEntity(props.user.id, entityId);
    }
}

// Format entity class for badge display
function getEntityClassColor(
    entityClass: string,
): "primary" | "success" | "warning" | "error" | "neutral" {
    return entityClass === "structural" ? "primary" : "success";
}
</script>

<template>
    <div class="flex flex-col gap-6">
        <!-- Header with Add Entity -->
        <div class="flex items-center justify-between gap-4">
            <div>
                <h3 class="text-lg font-semibold text-foreground">
                    Entity Memberships
                </h3>
                <p class="text-sm text-muted">
                    Entities this user belongs to
                </p>
            </div>
            <div v-if="isLoadingEntities" class="flex items-center">
                <UIcon
                    name="i-lucide-loader-2"
                    class="w-5 h-5 animate-spin text-primary"
                />
            </div>
            <div v-else-if="availableEntities.length > 0" class="flex gap-2">
                <USelect
                    v-model="selectedEntityId"
                    :items="
                        availableEntities.map((e) => ({
                            label: e.display_name || e.name,
                            value: e.id,
                        }))
                    "
                    value-key="value"
                    placeholder="Select entity..."
                    class="w-48"
                />
                <UButton
                    icon="i-lucide-plus"
                    label="Add"
                    @click="handleAddToEntity"
                    :disabled="!selectedEntityId"
                />
            </div>
        </div>

        <!-- Current Memberships List -->
        <div class="space-y-3">
            <div v-if="isLoadingMemberships" class="text-center py-8">
                <UIcon
                    name="i-lucide-loader-2"
                    class="w-6 h-6 animate-spin text-primary mb-2"
                />
                <p class="text-sm text-muted">Loading memberships...</p>
            </div>

            <div
                v-else-if="enrichedMemberships.length === 0"
                class="text-center py-8"
            >
                <UIcon
                    name="i-lucide-building-2"
                    class="w-12 h-12 text-muted mb-4"
                />
                <p class="text-sm font-medium text-foreground mb-1">
                    No entity memberships
                </p>
                <p class="text-xs text-muted">
                    This user doesn't belong to any entities yet
                </p>
            </div>

            <UCard
                v-else
                v-for="membership in enrichedMemberships"
                :key="membership.id"
                class="hover:bg-muted/50 transition-colors"
            >
                <div class="flex items-start justify-between">
                    <!-- Entity Info -->
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-1">
                            <p class="font-medium text-foreground">
                                {{
                                    membership.entity?.display_name ||
                                    membership.entity?.name
                                }}
                            </p>
                            <UBadge
                                :color="
                                    getEntityClassColor(
                                        membership.entity?.entity_class || '',
                                    )
                                "
                                variant="subtle"
                                size="xs"
                            >
                                {{ membership.entity?.entity_class }}
                            </UBadge>
                            <UBadge color="neutral" variant="subtle" size="xs">
                                {{ membership.entity?.entity_type }}
                            </UBadge>
                        </div>

                        <p
                            v-if="membership.entity?.description"
                            class="text-sm text-muted mb-2"
                        >
                            {{ membership.entity.description }}
                        </p>

                        <div class="flex items-center gap-4 text-xs text-muted">
                            <div
                                v-if="membership.role_ids.length > 0"
                                class="flex items-center gap-1"
                            >
                                <UIcon name="i-lucide-shield" class="w-3 h-3" />
                                <span
                                    >{{ membership.role_ids.length }}
                                    {{
                                        membership.role_ids.length === 1
                                            ? "role"
                                            : "roles"
                                    }}</span
                                >
                            </div>
                            <div
                                v-if="membership.entity?.status"
                                class="flex items-center gap-1"
                            >
                                <UIcon name="i-lucide-circle" class="w-3 h-3" />
                                <span>{{ membership.entity.status }}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Remove Button -->
                    <UButton
                        icon="i-lucide-trash"
                        color="error"
                        variant="ghost"
                        size="sm"
                        @click="handleRemoveFromEntity(membership.entity_id)"
                    />
                </div>
            </UCard>
        </div>
    </div>
</template>
