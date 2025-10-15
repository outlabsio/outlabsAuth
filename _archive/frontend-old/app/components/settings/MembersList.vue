<script setup lang="ts">
import type { Member } from "~/types";

// Extend the Member type to include needed properties
interface MemberWithAdminProps extends Member {
  id: string;
  is_superuser?: boolean;
  is_active?: boolean;
}

// Define dropdown menu item types with correct color values
type DropdownMenuItemColor = "error" | "primary" | "secondary" | "success" | "info" | "warning" | "neutral";

type DropdownMenuItem = { label: string; icon?: string; color?: DropdownMenuItemColor; onSelect: () => void } | { type: "separator" };

defineProps<{
  members: MemberWithAdminProps[];
}>();

const emit = defineEmits(["edit", "delete", "toggleActive", "managePermissions", "toggleTeamMember"]);

// Update items to use the emit events with dynamic options based on active status
const getItems = (member: MemberWithAdminProps): DropdownMenuItem[] => {
  const items: DropdownMenuItem[] = [
    {
      label: "Edit member",
      icon: "i-lucide-edit",
      onSelect: () => emit("edit", member),
    },
    {
      label: "Manage permissions",
      icon: "i-lucide-key",
      onSelect: () => emit("managePermissions", member),
    },
  ];

  // Add suspend/unsuspend option based on current active status
  if (member.is_active) {
    items.push({
      label: "Suspend user",
      icon: "i-lucide-user-x",
      color: "warning",
      onSelect: () => emit("toggleActive", { id: member.id, active: false }),
    });
  } else {
    items.push({
      label: "Activate user",
      icon: "i-lucide-user-check",
      color: "success",
      onSelect: () => emit("toggleActive", { id: member.id, active: true }),
    });
  }

  // Add remove from team option before delete
  items.push(
    {
      label: "Remove from team",
      icon: "i-lucide-user-minus",
      color: "warning",
      onSelect: () => emit("toggleTeamMember", { id: member.id, isTeamMember: false }),
    },
    {
      type: "separator",
    },
    {
      label: "Remove member",
      icon: "i-lucide-trash",
      color: "error",
      onSelect: () => emit("delete", member.id),
    }
  );

  return items;
};
</script>

<template>
  <ul role="list" class="divide-y divide-(--ui-border)">
    <li v-for="(member, index) in members" :key="index" class="flex items-center justify-between gap-3 py-3 px-4 sm:px-6">
      <div class="flex items-center gap-3 min-w-0">
        <UAvatar v-bind="member.avatar" size="md" />

        <div class="text-sm min-w-0">
          <div class="flex items-center">
            <p class="text-(--ui-text-highlighted) font-medium truncate">
              {{ member.name }}
            </p>
            <UBadge v-if="member.is_superuser" color="success" class="ml-2" size="xs">
              <template #leading>
                <UIcon name="i-lucide-shield-check" class="h-3 w-3" />
              </template>
              Admin
            </UBadge>
          </div>
          <p class="text-(--ui-text-muted) truncate">
            {{ member.username }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <UBadge :color="member.is_active ? 'success' : 'neutral'" variant="subtle" size="sm">
          <template #leading>
            <UIcon :name="member.is_active ? 'i-lucide-check-circle' : 'i-lucide-circle'" class="h-3 w-3" />
          </template>
          {{ member.is_active ? "Active" : "Inactive" }}
        </UBadge>

        <UDropdownMenu :items="getItems(member)" :content="{ align: 'end' }">
          <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" />
        </UDropdownMenu>
      </div>
    </li>
  </ul>
</template>
