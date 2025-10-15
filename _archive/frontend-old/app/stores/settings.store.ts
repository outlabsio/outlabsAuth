export const useSettingsStore = defineStore('settings', () => {
  // State
  const state = reactive({
    // General Settings
    general: {
      platform_name: 'OutlabsAuth',
      platform_description: '',
      default_language: 'en',
      timezone: 'UTC'
    },
    
    // Security Settings
    security: {
      min_password_length: 8,
      require_uppercase: true,
      require_lowercase: true,
      require_digits: true,
      require_special_chars: true,
      access_token_minutes: 15,
      refresh_token_days: 30,
      max_login_attempts: 5
    },
    
    // Notification Settings
    notifications: {
      email: {
        enabled: false,
        smtp_host: '',
        smtp_port: 587,
        smtp_username: '',
        smtp_password: '',
        smtp_from_email: '',
        smtp_from_name: ''
      },
      // Future: slack, webhook, etc.
    },
    
    // Rate Limiting Settings
    rateLimiting: {
      enabled: true,
      window_minutes: 15,
      max_requests: 100,
      max_login_attempts: 5,
      block_duration_minutes: 30
    },
    
    // Loading states
    isLoading: false,
    isSaving: false,
    loadError: null as string | null
  })

  // Dependencies
  const authStore = useAuthStore()
  const toast = useToast()

  // Actions
  const fetchSettings = async () => {
    state.isLoading = true
    state.loadError = null
    
    try {
      // In a real implementation, this would fetch from API
      const response = await authStore.apiCall<any>('/v1/settings')
      
      // Update state with fetched settings
      if (response.general) state.general = response.general
      if (response.security) state.security = response.security
      if (response.notifications) state.notifications = response.notifications
      if (response.rateLimiting) state.rateLimiting = response.rateLimiting
      
    } catch (error: any) {
      state.loadError = error.message || 'Failed to load settings'
      console.error('Failed to fetch settings:', error)
    } finally {
      state.isLoading = false
    }
  }

  const saveGeneralSettings = async (settings: typeof state.general) => {
    state.isSaving = true
    try {
      await authStore.apiCall('/v1/settings/general', {
        method: 'PUT',
        body: settings
      })
      
      state.general = settings
      
      toast.add({
        title: 'Settings saved',
        description: 'General settings have been updated',
        color: 'success'
      })
    } catch (error: any) {
      toast.add({
        title: 'Failed to save settings',
        description: error.message || 'An error occurred',
        color: 'error'
      })
      throw error
    } finally {
      state.isSaving = false
    }
  }

  const saveSecuritySettings = async (settings: typeof state.security) => {
    state.isSaving = true
    try {
      await authStore.apiCall('/v1/settings/security', {
        method: 'PUT',
        body: settings
      })
      
      state.security = settings
      
      toast.add({
        title: 'Settings saved',
        description: 'Security settings have been updated',
        color: 'success'
      })
    } catch (error: any) {
      toast.add({
        title: 'Failed to save settings',
        description: error.message || 'An error occurred',
        color: 'error'
      })
      throw error
    } finally {
      state.isSaving = false
    }
  }

  const saveNotificationSettings = async (settings: typeof state.notifications) => {
    state.isSaving = true
    try {
      await authStore.apiCall('/v1/settings/notifications', {
        method: 'PUT',
        body: settings
      })
      
      state.notifications = settings
      
      toast.add({
        title: 'Settings saved',
        description: 'Notification settings have been updated',
        color: 'success'
      })
    } catch (error: any) {
      toast.add({
        title: 'Failed to save settings',
        description: error.message || 'An error occurred',
        color: 'error'
      })
      throw error
    } finally {
      state.isSaving = false
    }
  }

  const saveRateLimitingSettings = async (settings: typeof state.rateLimiting) => {
    state.isSaving = true
    try {
      await authStore.apiCall('/v1/settings/rate-limiting', {
        method: 'PUT',
        body: settings
      })
      
      state.rateLimiting = settings
      
      toast.add({
        title: 'Settings saved',
        description: 'Rate limiting settings have been updated',
        color: 'success'
      })
    } catch (error: any) {
      toast.add({
        title: 'Failed to save settings',
        description: error.message || 'An error occurred',
        color: 'error'
      })
      throw error
    } finally {
      state.isSaving = false
    }
  }

  const testEmailConnection = async () => {
    try {
      await authStore.apiCall('/v1/settings/notifications/test-email', {
        method: 'POST',
        body: state.notifications.email
      })
      
      toast.add({
        title: 'Test successful',
        description: 'Email connection is working correctly',
        color: 'success'
      })
      
      return true
    } catch (error: any) {
      toast.add({
        title: 'Test failed',
        description: error.message || 'Could not connect to email server',
        color: 'error'
      })
      return false
    }
  }

  // Computed
  const isEmailConfigured = computed(() => {
    const email = state.notifications.email
    return email.enabled && 
           email.smtp_host && 
           email.smtp_port && 
           email.smtp_username && 
           email.smtp_from_email
  })

  const isRateLimitingActive = computed(() => {
    return state.rateLimiting.enabled
  })

  const passwordPolicyDescription = computed(() => {
    const policy = state.security
    const requirements = []
    
    requirements.push(`At least ${policy.min_password_length} characters`)
    if (policy.require_uppercase) requirements.push('One uppercase letter')
    if (policy.require_lowercase) requirements.push('One lowercase letter')
    if (policy.require_digits) requirements.push('One number')
    if (policy.require_special_chars) requirements.push('One special character')
    
    return requirements.join(', ')
  })

  return {
    // State
    general: computed(() => state.general),
    security: computed(() => state.security),
    notifications: computed(() => state.notifications),
    rateLimiting: computed(() => state.rateLimiting),
    isLoading: computed(() => state.isLoading),
    isSaving: computed(() => state.isSaving),
    loadError: computed(() => state.loadError),
    
    // Computed
    isEmailConfigured,
    isRateLimitingActive,
    passwordPolicyDescription,
    
    // Actions
    fetchSettings,
    saveGeneralSettings,
    saveSecuritySettings,
    saveNotificationSettings,
    saveRateLimitingSettings,
    testEmailConnection
  }
})