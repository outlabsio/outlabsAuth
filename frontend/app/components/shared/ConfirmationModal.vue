<template>
  <UModal v-model="isOpen">
    <UCard>
      <template #header>
        <div class="flex items-center gap-3">
          <div :class="iconWrapperClass">
            <UIcon :name="icon" :class="iconClass" />
          </div>
          <h3 class="text-lg font-semibold">{{ title }}</h3>
        </div>
      </template>

      <div class="space-y-4">
        <p class="text-sm text-muted-foreground">{{ description }}</p>
        
        <div v-if="$slots.default" class="pt-2">
          <slot />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <UButton 
            variant="outline" 
            @click="handleCancel"
          >
            {{ cancelText }}
          </UButton>
          <UButton 
            :color="confirmColor"
            :loading="isLoading"
            @click="handleConfirm"
          >
            {{ confirmText }}
          </UButton>
        </div>
      </template>
    </UCard>
  </UModal>
</template>

<script setup lang="ts">
interface Props {
  modelValue: boolean
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  confirmColor?: 'primary' | 'error' | 'warning' | 'success' | 'info'
  icon?: string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  confirmText: 'Confirm',
  cancelText: 'Cancel',
  confirmColor: 'primary',
  icon: 'i-lucide-alert-triangle',
  loading: false
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'confirm': []
  'cancel': []
}>()

// Model binding
const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Computed
const isLoading = computed(() => props.loading)

const iconWrapperClass = computed(() => {
  const baseClass = 'p-2 rounded-lg'
  const colorClasses = {
    primary: 'bg-primary/10',
    error: 'bg-error/10',
    warning: 'bg-warning/10',
    success: 'bg-success/10',
    info: 'bg-info/10'
  }
  return `${baseClass} ${colorClasses[props.confirmColor]}`
})

const iconClass = computed(() => {
  const colorClasses = {
    primary: 'text-primary',
    error: 'text-error',
    warning: 'text-warning',
    success: 'text-success',
    info: 'text-info'
  }
  return `h-5 w-5 ${colorClasses[props.confirmColor]}`
})

// Methods
const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  emit('cancel')
  isOpen.value = false
}
</script>