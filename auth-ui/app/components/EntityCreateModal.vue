<script setup lang="ts">
import type { EntityClass } from "~/types/entity";
import { useCreateEntityMutation } from "~/queries/entities";

const open = defineModel<boolean>("open", { default: false });

const entitiesStore = useEntitiesStore();
const { mutateAsync: createEntity, isPending } = useCreateEntityMutation();

// Form state
const state = reactive({
    name: "",
    display_name: "",
    slug: "",
    description: "",
    entity_class: "structural" as EntityClass,
    entity_type: "",
    parent_entity_id: undefined as string | undefined,
});

// Auto-generate slug and display_name from name
watch(
    () => state.name,
    (newName) => {
        if (newName) {
            // Auto-set display_name to match name
            state.display_name = newName;
            // Auto-generate slug if not already set
            if (!state.slug) {
                state.slug = newName
                    .toLowerCase()
                    .replace(/\s+/g, "-")
                    .replace(/[^a-z0-9-]/g, "");
            }
        }
    },
);

// Entity type options
const entityTypes = computed(() => {
    if (state.entity_class === "structural") {
        return [
            { label: "Organization", value: "organization" },
            { label: "Department", value: "department" },
            { label: "Team", value: "team" },
            { label: "Division", value: "division" },
            { label: "Project", value: "project" },
        ];
    } else {
        return [
            { label: "Access Group", value: "access_group" },
            { label: "Permission Group", value: "permission_group" },
            { label: "Admin Group", value: "admin_group" },
        ];
    }
});

// Parent entity options (root entities only)
const parentOptions = computed(() => [
    { label: "None (Root Entity)", value: undefined },
    ...entitiesStore.rootEntities.map((e) => ({
        label: `${e.name} (${e.entity_type})`,
        value: e.id,
    })),
]);

// Submit handler
const showEntityHelp = ref(false);

async function handleSubmit() {
    try {
        await createEntity(state);

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
        });
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
                        :disabled="isPending"
                    />
                    <UButton
                        label="Create Entity"
                        icon="i-lucide-plus"
                        :loading="isPending"
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
