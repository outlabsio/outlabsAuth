<script setup lang="ts">
const props = defineProps<{
  count?: number;
}>();

const open = ref(false);
const toast = useToast();

function onDelete() {
  toast.add({
    title: "Not implemented",
    description: "User deletion functionality is not yet implemented.",
    color: "warning",
  });
  open.value = false;
}
</script>

<template>
  <UModal v-model:open="open" title="Delete Users">
    <slot />

    <template #body>
      <div class="space-y-4">
        <p>Are you sure you want to delete {{ count === 1 ? "this user" : `these ${count} users` }}? This action cannot be undone.</p>
        <div class="flex justify-end gap-2">
          <UButton label="Cancel" color="neutral" variant="subtle" @click="open = false" />
          <UButton label="Delete" color="error" icon="i-lucide-trash" @click="onDelete" />
        </div>
      </div>
    </template>
  </UModal>
</template>
