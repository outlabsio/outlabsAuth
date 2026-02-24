<template>
    <UModal v-model:open="open" :ui="{ width: 'sm:max-w-md' }">
        <UCard>
            <template #header>
                <div class="flex items-start gap-3">
                    <UIcon :name="icon" class="size-5 text-warning shrink-0 mt-0.5" />
                    <div class="space-y-1">
                        <h3 class="text-base font-semibold text-highlighted">
                            {{ title }}
                        </h3>
                        <p v-if="description" class="text-sm text-muted">
                            {{ description }}
                        </p>
                    </div>
                </div>
            </template>

            <template #footer>
                <div class="flex justify-end gap-2">
                    <UButton
                        color="neutral"
                        variant="soft"
                        :disabled="loading"
                        @click="onCancel"
                    >
                        {{ cancelLabel }}
                    </UButton>
                    <UButton
                        :color="confirmColor"
                        :variant="confirmVariant"
                        :loading="loading"
                        @click="emit('confirm')"
                    >
                        {{ confirmLabel }}
                    </UButton>
                </div>
            </template>
        </UCard>
    </UModal>
</template>

<script setup lang="ts">
interface Props {
    title?: string;
    description?: string;
    icon?: string;
    confirmLabel?: string;
    cancelLabel?: string;
    confirmColor?: string;
    confirmVariant?: "solid" | "outline" | "soft" | "ghost" | "subtle" | "link";
    loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    title: "Confirm action",
    description: "",
    icon: "i-lucide-triangle-alert",
    confirmLabel: "Confirm",
    cancelLabel: "Cancel",
    confirmColor: "error",
    confirmVariant: "solid",
    loading: false,
});

const emit = defineEmits<{
    cancel: [];
    confirm: [];
}>();

const open = defineModel<boolean>("open", { required: true });

function onCancel() {
    if (props.loading) {
        return;
    }
    open.value = false;
    emit("cancel");
}
</script>
