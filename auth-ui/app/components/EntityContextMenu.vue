<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'

defineProps<{
  collapsed?: boolean
}>()

const contextStore = useContextStore()

const items = computed<DropdownMenuItem[][]>(() => {
  if (!contextStore.availableEntities || contextStore.availableEntities.length === 0) {
    return [[{
      label: 'No entities available',
      disabled: true
    }]]
  }

  return [
    contextStore.availableEntities.map(entity => ({
      label: entity.name,
      avatar: entity.is_system
        ? { icon: 'i-lucide-settings-2' }
        : { icon: 'i-lucide-building' },
      onSelect() {
        contextStore.switchContext(entity)
      }
    }))
  ]
})

const selectedEntity = computed(() => contextStore.selectedEntity)
</script>

<template>
  <UDropdownMenu
    v-if="selectedEntity"
    :items="items"
    :content="{ align: 'center', collisionPadding: 12 }"
    :ui="{ content: collapsed ? 'w-48' : 'w-(--reka-dropdown-menu-trigger-width)' }"
  >
    <UButton
      v-bind="{
        label: collapsed ? undefined : selectedEntity?.name,
        avatar: selectedEntity.is_system
          ? { icon: 'i-lucide-settings-2' }
          : { icon: 'i-lucide-building' },
        trailingIcon: collapsed ? undefined : 'i-lucide-chevrons-up-down'
      }"
      color="neutral"
      variant="ghost"
      block
      :square="collapsed"
      class="data-[state=open]:bg-elevated"
      :class="[!collapsed && 'py-2']"
      :ui="{
        trailingIcon: 'text-dimmed'
      }"
    />
  </UDropdownMenu>
</template>
