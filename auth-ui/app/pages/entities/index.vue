<script setup lang="ts">
import type { TableColumn, TreeItem, BreadcrumbItem } from "@nuxt/ui";
import type { Entity, EntityClass } from "~/types/entity";
import type { EntityMember } from "~/types/membership";
import type { UiColor } from "~/types/ui";
import { useQuery } from "@pinia/colada";
import { entitiesQueries, useDeleteEntityMutation } from "~/queries/entities";
import {
    membershipsQueries,
    useRemoveMemberMutation,
} from "~/queries/memberships";
import { rolesQueries, useDeleteRoleMutation } from "~/queries/roles";
import type { Role } from "~/types/role";
import { UButton, UBadge } from "#components";

// Resolve components for use in cell renderers
const UButtonResolved = resolveComponent("UButton");
const UBadgeResolved = resolveComponent("UBadge");
const UIcon = resolveComponent("UIcon");

// State
const treeSearch = ref("");
const showCreateModal = ref(false);
const showEditModal = ref(false);
const showAddMemberModal = ref(false);
const showEditMemberRolesModal = ref(false);
const showCreateEntityRoleModal = ref(false);
const showEditRoleModal = ref(false);
const editEntityId = ref<string | null>(null);
const editRoleId = ref<string | null>(null);
const selectedTreeEntityId = ref<string | undefined>(undefined);
const activeTab = ref("children"); // "children" | "members" | "roles"
const editingMember = ref<EntityMember | null>(null);
const showActionConfirm = ref(false);
const pendingAction = ref<
    | { kind: "delete-entity"; entity: Entity }
    | { kind: "remove-member"; member: EntityMember; entityId: string }
    | { kind: "delete-role"; role: Role }
    | null
>(null);
const isConfirmingAction = ref(false);

// Query all entities
const { data: entitiesData, isLoading } = useQuery(
    entitiesQueries.list({}, { page: 1, limit: 500 }),
);

// Query entity members (only when entity selected and members tab active)
const { data: membersData, isLoading: isMembersLoading } = useQuery(() => ({
    ...membershipsQueries.entityMembersWithDetails(
        selectedTreeEntityId.value || "",
    ),
    enabled:
        !!selectedTreeEntityId.value && activeTab.value === "members",
}));

// Query entity roles (only when entity selected and roles tab active)
const { data: entityRolesData, isLoading: isRolesLoading } = useQuery(() => ({
    ...rolesQueries.list(
        { for_entity_id: selectedTreeEntityId.value || "" },
        { limit: 100 },
    ),
    enabled:
        !!selectedTreeEntityId.value && activeTab.value === "roles",
}));

// Mutations
const { mutate: deleteEntity } = useDeleteEntityMutation();
const { mutate: removeMember } = useRemoveMemberMutation();
const { mutate: deleteRole } = useDeleteRoleMutation();

// Entity members list
const entityMembers = computed(() => membersData.value || []);

// Entity roles grouped by type
const entityRoles = computed(() => entityRolesData.value?.items || []);

const rolesByType = computed(() => {
    const roles = entityRoles.value;
    const grouped = {
        entityLocal: [] as Role[],
        inherited: [] as Role[],
        global: [] as Role[],
    };

    for (const role of roles) {
        if (role.is_global) {
            grouped.global.push(role);
        } else if (role.scope_entity_id === selectedTreeEntityId.value) {
            grouped.entityLocal.push(role);
        } else if (role.scope_entity_id) {
            // Entity-local from an ancestor (inherited)
            grouped.inherited.push(role);
        } else {
            // Org-scoped (root_entity_id set but no scope_entity_id)
            grouped.global.push(role);
        }
    }

    return grouped;
});

// Get all entities as flat array
const allEntities = computed(() => entitiesData.value?.items || []);

// Entity tree node type
interface EntityTreeNode extends Entity {
    children: EntityTreeNode[];
    depth: number;
}

// Build tree from flat entity list
function buildTree(
    entities: Entity[],
    parentEntityId?: string | null,
    depth = 0,
): EntityTreeNode[] {
    return entities
        .filter((e) => {
            // Handle null vs undefined - API returns null, code uses undefined
            if (!parentEntityId) {
                return !e.parent_entity_id; // matches both null and undefined
            }
            return e.parent_entity_id === parentEntityId;
        })
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((entity) => ({
            ...entity,
            depth,
            children: buildTree(entities, entity.id, depth + 1),
        }));
}

// Entity tree computed
const entityTree = computed(() => buildTree(allEntities.value));

// Icon mapping for entity types
function getEntityIcon(entityClass: EntityClass, entityType: string): string {
    const icons: Record<string, string> = {
        organization: "i-lucide-building-2",
        department: "i-lucide-layout-grid",
        team: "i-lucide-users",
        office: "i-lucide-map-pin",
        region: "i-lucide-globe",
        division: "i-lucide-git-branch",
        project: "i-lucide-folder",
        access_group: "i-lucide-shield",
        permission_group: "i-lucide-lock",
        admin_group: "i-lucide-user-cog",
    };
    return (
        icons[entityType] ||
        (entityClass === "structural" ? "i-lucide-building" : "i-lucide-users")
    );
}

// Transform entity tree to UTree items
interface EntityTreeItem extends TreeItem {
    id: string;
    entity: EntityTreeNode;
    children?: EntityTreeItem[];
}

function entitiesToTreeItems(nodes: EntityTreeNode[]): EntityTreeItem[] {
    return nodes.map((node) => ({
        id: node.id,
        label: node.display_name || node.name,
        icon: getEntityIcon(node.entity_class, node.entity_type),
        defaultExpanded: node.depth === 0,
        entity: node,
        children: node.children?.length
            ? entitiesToTreeItems(node.children)
            : undefined,
    }));
}

// Tree items computed
const treeItems = computed(() => {
    const items = entitiesToTreeItems(entityTree.value);

    // Filter by search if search is active
    if (treeSearch.value) {
        const searchLower = treeSearch.value.toLowerCase();
        // For search, flatten and filter
        const filterTree = (items: EntityTreeItem[]): EntityTreeItem[] => {
            return items.reduce((acc: EntityTreeItem[], item) => {
                const matches =
                    item.entity.name.toLowerCase().includes(searchLower) ||
                    item.entity.display_name
                        ?.toLowerCase()
                        .includes(searchLower) ||
                    item.entity.entity_type.toLowerCase().includes(searchLower);

                const filteredChildren = item.children
                    ? filterTree(item.children)
                    : [];

                if (matches || filteredChildren.length > 0) {
                    acc.push({
                        ...item,
                        defaultExpanded: true,
                        children:
                            filteredChildren.length > 0
                                ? filteredChildren
                                : item.children,
                    });
                }

                return acc;
            }, []);
        };
        return filterTree(items);
    }

    return items;
});

// Helper to find tree item by ID (recursive search)
function findTreeItemById(
    items: EntityTreeItem[],
    id: string,
): EntityTreeItem | undefined {
    for (const item of items) {
        if (item.id === id) return item;
        if (item.children) {
            const found = findTreeItemById(item.children, id);
            if (found) return found;
        }
    }
    return undefined;
}

// Computed for tree v-model - converts between ID and item object
const selectedTreeItem = computed({
    get(): EntityTreeItem | undefined {
        if (!selectedTreeEntityId.value) return undefined;
        return findTreeItemById(treeItems.value, selectedTreeEntityId.value);
    },
    set(item: EntityTreeItem | undefined) {
        selectedTreeEntityId.value = item?.id;
    },
});

// Selected entity from tree
const selectedEntity = computed(() => {
    if (!selectedTreeEntityId.value) return null;
    return allEntities.value.find((e) => e.id === selectedTreeEntityId.value);
});

// Children of selected entity (or root entities if none selected)
const childEntities = computed(() => {
    if (!selectedTreeEntityId.value) {
        return allEntities.value.filter((e) => !e.parent_entity_id);
    }
    return allEntities.value.filter(
        (e) => e.parent_entity_id === selectedTreeEntityId.value,
    );
});

// Extended breadcrumb item with entity ID for click handling
interface EntityBreadcrumbItem extends BreadcrumbItem {
    entityId?: string;
}

// Build breadcrumb path to selected entity
const breadcrumbItems = computed((): EntityBreadcrumbItem[] => {
    if (!selectedEntity.value) return [];

    const path: EntityBreadcrumbItem[] = [];
    let current: Entity | undefined = selectedEntity.value;

    // Build path from selected entity to root
    while (current) {
        path.unshift({
            label: current.display_name || current.name,
            icon: getEntityIcon(current.entity_class, current.entity_type),
            entityId: current.id,
        });
        if (current.parent_entity_id) {
            current = allEntities.value.find(
                (e) => e.id === current!.parent_entity_id,
            );
        } else {
            break;
        }
    }

    // Add root item (no entityId = go to root)
    path.unshift({
        label: "All Entities",
        icon: "i-lucide-home",
        entityId: undefined,
    });

    return path;
});

// Handle breadcrumb click
function onBreadcrumbClick(item: EntityBreadcrumbItem) {
    selectedTreeEntityId.value = item.entityId;
}

// Open edit modal
function openEditModal(entityId: string) {
    editEntityId.value = entityId;
    showEditModal.value = true;
}

// Navigate into entity (show children)
function navigateToEntity(entityId: string) {
    selectedTreeEntityId.value = entityId;
}

// Handle tree selection - extract ID from the select event
function onTreeSelect(e: any) {
    // The event contains the item in e.detail or directly as the item
    const item = e?.item || e;
    if (item?.id) {
        selectedTreeEntityId.value = item.id;
    }
}

// Open edit member roles modal
function openEditMemberRolesModal(member: EntityMember) {
    editingMember.value = member;
    showEditMemberRolesModal.value = true;
}

// Open edit role modal
function openEditRoleModal(roleId: string) {
    editRoleId.value = roleId;
    showEditRoleModal.value = true;
}

const actionConfirmMeta = computed<{
    title: string;
    description: string;
    confirmLabel: string;
    confirmColor: UiColor;
}>(() => {
    if (!pendingAction.value) {
        return {
            title: "Confirm action",
            description: "",
            confirmLabel: "Confirm",
            confirmColor: "error",
        };
    }

    if (pendingAction.value.kind === "delete-entity") {
        return {
            title: "Delete entity?",
            description: `This will permanently delete '${pendingAction.value.entity.display_name || pendingAction.value.entity.name}'.`,
            confirmLabel: "Delete entity",
            confirmColor: "error",
        };
    }

    if (pendingAction.value.kind === "remove-member") {
        return {
            title: "Remove member?",
            description: `Remove '${pendingAction.value.member.user_email}' from this entity.`,
            confirmLabel: "Remove member",
            confirmColor: "warning",
        };
    }

    return {
        title: "Delete role?",
        description: `This will permanently delete '${pendingAction.value.role.display_name || pendingAction.value.role.name}'.`,
        confirmLabel: "Delete role",
        confirmColor: "error",
    };
});

function requestDeleteEntity(entity: Entity) {
    pendingAction.value = { kind: "delete-entity", entity };
    showActionConfirm.value = true;
}

function requestRemoveMember(member: EntityMember) {
    if (!selectedTreeEntityId.value) {
        return;
    }
    pendingAction.value = {
        kind: "remove-member",
        member,
        entityId: selectedTreeEntityId.value,
    };
    showActionConfirm.value = true;
}

function requestDeleteRole(role: Role) {
    pendingAction.value = { kind: "delete-role", role };
    showActionConfirm.value = true;
}

function resetActionConfirm() {
    if (isConfirmingAction.value) {
        return;
    }
    showActionConfirm.value = false;
    pendingAction.value = null;
}

async function confirmPendingAction() {
    if (!pendingAction.value) {
        return;
    }

    isConfirmingAction.value = true;
    try {
        if (pendingAction.value.kind === "delete-entity") {
            await deleteEntity({
                entityId: pendingAction.value.entity.id,
                parentId: pendingAction.value.entity.parent_entity_id,
            });
        } else if (pendingAction.value.kind === "remove-member") {
            await removeMember({
                entityId: pendingAction.value.entityId,
                userId: pendingAction.value.member.user_id,
            });
        } else {
            await deleteRole(pendingAction.value.role.id);
        }

        showActionConfirm.value = false;
        pendingAction.value = null;
    } finally {
        isConfirmingAction.value = false;
    }
}

watch(showActionConfirm, (isOpen) => {
    if (!isOpen && !isConfirmingAction.value) {
        pendingAction.value = null;
    }
});

// Get scope badge for roles
function getRoleScopeBadge(role: Role): { color: UiColor; label: string } {
    if (role.is_global) return { color: "info", label: "Global" };
    if (role.scope === "entity_only")
        return { color: "warning", label: "This entity only" };
    return { color: "success", label: "Hierarchy" };
}

// Table columns
const columns: TableColumn<Entity>[] = [
    {
        accessorKey: "name",
        header: "Entity",
        cell: ({ row }) => {
            const hasChildren = allEntities.value.some(
                (e) => e.parent_entity_id === row.original.id,
            );
            return h("div", { class: "flex items-center gap-3" }, [
                h(UIcon, {
                    name: getEntityIcon(
                        row.original.entity_class,
                        row.original.entity_type,
                    ),
                    class: "w-5 h-5 text-muted shrink-0",
                }),
                h("div", { class: "flex flex-col gap-0.5" }, [
                    h(
                        "button",
                        {
                            class: "font-medium text-left hover:text-primary transition-colors",
                            onClick: () => navigateToEntity(row.original.id),
                        },
                        [
                            row.original.display_name || row.original.name,
                            hasChildren &&
                                h(UIcon, {
                                    name: "i-lucide-chevron-right",
                                    class: "w-4 h-4 inline ml-1 text-muted",
                                }),
                        ],
                    ),
                    h(
                        "p",
                        { class: "text-xs text-muted" },
                        row.original.entity_type,
                    ),
                ]),
            ]);
        },
    },
    {
        accessorKey: "entity_class",
        header: "Class",
        cell: ({ row }) =>
            h(
                UBadgeResolved,
                {
                    color:
                        row.original.entity_class === "structural"
                            ? "primary"
                            : "success",
                    variant: "subtle",
                    size: "xs",
                },
                () => row.original.entity_class,
            ),
    },
    {
        accessorKey: "description",
        header: "Description",
        cell: ({ row }) =>
            h(
                "span",
                { class: "text-sm text-muted truncate max-w-xs block" },
                row.original.description || "-",
            ),
    },
    {
        id: "actions",
        header: "Actions",
        cell: ({ row }) =>
            h("div", { class: "flex items-center gap-1" }, [
                h(UButtonResolved, {
                    icon: "i-lucide-folder-open",
                    color: "neutral",
                    variant: "ghost",
                    size: "xs",
                    title: "View children",
                    onClick: () => navigateToEntity(row.original.id),
                }),
                h(UButtonResolved, {
                    icon: "i-lucide-pencil",
                    color: "neutral",
                    variant: "ghost",
                    size: "xs",
                    onClick: () => openEditModal(row.original.id),
                }),
                h(UButtonResolved, {
                    icon: "i-lucide-trash-2",
                    color: "error",
                    variant: "ghost",
                    size: "xs",
                    onClick: () => requestDeleteEntity(row.original),
                }),
            ]),
    },
];

// Create child entity with pre-filled parent
const createParentId = computed(() => selectedTreeEntityId.value || undefined);

// Members table columns
const memberColumns: TableColumn<EntityMember>[] = [
    {
        accessorKey: "user_email",
        header: "User",
        cell: ({ row }) =>
            h("div", { class: "flex flex-col gap-0.5" }, [
                h(
                    "span",
                    { class: "font-medium" },
                    row.original.user_first_name && row.original.user_last_name
                        ? `${row.original.user_first_name} ${row.original.user_last_name}`
                        : row.original.user_email,
                ),
                h(
                    "span",
                    { class: "text-xs text-muted" },
                    row.original.user_email,
                ),
            ]),
    },
    {
        accessorKey: "roles",
        header: "Roles",
        cell: ({ row }) =>
            h(
                "div",
                { class: "flex flex-wrap gap-1 items-center" },
                row.original.roles.length > 0
                    ? [
                          ...row.original.roles.slice(0, 3).map((role) =>
                              h(
                                  UBadgeResolved,
                                  {
                                      color: "primary",
                                      variant: "subtle",
                                      size: "xs",
                                  },
                                  () => role.display_name || role.name,
                              ),
                          ),
                          row.original.roles.length > 3 &&
                              h(
                                  UBadgeResolved,
                                  {
                                      color: "neutral",
                                      variant: "subtle",
                                      size: "xs",
                                  },
                                  () => `+${row.original.roles.length - 3}`,
                              ),
                      ].filter(Boolean)
                    : h("span", { class: "text-muted text-sm" }, "No roles"),
            ),
    },
    {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) =>
            h(
                UBadgeResolved,
                {
                    color:
                        row.original.status === "active"
                            ? "success"
                            : "warning",
                    variant: "subtle",
                    size: "xs",
                },
                () => row.original.status,
            ),
    },
    {
        accessorKey: "joined_at",
        header: "Joined",
        cell: ({ row }) =>
            h(
                "span",
                { class: "text-sm text-muted" },
                new Date(row.original.joined_at).toLocaleDateString(),
            ),
    },
    {
        id: "actions",
        header: "Actions",
        cell: ({ row }) =>
            h("div", { class: "flex items-center gap-1" }, [
                h(UButtonResolved, {
                    icon: "i-lucide-shield",
                    color: "neutral",
                    variant: "ghost",
                    size: "xs",
                    title: "Edit roles",
                    onClick: () => openEditMemberRolesModal(row.original),
                }),
                h(UButtonResolved, {
                    icon: "i-lucide-trash-2",
                    color: "error",
                    variant: "ghost",
                    size: "xs",
                    title: "Remove member",
                    onClick: () => requestRemoveMember(row.original),
                }),
            ]),
    },
];

// Tab items
const tabItems = [
    { label: "Children", value: "children", icon: "i-lucide-folder-tree" },
    { label: "Members", value: "members", icon: "i-lucide-users" },
    { label: "Roles", value: "roles", icon: "i-lucide-shield" },
];
</script>

<template>
    <div class="flex flex-1">
        <!-- Left Panel: Tree Navigator -->
        <UDashboardPanel
            id="entity-tree"
            resizable
            :min-size="15"
            :default-size="22"
            :max-size="35"
        >
            <div class="flex flex-col flex-1 min-h-0">
                <!-- Header -->
                <UDashboardNavbar title="Hierarchy">
                    <template #leading>
                        <UDashboardSidebarCollapse />
                    </template>
                    <template #right>
                        <UButton
                            icon="i-lucide-plus"
                            size="xs"
                            variant="ghost"
                            color="neutral"
                            @click="showCreateModal = true"
                        />
                    </template>
                </UDashboardNavbar>

                <!-- Search -->
                <div class="px-3 py-2 border-b border-default">
                    <UInput
                        v-model="treeSearch"
                        icon="i-lucide-search"
                        placeholder="Search..."
                        size="sm"
                    />
                </div>

                <!-- Loading State -->
                <div
                    v-if="isLoading"
                    class="flex-1 flex items-center justify-center"
                >
                    <UIcon
                        name="i-lucide-loader-2"
                        class="w-6 h-6 animate-spin text-primary"
                    />
                </div>

                <!-- Tree -->
                <div v-else class="flex-1 overflow-y-auto">
                    <div v-if="treeItems.length === 0" class="p-4 text-center">
                        <UIcon
                            name="i-lucide-folder-tree"
                            class="w-8 h-8 text-muted mb-2"
                        />
                        <p class="text-sm text-muted">No entities yet</p>
                    </div>
                    <UTree
                        v-else
                        v-model="selectedTreeItem"
                        :items="treeItems"
                        :get-key="(item: EntityTreeItem) => item.id"
                        color="primary"
                        size="sm"
                        @select="onTreeSelect"
                    />
                </div>
            </div>
        </UDashboardPanel>

        <!-- Right Panel: Entity Content -->
        <UDashboardPanel id="entity-content">
            <div class="flex flex-col flex-1 min-h-0">
                <!-- Header -->
                <UDashboardNavbar
                    :title="
                        selectedEntity?.display_name ||
                        selectedEntity?.name ||
                        'All Entities'
                    "
                >
                    <template #right>
                        <UButton
                            v-if="!selectedEntity || activeTab === 'children'"
                            icon="i-lucide-plus"
                            :label="
                                selectedEntity ? 'Add Child' : 'Create Entity'
                            "
                            color="primary"
                            @click="showCreateModal = true"
                        />
                        <UButton
                            v-else-if="activeTab === 'members'"
                            icon="i-lucide-user-plus"
                            label="Add Member"
                            color="primary"
                            @click="showAddMemberModal = true"
                        />
                        <UButton
                            v-else-if="activeTab === 'roles'"
                            icon="i-lucide-shield-plus"
                            label="Create Role"
                            color="primary"
                            @click="showCreateEntityRoleModal = true"
                        />
                    </template>
                </UDashboardNavbar>

                <!-- Breadcrumb -->
                <div
                    v-if="breadcrumbItems.length > 1"
                    class="px-4 py-2 border-b border-default"
                >
                    <UBreadcrumb :items="breadcrumbItems">
                        <template #item="{ item, index }">
                            <button
                                type="button"
                                class="flex items-center gap-1.5 text-sm min-w-0 hover:text-default transition-colors"
                                :class="
                                    index === breadcrumbItems.length - 1
                                        ? 'text-primary font-semibold'
                                        : 'text-muted font-medium'
                                "
                                @click="onBreadcrumbClick(item)"
                            >
                                <UIcon
                                    v-if="item.icon"
                                    :name="item.icon"
                                    class="shrink-0 size-5"
                                />
                                <span class="truncate">{{ item.label }}</span>
                            </button>
                        </template>
                    </UBreadcrumb>
                </div>

                <!-- Entity Info Card (when entity selected) -->
                <div
                    v-if="selectedEntity"
                    class="px-4 py-3 border-b border-default bg-muted/30"
                >
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div
                                class="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center"
                            >
                                <UIcon
                                    :name="
                                        getEntityIcon(
                                            selectedEntity.entity_class,
                                            selectedEntity.entity_type,
                                        )
                                    "
                                    class="w-5 h-5 text-primary"
                                />
                            </div>
                            <div>
                                <p class="font-medium">
                                    {{
                                        selectedEntity.display_name ||
                                        selectedEntity.name
                                    }}
                                </p>
                                <div class="flex items-center gap-2 text-xs">
                                    <UBadge
                                        :color="
                                            selectedEntity.entity_class ===
                                            'structural'
                                                ? 'primary'
                                                : 'success'
                                        "
                                        variant="subtle"
                                        size="xs"
                                    >
                                        {{ selectedEntity.entity_class }}
                                    </UBadge>
                                    <span class="text-muted">{{
                                        selectedEntity.entity_type
                                    }}</span>
                                </div>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <UButton
                                icon="i-lucide-pencil"
                                label="Edit"
                                variant="outline"
                                color="neutral"
                                size="sm"
                                @click="openEditModal(selectedEntity.id)"
                            />
                        </div>
                    </div>
                    <p
                        v-if="selectedEntity.description"
                        class="text-sm text-muted mt-2"
                    >
                        {{ selectedEntity.description }}
                    </p>
                </div>

                <!-- Tabs (when entity selected) -->
                <div
                    v-if="selectedEntity"
                    class="px-4 py-2 border-b border-default"
                >
                    <div class="flex gap-4">
                        <button
                            v-for="tab in tabItems"
                            :key="tab.value"
                            class="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors"
                            :class="
                                activeTab === tab.value
                                    ? 'bg-primary/10 text-primary'
                                    : 'text-muted hover:text-default hover:bg-muted/50'
                            "
                            @click="activeTab = tab.value"
                        >
                            <UIcon :name="tab.icon" class="w-4 h-4" />
                            {{ tab.label }}
                            <UBadge
                                v-if="
                                    tab.value === 'children' &&
                                    childEntities.length > 0
                                "
                                :label="String(childEntities.length)"
                                size="xs"
                                color="neutral"
                                variant="subtle"
                            />
                            <UBadge
                                v-if="
                                    tab.value === 'members' &&
                                    entityMembers.length > 0
                                "
                                :label="String(entityMembers.length)"
                                size="xs"
                                color="neutral"
                                variant="subtle"
                            />
                            <UBadge
                                v-if="
                                    tab.value === 'roles' &&
                                    rolesByType.entityLocal.length > 0
                                "
                                :label="String(rolesByType.entityLocal.length)"
                                size="xs"
                                color="neutral"
                                variant="subtle"
                            />
                        </button>
                    </div>
                </div>

                <!-- Children Table -->
                <UTable
                    v-if="!selectedEntity || activeTab === 'children'"
                    sticky
                    class="flex-1"
                    :columns="columns"
                    :data="childEntities"
                    :loading="isLoading"
                >
                    <template #empty>
                        <div
                            class="flex flex-col items-center justify-center py-12 gap-4"
                        >
                            <UIcon
                                :name="
                                    selectedEntity
                                        ? 'i-lucide-folder-open'
                                        : 'i-lucide-building'
                                "
                                class="w-12 h-12 text-muted"
                            />
                            <p class="text-muted">
                                {{
                                    selectedEntity
                                        ? "No child entities"
                                        : "No entities yet"
                                }}
                            </p>
                            <UButton
                                icon="i-lucide-plus"
                                :label="
                                    selectedEntity
                                        ? 'Create child entity'
                                        : 'Create your first entity'
                                "
                                variant="outline"
                                @click="showCreateModal = true"
                            />
                        </div>
                    </template>
                </UTable>

                <!-- Members Table -->
                <UTable
                    v-else-if="activeTab === 'members'"
                    sticky
                    class="flex-1"
                    :columns="memberColumns"
                    :data="entityMembers"
                    :loading="isMembersLoading"
                >
                    <template #empty>
                        <div
                            class="flex flex-col items-center justify-center py-12 gap-4"
                        >
                            <UIcon
                                name="i-lucide-users"
                                class="w-12 h-12 text-muted"
                            />
                            <p class="text-muted">No members yet</p>
                            <UButton
                                icon="i-lucide-user-plus"
                                label="Add first member"
                                variant="outline"
                                @click="showAddMemberModal = true"
                            />
                        </div>
                    </template>
                </UTable>

                <!-- Roles Tab Content -->
                <div
                    v-else-if="activeTab === 'roles'"
                    class="flex-1 overflow-y-auto p-4 space-y-6"
                >
                    <!-- Loading State -->
                    <div
                        v-if="isRolesLoading"
                        class="flex items-center justify-center py-12"
                    >
                        <UIcon
                            name="i-lucide-loader-2"
                            class="w-8 h-8 animate-spin text-primary"
                        />
                    </div>

                    <template v-else>
                        <!-- Entity-Local Roles -->
                        <div>
                            <div class="flex items-center justify-between mb-3">
                                <h4
                                    class="text-sm font-semibold flex items-center gap-2"
                                >
                                    <UIcon
                                        name="i-lucide-map-pin"
                                        class="w-4 h-4"
                                    />
                                    Roles at
                                    {{
                                        selectedEntity?.display_name ||
                                        selectedEntity?.name
                                    }}
                                </h4>
                                <UButton
                                    icon="i-lucide-plus"
                                    label="Add Role"
                                    size="xs"
                                    variant="outline"
                                    @click="showCreateEntityRoleModal = true"
                                />
                            </div>
                            <div
                                v-if="rolesByType.entityLocal.length > 0"
                                class="space-y-2"
                            >
                                <div
                                    v-for="role in rolesByType.entityLocal"
                                    :key="role.id"
                                    class="flex items-center justify-between p-3 rounded-lg border border-default bg-default/50"
                                >
                                    <div class="flex items-center gap-3">
                                        <div
                                            class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center"
                                        >
                                            <UIcon
                                                name="i-lucide-shield"
                                                class="w-4 h-4 text-primary"
                                            />
                                        </div>
                                        <div>
                                            <p class="font-medium text-sm">
                                                {{
                                                    role.display_name ||
                                                    role.name
                                                }}
                                            </p>
                                            <p
                                                v-if="role.description"
                                                class="text-xs text-muted"
                                            >
                                                {{ role.description }}
                                            </p>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <UBadge
                                            v-if="role.is_auto_assigned"
                                            color="primary"
                                            variant="subtle"
                                            size="xs"
                                        >
                                            Auto-assigned
                                        </UBadge>
                                        <UBadge
                                            :color="
                                                getRoleScopeBadge(role).color
                                            "
                                            variant="subtle"
                                            size="xs"
                                        >
                                            {{ getRoleScopeBadge(role).label }}
                                        </UBadge>
                                        <UBadge
                                            color="neutral"
                                            variant="subtle"
                                            size="xs"
                                        >
                                            {{ role.permissions?.length || 0 }}
                                            perms
                                        </UBadge>
                                        <UButton
                                            icon="i-lucide-pencil"
                                            color="neutral"
                                            variant="ghost"
                                            size="xs"
                                            @click="openEditRoleModal(role.id)"
                                        />
                                        <UButton
                                            icon="i-lucide-trash-2"
                                            color="error"
                                            variant="ghost"
                                            size="xs"
                                            @click="
                                                () => requestDeleteRole(role)
                                            "
                                        />
                                    </div>
                                </div>
                            </div>
                            <div
                                v-else
                                class="text-center py-8 border border-dashed border-default rounded-lg"
                            >
                                <UIcon
                                    name="i-lucide-shield-off"
                                    class="w-8 h-8 text-muted mx-auto mb-2"
                                />
                                <p class="text-sm text-muted">
                                    No roles defined at this entity
                                </p>
                                <UButton
                                    icon="i-lucide-plus"
                                    label="Create first role"
                                    size="xs"
                                    variant="link"
                                    class="mt-2"
                                    @click="showCreateEntityRoleModal = true"
                                />
                            </div>
                        </div>

                        <!-- Inherited Roles -->
                        <div v-if="rolesByType.inherited.length > 0">
                            <h4
                                class="text-sm font-semibold flex items-center gap-2 mb-3"
                            >
                                <UIcon
                                    name="i-lucide-git-branch"
                                    class="w-4 h-4"
                                />
                                Inherited Roles
                                <UTooltip
                                    text="Roles from parent entities with hierarchy scope"
                                >
                                    <UIcon
                                        name="i-lucide-info"
                                        class="w-3.5 h-3.5 text-muted"
                                    />
                                </UTooltip>
                            </h4>
                            <div class="space-y-2">
                                <div
                                    v-for="role in rolesByType.inherited"
                                    :key="role.id"
                                    class="flex items-center justify-between p-3 rounded-lg border border-default bg-muted/20"
                                >
                                    <div class="flex items-center gap-3">
                                        <div
                                            class="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center"
                                        >
                                            <UIcon
                                                name="i-lucide-shield"
                                                class="w-4 h-4 text-success"
                                            />
                                        </div>
                                        <div>
                                            <p class="font-medium text-sm">
                                                {{
                                                    role.display_name ||
                                                    role.name
                                                }}
                                            </p>
                                            <p class="text-xs text-muted">
                                                from
                                                {{
                                                    role.scope_entity_name ||
                                                    "parent entity"
                                                }}
                                            </p>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <UBadge
                                            color="success"
                                            variant="subtle"
                                            size="xs"
                                        >
                                            Hierarchy
                                        </UBadge>
                                        <UBadge
                                            color="neutral"
                                            variant="subtle"
                                            size="xs"
                                        >
                                            {{ role.permissions?.length || 0 }}
                                            perms
                                        </UBadge>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Global Roles -->
                        <div v-if="rolesByType.global.length > 0">
                            <h4
                                class="text-sm font-semibold flex items-center gap-2 mb-3"
                            >
                                <UIcon name="i-lucide-globe" class="w-4 h-4" />
                                Global Roles
                            </h4>
                            <div class="space-y-2">
                                <div
                                    v-for="role in rolesByType.global"
                                    :key="role.id"
                                    class="flex items-center justify-between p-3 rounded-lg border border-default bg-muted/20"
                                >
                                    <div class="flex items-center gap-3">
                                        <div
                                            class="w-8 h-8 rounded-lg bg-info/10 flex items-center justify-center"
                                        >
                                            <UIcon
                                                name="i-lucide-shield"
                                                class="w-4 h-4 text-info"
                                            />
                                        </div>
                                        <div>
                                            <p class="font-medium text-sm">
                                                {{
                                                    role.display_name ||
                                                    role.name
                                                }}
                                            </p>
                                            <p
                                                v-if="role.description"
                                                class="text-xs text-muted"
                                            >
                                                {{ role.description }}
                                            </p>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <UBadge
                                            color="info"
                                            variant="subtle"
                                            size="xs"
                                        >
                                            Global
                                        </UBadge>
                                        <UBadge
                                            color="neutral"
                                            variant="subtle"
                                            size="xs"
                                        >
                                            {{ role.permissions?.length || 0 }}
                                            perms
                                        </UBadge>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Empty State (no roles at all) -->
                        <div
                            v-if="entityRoles.length === 0"
                            class="flex flex-col items-center justify-center py-12 gap-4"
                        >
                            <UIcon
                                name="i-lucide-shield-off"
                                class="w-12 h-12 text-muted"
                            />
                            <p class="text-muted">
                                No roles available for this entity
                            </p>
                            <UButton
                                icon="i-lucide-plus"
                                label="Create first role"
                                variant="outline"
                                @click="showCreateEntityRoleModal = true"
                            />
                        </div>
                    </template>
                </div>
            </div>
        </UDashboardPanel>
    </div>

    <!-- Create Entity Modal -->
    <EntityCreateModal
        v-model:open="showCreateModal"
        :parent-entity-id="createParentId"
    />

    <!-- Edit Entity Modal -->
    <EntityUpdateModal
        v-if="editEntityId"
        v-model:open="showEditModal"
        :entity-id="editEntityId"
    />

    <!-- Add Member Modal -->
    <EntityMemberAddModal
        v-if="selectedTreeEntityId"
        v-model:open="showAddMemberModal"
        :entity-id="selectedTreeEntityId"
    />

    <!-- Edit Member Roles Modal -->
    <MemberRoleEditModal
        v-if="selectedTreeEntityId && editingMember"
        v-model:open="showEditMemberRolesModal"
        :entity-id="selectedTreeEntityId"
        :member="editingMember"
    />

    <!-- Create Entity Role Modal -->
    <EntityRoleCreateModal
        v-if="selectedTreeEntityId"
        v-model:open="showCreateEntityRoleModal"
        :entity-id="selectedTreeEntityId"
        :entity-name="
            selectedEntity?.display_name || selectedEntity?.name || ''
        "
    />

    <!-- Edit Role Modal (reuse existing) -->
    <RoleUpdateModal
        v-if="editRoleId"
        v-model:open="showEditRoleModal"
        :role-id="editRoleId"
    />

    <ConfirmActionModal
        v-model:open="showActionConfirm"
        :title="actionConfirmMeta.title"
        :description="actionConfirmMeta.description"
        :confirm-label="actionConfirmMeta.confirmLabel"
        :confirm-color="actionConfirmMeta.confirmColor"
        :loading="isConfirmingAction"
        @confirm="confirmPendingAction"
        @cancel="resetActionConfirm"
    />
</template>
