<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui";
import { useQuery } from "@pinia/colada";
import {
    apiKeysQueries,
    useRevokeApiKeyMutation,
    useSuspendApiKeyMutation,
    useResumeApiKeyMutation,
} from "~/queries/api-keys";
import type { ApiKey } from "~/types/api-key";

// Resolve components for h() render functions
const UBadge = resolveComponent("UBadge");
const UButton = resolveComponent("UButton");

const search = ref("");
const statusFilter = ref<
    "all" | "active" | "revoked" | "expired" | "suspended"
>("all");
const showCreateModal = ref(false);
const showDetailModal = ref(false);
const showEditModal = ref(false);
const selectedKeyId = ref<string | null>(null);
const showKeyActionConfirm = ref(false);
const pendingKeyAction = ref<"revoke" | "suspend" | null>(null);
const pendingKey = ref<ApiKey | null>(null);
const isConfirmingKeyAction = ref(false);

// Fetch API keys from backend
const { data: apiKeys, isLoading, error } = useQuery(apiKeysQueries.list());
const apiKeysErrorMessage = computed(() => {
    if (!error.value) {
        return "";
    }
    return error.value instanceof Error ? error.value.message : String(error.value);
});

// Mutations
const revokeMutation = useRevokeApiKeyMutation();
const suspendMutation = useSuspendApiKeyMutation();
const resumeMutation = useResumeApiKeyMutation();

const keyActionConfirmMeta = computed(() => {
    const label = pendingKey.value
        ? `'${pendingKey.value.name}' (${pendingKey.value.prefix})`
        : "this API key";

    if (pendingKeyAction.value === "revoke") {
        return {
            title: "Revoke API key?",
            description: `This permanently revokes ${label}. This action cannot be undone.`,
            confirmLabel: "Revoke key",
            confirmColor: "error",
        };
    }

    return {
        title: "Suspend API key?",
        description: `${label} will be temporarily disabled and can be resumed later.`,
        confirmLabel: "Suspend key",
        confirmColor: "warning",
    };
});

function requestKeyAction(action: "revoke" | "suspend", key: ApiKey) {
    pendingKeyAction.value = action;
    pendingKey.value = key;
    showKeyActionConfirm.value = true;
}

function resetKeyActionState() {
    if (isConfirmingKeyAction.value) {
        return;
    }
    showKeyActionConfirm.value = false;
    pendingKeyAction.value = null;
    pendingKey.value = null;
}

async function confirmKeyAction() {
    if (!pendingKeyAction.value || !pendingKey.value) {
        return;
    }

    isConfirmingKeyAction.value = true;
    try {
        if (pendingKeyAction.value === "revoke") {
            await revokeMutation.mutateAsync(pendingKey.value.id);
        } else {
            await suspendMutation.mutateAsync(pendingKey.value.id);
        }

        showKeyActionConfirm.value = false;
        pendingKeyAction.value = null;
        pendingKey.value = null;
    } finally {
        isConfirmingKeyAction.value = false;
    }
}

watch(showKeyActionConfirm, (isOpen) => {
    if (!isOpen && !isConfirmingKeyAction.value) {
        pendingKeyAction.value = null;
        pendingKey.value = null;
    }
});

// Handle resume action
const handleResume = async (key: ApiKey) => {
    await resumeMutation.mutateAsync(key.id);
};

// Table columns
const columns: TableColumn<ApiKey>[] = [
    {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) =>
            h("div", { class: "flex flex-col gap-1" }, [
                h("p", { class: "font-medium" }, row.original.name),
                h("code", { class: "text-xs text-muted" }, row.original.prefix),
            ]),
    },
    {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => {
            const colors: Record<string, string> = {
                active: "success",
                suspended: "warning",
                revoked: "error",
                expired: "neutral",
            };
            return h(
                UBadge,
                {
                    color: colors[row.original.status] || "neutral",
                    variant: "subtle",
                },
                () => row.original.status.toUpperCase(),
            );
        },
    },
    {
        accessorKey: "scopes",
        header: "Scopes",
        cell: ({ row }) => {
            const scopes = row.original.scopes || [];
            if (scopes.length === 0) {
                return h(
                    UBadge,
                    { color: "neutral", variant: "subtle", size: "xs" },
                    () => "No permissions",
                );
            }
            if (scopes.includes("*:*")) {
                return h(
                    UBadge,
                    { color: "warning", variant: "subtle" },
                    () => "All Permissions",
                );
            }
            return h(
                "div",
                { class: "flex flex-wrap gap-1" },
                scopes
                    .slice(0, 2)
                    .map((scope) =>
                        h(
                            UBadge,
                            { color: "neutral", variant: "subtle", size: "xs" },
                            () => scope,
                        ),
                    )
                    .concat(
                        scopes.length > 2
                            ? [
                                  h(
                                      UBadge,
                                      {
                                          color: "neutral",
                                          variant: "subtle",
                                          size: "xs",
                                      },
                                      () => `+${scopes.length - 2}`,
                                  ),
                              ]
                            : [],
                    ),
            );
        },
    },
    {
        accessorKey: "last_used_at",
        header: "Last Used",
        cell: ({ row }) => {
            if (!row.original.last_used_at)
                return h("span", { class: "text-sm text-muted" }, "Never");
            const date = new Date(row.original.last_used_at);
            const now = new Date();
            const diffHours = Math.floor(
                (now.getTime() - date.getTime()) / (1000 * 60 * 60),
            );

            if (diffHours < 1)
                return h(
                    "span",
                    { class: "text-sm text-success" },
                    "Just now",
                );
            if (diffHours < 24)
                return h("span", { class: "text-sm" }, `${diffHours}h ago`);
            return h(
                "span",
                { class: "text-sm text-muted" },
                date.toLocaleDateString(),
            );
        },
    },
    {
        accessorKey: "expires_at",
        header: "Expires",
        cell: ({ row }) => {
            if (!row.original.expires_at) {
                return h(
                    UBadge,
                    { color: "info", variant: "subtle" },
                    () => "Never",
                );
            }
            const date = new Date(row.original.expires_at);
            const now = new Date();
            const isExpired = date < now;
            const daysUntilExpiry = Math.ceil(
                (date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
            );

            if (isExpired) {
                return h("span", { class: "text-sm text-error" }, "Expired");
            }
            // Warn if expiring within 7 days
            if (daysUntilExpiry <= 7) {
                return h(
                    UBadge,
                    { color: "warning", variant: "subtle" },
                    () => `${daysUntilExpiry}d left`,
                );
            }
            return h(
                "span",
                { class: "text-sm text-muted" },
                date.toLocaleDateString(),
            );
        },
    },
    {
        id: "actions",
        header: "Actions",
        cell: ({ row }) => {
            const isActive = row.original.status === "active";
            const isSuspended = row.original.status === "suspended";
            const isRevoked = row.original.status === "revoked";

            return h(
                "div",
                { class: "flex items-center gap-1" },
                [
                    h(UButton, {
                        icon: "i-lucide-eye",
                        color: "neutral",
                        variant: "ghost",
                        size: "xs",
                        onClick: () => {
                            selectedKeyId.value = row.original.id;
                            showDetailModal.value = true;
                        },
                    }),
                    !isRevoked &&
                        h(UButton, {
                            icon: "i-lucide-pencil",
                            color: "neutral",
                            variant: "ghost",
                            size: "xs",
                            onClick: () => {
                                selectedKeyId.value = row.original.id;
                                showEditModal.value = true;
                            },
                        }),
                    isSuspended &&
                        h(UButton, {
                            icon: "i-lucide-play-circle",
                            color: "success",
                            variant: "ghost",
                            size: "xs",
                            loading:
                                resumeMutation.isPending &&
                                resumeMutation.variables === row.original.id,
                            onClick: () => handleResume(row.original),
                        }),
                    isActive &&
                        h(UButton, {
                            icon: "i-lucide-pause-circle",
                            color: "warning",
                            variant: "ghost",
                            size: "xs",
                            onClick: () =>
                                requestKeyAction("suspend", row.original),
                        }),
                    isActive &&
                        h(UButton, {
                            icon: "i-lucide-ban",
                            color: "error",
                            variant: "ghost",
                            size: "xs",
                            onClick: () =>
                                requestKeyAction("revoke", row.original),
                        }),
                ].filter(Boolean),
            );
        },
    },
];

// Filtered API keys
const filteredKeys = computed(() => {
    if (!apiKeys.value) return [];
    let result = apiKeys.value;

    // Apply status filter
    if (statusFilter.value !== "all") {
        result = result.filter((key) => key.status === statusFilter.value);
    }

    // Apply search filter
    if (search.value) {
        const searchLower = search.value.toLowerCase();
        result = result.filter(
            (key) =>
                key.name.toLowerCase().includes(searchLower) ||
                key.prefix.toLowerCase().includes(searchLower) ||
                (key.description &&
                    key.description.toLowerCase().includes(searchLower)),
        );
    }

    return result;
});

// Stats
const stats = computed(() => {
    if (!apiKeys.value)
        return { total: 0, active: 0, revoked: 0, expired: 0, suspended: 0 };

    const now = new Date();
    return {
        total: apiKeys.value.length,
        active: apiKeys.value.filter((k) => k.status === "active").length,
        suspended: apiKeys.value.filter((k) => k.status === "suspended").length,
        revoked: apiKeys.value.filter((k) => k.status === "revoked").length,
        expired: apiKeys.value.filter(
            (k) =>
                k.status === "expired" ||
                (k.expires_at && new Date(k.expires_at) < now),
        ).length,
    };
});
</script>

<template>
    <UDashboardPanel id="api-keys">
        <!-- Default slot for edge-to-edge table -->
        <div class="flex flex-col flex-1 min-h-0">
            <!-- Header -->
            <UDashboardNavbar title="API Keys">
                <template #leading>
                    <UDashboardSidebarCollapse />
                </template>

                <template #right>
                    <UButton
                        icon="i-lucide-plus"
                        label="Create API Key"
                        color="primary"
                        @click="showCreateModal = true"
                    />
                </template>
            </UDashboardNavbar>

            <!-- Stats Cards -->
            <div
                class="grid grid-cols-1 md:grid-cols-4 gap-4 px-4 py-4 border-b border-default"
            >
                <UCard>
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-sm text-muted">Total Keys</p>
                            <p class="text-2xl font-bold mt-1">
                                {{ stats.total }}
                            </p>
                        </div>
                        <UIcon
                            name="i-lucide-key"
                            class="w-8 h-8 text-primary"
                        />
                    </div>
                </UCard>

                <UCard>
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-sm text-muted">Active</p>
                            <p class="text-2xl font-bold mt-1 text-success">
                                {{ stats.active }}
                            </p>
                        </div>
                        <UIcon
                            name="i-lucide-check-circle"
                            class="w-8 h-8 text-success"
                        />
                    </div>
                </UCard>

                <UCard>
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-sm text-muted">Revoked</p>
                            <p class="text-2xl font-bold mt-1 text-error">
                                {{ stats.revoked }}
                            </p>
                        </div>
                        <UIcon
                            name="i-lucide-ban"
                            class="w-8 h-8 text-error"
                        />
                    </div>
                </UCard>

                <UCard>
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-sm text-muted">Expired</p>
                            <p class="text-2xl font-bold mt-1 text-neutral-600">
                                {{ stats.expired }}
                            </p>
                        </div>
                        <UIcon
                            name="i-lucide-clock"
                            class="w-8 h-8 text-neutral-500"
                        />
                    </div>
                </UCard>
            </div>

            <!-- Toolbar -->
            <div
                class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-default"
            >
                <div class="flex items-center gap-2">
                    <UInput
                        v-model="search"
                        icon="i-lucide-search"
                        placeholder="Search API keys..."
                        class="w-64"
                    />

                    <div class="flex items-center gap-1">
                        <UButton
                            :color="
                                statusFilter === 'all' ? 'primary' : 'neutral'
                            "
                            :variant="
                                statusFilter === 'all' ? 'solid' : 'ghost'
                            "
                            label="All"
                            @click="statusFilter = 'all'"
                        />
                        <UButton
                            :color="
                                statusFilter === 'active'
                                    ? 'primary'
                                    : 'neutral'
                            "
                            :variant="
                                statusFilter === 'active' ? 'solid' : 'ghost'
                            "
                            label="Active"
                            @click="statusFilter = 'active'"
                        />
                        <UButton
                            :color="
                                statusFilter === 'suspended'
                                    ? 'primary'
                                    : 'neutral'
                            "
                            :variant="
                                statusFilter === 'suspended' ? 'solid' : 'ghost'
                            "
                            label="Suspended"
                            @click="statusFilter = 'suspended'"
                        />
                        <UButton
                            :color="
                                statusFilter === 'revoked'
                                    ? 'primary'
                                    : 'neutral'
                            "
                            :variant="
                                statusFilter === 'revoked' ? 'solid' : 'ghost'
                            "
                            label="Revoked"
                            @click="statusFilter = 'revoked'"
                        />
                        <UButton
                            :color="
                                statusFilter === 'expired'
                                    ? 'primary'
                                    : 'neutral'
                            "
                            :variant="
                                statusFilter === 'expired' ? 'solid' : 'ghost'
                            "
                            label="Expired"
                            @click="statusFilter = 'expired'"
                        />
                    </div>
                </div>

                <UButton
                    icon="i-lucide-download"
                    color="neutral"
                    variant="ghost"
                    label="Export"
                />
            </div>

            <!-- Table -->
            <UAlert
                v-if="apiKeysErrorMessage"
                color="error"
                variant="subtle"
                icon="i-lucide-alert-circle"
                title="Unable to load API keys"
                :description="apiKeysErrorMessage"
                class="m-4"
            />

            <UTable
                sticky
                class="flex-1"
                :columns="columns"
                :data="filteredKeys"
                :loading="isLoading"
            >
                <template #empty>
                    <div
                        class="flex flex-col items-center justify-center py-12 gap-4"
                    >
                        <UIcon
                            name="i-lucide-key"
                            class="w-12 h-12 text-muted"
                        />
                        <p class="text-muted">No API keys found</p>
                        <UButton
                            icon="i-lucide-plus"
                            label="Create your first API key"
                            variant="outline"
                            @click="showCreateModal = true"
                        />
                    </div>
                </template>
            </UTable>
        </div>
    </UDashboardPanel>

    <!-- Create API Key Modal -->
    <ApiKeyCreateModal v-model:open="showCreateModal" />

    <!-- API Key Detail Modal -->
    <ApiKeyDetailModal
        v-if="selectedKeyId"
        v-model:open="showDetailModal"
        :key-id="selectedKeyId"
        @edit="
            () => {
                showDetailModal = false;
                showEditModal = true;
            }
        "
    />

    <!-- API Key Update/Edit Modal -->
    <ApiKeyUpdateModal
        v-if="selectedKeyId"
        v-model:open="showEditModal"
        :key-id="selectedKeyId"
    />

    <ConfirmActionModal
        v-model:open="showKeyActionConfirm"
        :title="keyActionConfirmMeta.title"
        :description="keyActionConfirmMeta.description"
        :confirm-label="keyActionConfirmMeta.confirmLabel"
        :confirm-color="keyActionConfirmMeta.confirmColor"
        :loading="isConfirmingKeyAction"
        @confirm="confirmKeyAction"
        @cancel="resetKeyActionState"
    />
</template>
