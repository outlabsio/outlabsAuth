<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold">Account Settings</h1>
      <p class="text-muted-foreground mt-1">
        Manage your account settings and preferences
      </p>
    </div>

    <!-- Settings Navigation -->
    <UTabs v-model="activeTab" :items="tabItems" class="w-full">
      <!-- Profile Tab -->
      <template #profile>
        <ProfileSettings />
      </template>

      <!-- Security Tab -->
      <template #security>
        <SecuritySettings />
      </template>

      <!-- Notifications Tab -->
      <template #notifications>
        <NotificationSettings />
      </template>

      <!-- Sessions Tab -->
      <template #sessions>
        <SessionSettings />
      </template>
    </UTabs>
  </div>
</template>

<script setup lang="ts">
// State
const activeTab = ref('profile')

// Tab configuration
const tabItems = [
  { slot: 'profile', label: 'Profile', icon: 'i-lucide-user' },
  { slot: 'security', label: 'Security', icon: 'i-lucide-shield' },
  { slot: 'notifications', label: 'Notifications', icon: 'i-lucide-bell' },
  { slot: 'sessions', label: 'Sessions', icon: 'i-lucide-monitor' }
]

// SEO
useHead({
  title: 'Account Settings',
  meta: [
    {
      name: 'description',
      content: 'Manage your account settings and preferences'
    }
  ]
})
</script>