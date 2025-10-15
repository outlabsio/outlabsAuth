<template>
  <UCard class="mt-4">
    <template #header>
      <h3 class="text-lg font-semibold">Notification Preferences</h3>
      <p class="text-sm text-muted-foreground mt-1">
        Control how and when you receive notifications
      </p>
    </template>

    <div class="space-y-6">
      <!-- Email Notifications -->
      <div class="space-y-4">
        <h4 class="font-medium">Email Notifications</h4>
        
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div>
              <p class="font-medium text-sm">Security Alerts</p>
              <p class="text-xs text-muted-foreground">
                Receive alerts about security events like new logins or password changes
              </p>
            </div>
            <USwitch v-model="settings.email.security_alerts" />
          </div>

          <USeparator />

          <div class="flex items-center justify-between">
            <div>
              <p class="font-medium text-sm">Entity Updates</p>
              <p class="text-xs text-muted-foreground">
                Get notified when you're added to or removed from entities
              </p>
            </div>
            <USwitch v-model="settings.email.entity_updates" />
          </div>

          <USeparator />

          <div class="flex items-center justify-between">
            <div>
              <p class="font-medium text-sm">Role Changes</p>
              <p class="text-xs text-muted-foreground">
                Receive notifications when your roles or permissions change
              </p>
            </div>
            <USwitch v-model="settings.email.role_changes" />
          </div>

          <USeparator />

          <div class="flex items-center justify-between">
            <div>
              <p class="font-medium text-sm">System Announcements</p>
              <p class="text-xs text-muted-foreground">
                Important updates about the platform and new features
              </p>
            </div>
            <USwitch v-model="settings.email.system_announcements" />
          </div>
        </div>
      </div>

      <USeparator />

      <!-- In-App Notifications -->
      <div class="space-y-4">
        <h4 class="font-medium">In-App Notifications</h4>
        
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div>
              <p class="font-medium text-sm">Real-time Updates</p>
              <p class="text-xs text-muted-foreground">
                Show notifications in the app when events occur
              </p>
            </div>
            <USwitch v-model="settings.inApp.enabled" />
          </div>

          <template v-if="settings.inApp.enabled">
            <USeparator />

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-sm">Desktop Notifications</p>
                <p class="text-xs text-muted-foreground">
                  Show browser notifications when the app is in the background
                </p>
              </div>
              <USwitch v-model="settings.inApp.desktop_notifications" />
            </div>

            <USeparator />

            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-sm">Sound Alerts</p>
                <p class="text-xs text-muted-foreground">
                  Play a sound when you receive a notification
                </p>
              </div>
              <USwitch v-model="settings.inApp.sound_alerts" />
            </div>
          </template>
        </div>
      </div>

      <USeparator />

      <!-- Notification Schedule -->
      <div class="space-y-4">
        <h4 class="font-medium">Notification Schedule</h4>
        
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div>
              <p class="font-medium text-sm">Do Not Disturb</p>
              <p class="text-xs text-muted-foreground">
                Pause all notifications during specific hours
              </p>
            </div>
            <USwitch v-model="settings.schedule.dnd_enabled" />
          </div>

          <template v-if="settings.schedule.dnd_enabled">
            <div class="grid grid-cols-2 gap-4 pl-4">
              <UFormField label="Start Time">
                <UInput 
                  v-model="settings.schedule.dnd_start" 
                  type="time"
                />
              </UFormField>
              
              <UFormField label="End Time">
                <UInput 
                  v-model="settings.schedule.dnd_end" 
                  type="time"
                />
              </UFormField>
            </div>

            <div class="pl-4">
              <p class="text-sm font-medium mb-2">Days</p>
              <div class="flex flex-wrap gap-2">
                <UCheckbox 
                  v-for="day in weekDays" 
                  :key="day.value"
                  v-model="settings.schedule.dnd_days"
                  :value="day.value"
                  :label="day.label"
                />
              </div>
            </div>
          </template>
        </div>
      </div>

      <USeparator />

      <!-- Save Button -->
      <div class="flex justify-end pt-4">
        <UButton 
          @click="saveSettings"
          :loading="isSaving"
        >
          Save Preferences
        </UButton>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
// Stores
const authStore = useAuthStore()
const toast = useToast()

// State
const isSaving = ref(false)

// Notification settings
const settings = reactive({
  email: {
    security_alerts: true,
    entity_updates: true,
    role_changes: true,
    system_announcements: false
  },
  inApp: {
    enabled: true,
    desktop_notifications: false,
    sound_alerts: true
  },
  schedule: {
    dnd_enabled: false,
    dnd_start: '22:00',
    dnd_end: '08:00',
    dnd_days: ['mon', 'tue', 'wed', 'thu', 'fri']
  }
})

// Week days
const weekDays = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' }
]

// Methods
const saveSettings = async () => {
  isSaving.value = true

  try {
    // In a real implementation, this would save to an API endpoint
    await new Promise(resolve => setTimeout(resolve, 1000))

    toast.add({
      title: 'Preferences saved',
      description: 'Your notification preferences have been updated',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Failed to save preferences',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSaving.value = false
  }
}

// Request permission for desktop notifications
const requestNotificationPermission = async () => {
  if ('Notification' in window && settings.inApp.desktop_notifications) {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') {
      settings.inApp.desktop_notifications = false
      toast.add({
        title: 'Permission denied',
        description: 'Desktop notifications require browser permission',
        color: 'warning'
      })
    }
  }
}

// Watch for desktop notification toggle
watch(() => settings.inApp.desktop_notifications, (enabled) => {
  if (enabled) {
    requestNotificationPermission()
  }
})
</script>