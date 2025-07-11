<template>
  <div class="bg-white dark:bg-neutral-800 rounded-2xl p-6 shadow-lg border border-neutral-100 dark:border-neutral-700">
    <h3 class="text-lg font-semibold mb-6 flex items-center gap-2">
      <UIcon name="i-lucide-shield" class="w-5 h-5 text-green-500" />
      Security & Access
    </h3>

    <div class="space-y-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div class="flex items-center gap-3 p-3 bg-neutral-50 dark:bg-neutral-700/50 rounded-xl">
          <div class="w-8 h-8 rounded-full flex items-center justify-center" :class="user.is_verified ? 'bg-green-100 dark:bg-green-900/30' : 'bg-amber-100 dark:bg-amber-900/30'">
            <UIcon
              :name="user.is_verified ? 'i-lucide-shield-check' : 'i-lucide-shield-alert'"
              :class="user.is_verified ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'"
              class="w-4 h-4"
            />
          </div>
          <div>
            <div class="font-medium text-sm">Email Verification</div>
            <div class="text-xs text-neutral-500 dark:text-neutral-400">
              {{ user.is_verified ? "Verified" : "Unverified" }}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-3 p-3 bg-neutral-50 dark:bg-neutral-700/50 rounded-xl">
          <div class="w-8 h-8 rounded-full flex items-center justify-center" :class="user.is_superuser ? 'bg-purple-100 dark:bg-purple-900/30' : 'bg-neutral-100 dark:bg-neutral-600'">
            <UIcon name="i-lucide-crown" :class="user.is_superuser ? 'text-purple-600 dark:text-purple-400' : 'text-neutral-400'" class="w-4 h-4" />
          </div>
          <div>
            <div class="font-medium text-sm">Admin Access</div>
            <div class="text-xs text-neutral-500 dark:text-neutral-400">
              {{ user.is_superuser ? "Superuser" : "Regular User" }}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-3 p-3 bg-neutral-50 dark:bg-neutral-700/50 rounded-xl">
          <div class="w-8 h-8 rounded-full flex items-center justify-center" :class="user.is_team_member ? 'bg-blue-100 dark:bg-blue-900/30' : 'bg-neutral-100 dark:bg-neutral-600'">
            <UIcon name="i-lucide-users" :class="user.is_team_member ? 'text-blue-600 dark:text-blue-400' : 'text-neutral-400'" class="w-4 h-4" />
          </div>
          <div>
            <div class="font-medium text-sm">Team Member</div>
            <div class="text-xs text-neutral-500 dark:text-neutral-400">
              {{ user.is_team_member ? "Yes" : "No" }}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-3 p-3 bg-neutral-50 dark:bg-neutral-700/50 rounded-xl">
          <div class="w-8 h-8 rounded-full flex items-center justify-center bg-neutral-100 dark:bg-neutral-600">
            <UIcon name="i-lucide-key" class="w-4 h-4 text-neutral-400" />
          </div>
          <div>
            <div class="font-medium text-sm">Permissions</div>
            <div class="text-xs text-neutral-500 dark:text-neutral-400">{{ user.permissions?.length || 0 }} granted</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface User {
  is_verified: boolean;
  is_superuser: boolean;
  is_team_member: boolean;
  permissions: string[];
}

interface Props {
  user: User;
}

defineProps<Props>();
</script>
