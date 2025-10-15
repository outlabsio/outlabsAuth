<script setup lang="ts">
import * as z from "zod";
import type { FormSubmitEvent } from "@nuxt/ui";

// Define props for v-model:open support
const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
}>();

const schema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Invalid email address"),
});

// Create a computed property to handle the v-model:open from parent
const isOpen = computed({
  get: () => props.open,
  set: (value) => emit("update:open", value),
});

type Schema = z.output<typeof schema>;

const state = reactive<Partial<Schema>>({
  name: undefined,
  email: undefined,
});

const loading = ref(false);
const toast = useToast();
const invitationsStore = useInvitationsStore();

async function onSubmit(event: FormSubmitEvent<Schema>) {
  loading.value = true;
  try {
    await invitationsStore.inviteUser({
      name: event.data.name,
      email: event.data.email,
    });

    toast.add({
      title: "Success",
      description: `Invitation sent to ${event.data.email}`,
      color: "success",
    });

    // Reset form
    state.name = undefined;
    state.email = undefined;

    // Close modal
    isOpen.value = false;
  } catch (error) {
    toast.add({
      title: "Error",
      description: error instanceof Error ? error.message : "Failed to invite user",
      color: "error",
    });
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <UModal v-model:open="isOpen" title="Invite User" description="Send an invitation email to a new user">
    <template #default>
      <UButton label="Invite User" color="primary" icon="i-lucide-user-plus" />
    </template>

    <template #body>
      <UForm :schema="schema" :state="state" class="space-y-4" @submit="onSubmit" id="inviteUserForm">
        <div class="space-y-5">
          <UFormField label="Email Address" name="email" required help="The email address to send the invitation to">
            <UInput v-model="state.email" class="w-full" placeholder="colleague@example.com" type="email" icon="i-lucide-mail" autofocus />
          </UFormField>

          <UFormField label="Full Name" name="name" help="The person's full name (optional)">
            <UInput v-model="state.name" class="w-full" placeholder="John Doe" icon="i-lucide-user" />
          </UFormField>
        </div>
      </UForm>
    </template>

    <template #footer>
      <div class="flex justify-end gap-3 w-full">
        <UButton label="Cancel" color="neutral" variant="soft" icon="i-lucide-x" @click="isOpen = false" />
        <UButton label="Send Invitation" color="primary" variant="solid" type="submit" form="inviteUserForm" icon="i-lucide-send" :loading="loading" />
      </div>
    </template>
  </UModal>
</template>
