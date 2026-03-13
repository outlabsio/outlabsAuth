<script setup lang="ts">
import type { User } from "~/types/auth";

const props = defineProps<{
    user: User;
}>();

function formatDate(date: string | undefined) {
    if (!date) return "Never";
    return new Date(date).toLocaleString();
}

function formatDateRelative(date: string | undefined) {
    if (!date) return "Never";

    const now = new Date();
    const then = new Date(date);
    const diffMs = now.getTime() - then.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays <= 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
    return `${Math.floor(diffDays / 365)} years ago`;
}

function calculateAccountAge() {
    if (!props.user.created_at) return "Unknown";

    const now = new Date();
    const created = new Date(props.user.created_at);
    const diffMs = now.getTime() - created.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays < 1) return "Today";
    if (diffDays === 1) return "1 day";
    if (diffDays < 30) return `${diffDays} days`;
    if (diffDays < 365) {
        const months = Math.floor(diffDays / 30);
        return `${months} ${months === 1 ? "month" : "months"}`;
    }

    const years = Math.floor(diffDays / 365);
    return `${years} ${years === 1 ? "year" : "years"}`;
}

function statusColor(status: string | undefined) {
    switch (status) {
        case "active":
            return "success";
        case "suspended":
            return "warning";
        case "banned":
            return "error";
        default:
            return "neutral";
    }
}
</script>

<template>
    <div class="space-y-6">
        <UCard>
            <template #header>
                <div>
                    <h3 class="text-lg font-semibold text-foreground">
                        Account Activity
                    </h3>
                    <p class="text-sm text-muted">
                        Real account timestamps and lifecycle state from the auth backend.
                    </p>
                </div>
            </template>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="p-4 bg-muted/50 rounded-lg">
                    <div class="flex items-center gap-2 mb-2">
                        <UIcon name="i-lucide-log-in" class="w-5 h-5 text-primary" />
                        <p class="text-sm font-medium text-muted">Last Login</p>
                    </div>
                    <p class="text-xl font-bold text-foreground">
                        {{ formatDateRelative(user.last_login) }}
                    </p>
                    <p class="text-xs text-muted mt-1">
                        {{ formatDate(user.last_login) }}
                    </p>
                </div>

                <div class="p-4 bg-muted/50 rounded-lg">
                    <div class="flex items-center gap-2 mb-2">
                        <UIcon name="i-lucide-activity" class="w-5 h-5 text-primary" />
                        <p class="text-sm font-medium text-muted">Last Activity</p>
                    </div>
                    <p class="text-xl font-bold text-foreground">
                        {{ formatDateRelative(user.last_activity) }}
                    </p>
                    <p class="text-xs text-muted mt-1">
                        {{ formatDate(user.last_activity) }}
                    </p>
                </div>

                <div class="p-4 bg-muted/50 rounded-lg">
                    <div class="flex items-center gap-2 mb-2">
                        <UIcon name="i-lucide-calendar" class="w-5 h-5 text-primary" />
                        <p class="text-sm font-medium text-muted">Account Age</p>
                    </div>
                    <p class="text-xl font-bold text-foreground">
                        {{ calculateAccountAge() }}
                    </p>
                    <p class="text-xs text-muted mt-1">
                        Created {{ formatDate(user.created_at) }}
                    </p>
                </div>
            </div>
        </UCard>

        <UCard>
            <template #header>
                <div>
                    <h3 class="text-lg font-semibold text-foreground">
                        Security State
                    </h3>
                    <p class="text-sm text-muted">
                        Current security and lifecycle controls on this account.
                    </p>
                </div>
            </template>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="p-4 bg-muted/50 rounded-lg">
                    <p class="text-sm font-medium text-foreground">
                        Last Password Change
                    </p>
                    <p class="text-sm text-muted mt-1">
                        {{ formatDate(user.last_password_change) }}
                    </p>
                </div>

                <div class="p-4 bg-muted/50 rounded-lg">
                    <p class="text-sm font-medium text-foreground">
                        Account Lock
                    </p>
                    <p class="text-sm text-muted mt-1">
                        {{ user.locked_until ? formatDate(user.locked_until) : "Not locked" }}
                    </p>
                </div>

                <div class="p-4 bg-muted/50 rounded-lg">
                    <p class="text-sm font-medium text-foreground">
                        Suspension
                    </p>
                    <p class="text-sm text-muted mt-1">
                        {{
                            user.suspended_until
                                ? `Suspended until ${formatDate(user.suspended_until)}`
                                : "No suspension deadline"
                        }}
                    </p>
                </div>

                <div class="p-4 bg-muted/50 rounded-lg">
                    <p class="text-sm font-medium text-foreground">
                        Deletion Marker
                    </p>
                    <p class="text-sm text-muted mt-1">
                        {{ user.deleted_at ? formatDate(user.deleted_at) : "Not deleted" }}
                    </p>
                </div>
            </div>
        </UCard>

        <UCard>
            <template #header>
                <div>
                    <h3 class="text-lg font-semibold text-foreground">
                        Account Details
                    </h3>
                    <p class="text-sm text-muted">
                        Canonical user state returned by the auth backend.
                    </p>
                </div>
            </template>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        User ID
                    </p>
                    <code class="text-xs text-muted font-mono bg-muted px-2 py-1 rounded">
                        {{ user.id }}
                    </code>
                </div>

                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Email Status
                    </p>
                    <UBadge :color="user.email_verified ? 'success' : 'warning'" variant="subtle">
                        {{ user.email_verified ? "Verified" : "Unverified" }}
                    </UBadge>
                </div>

                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Account Status
                    </p>
                    <UBadge :color="statusColor(user.status)" variant="subtle">
                        {{ user.status }}
                    </UBadge>
                </div>

                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Superuser
                    </p>
                    <UBadge :color="user.is_superuser ? 'primary' : 'neutral'" variant="subtle">
                        {{ user.is_superuser ? "Yes" : "No" }}
                    </UBadge>
                </div>

                <div v-if="user.root_entity_name || user.root_entity_id">
                    <p class="text-sm font-medium text-foreground mb-1">
                        Organization
                    </p>
                    <p class="text-sm text-muted">
                        {{ user.root_entity_name || user.root_entity_id }}
                    </p>
                </div>

                <div>
                    <p class="text-sm font-medium text-foreground mb-1">
                        Last Updated
                    </p>
                    <p class="text-sm text-muted">
                        {{ formatDate(user.updated_at) }}
                    </p>
                </div>
            </div>
        </UCard>
    </div>
</template>
