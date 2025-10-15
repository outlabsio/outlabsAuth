<script setup lang="ts">
import * as z from "zod";
import type { FormSubmitEvent } from "@nuxt/ui";

const props = defineProps<{
  user?: {
    id: string;
    name: string;
    email: string;
    is_active: boolean;
    is_superuser: boolean;
    is_team_member: boolean;
    is_verified: boolean;
    permissions: string[];
  };
}>();

const emit = defineEmits(["update"]);

const schema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Invalid email address"),
  is_active: z.boolean(),
  is_superuser: z.boolean(),
  is_team_member: z.boolean(),
  is_verified: z.boolean(),
});

const open = ref(false);

type Schema = z.output<typeof schema>;

const state = reactive<Partial<Schema>>({
  name: undefined,
  email: undefined,
  is_active: undefined,
  is_superuser: undefined,
  is_team_member: undefined,
  is_verified: undefined,
});

// Reset form state when user prop changes
watch(
  () => props.user,
  (newUser) => {
    if (newUser) {
      state.name = newUser.name;
      state.email = newUser.email;
      state.is_active = newUser.is_active;
      state.is_superuser = newUser.is_superuser;
      state.is_team_member = newUser.is_team_member;
      state.is_verified = newUser.is_verified;
    }
  },
  { immediate: true }
);

const toast = useToast();
const usersStore = useUsersStore();

async function onSubmit(event: FormSubmitEvent<Schema>) {
  try {
    if (!props.user?.id) {
      throw new Error("User ID is missing");
    }

    await usersStore.updateUser({
      id: props.user.id,
      ...event.data,
    });

    toast.add({
      title: "Success",
      description: `User ${event.data.name} updated successfully`,
      color: "success",
    });

    emit("update");

    // Close modal
    open.value = false;
  } catch (error) {
    toast.add({
      title: "Error",
      description: error instanceof Error ? error.message : "Failed to update user",
      color: "error",
    });
  }
}
</script>

<template>
  <UModal v-model:open="open" title="Edit User" :disabled="!user">
    <slot />

    <template #body>
      <UForm v-if="user" :schema="schema" :state="state" class="space-y-4" @submit="onSubmit">
        <UFormField label="Name" name="name">
          <UInput v-model="state.name" class="w-full" />
        </UFormField>

        <UFormField label="Email" name="email">
          <UInput v-model="state.email" class="w-full" />
        </UFormField>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <UFormField label="Active" name="is_active">
            <USwitch v-model="state.is_active" />
          </UFormField>

          <UFormField label="Verified" name="is_verified">
            <USwitch v-model="state.is_verified" />
          </UFormField>

          <UFormField label="Team Member" name="is_team_member">
            <USwitch v-model="state.is_team_member" />
          </UFormField>

          <UFormField label="Super User" name="is_superuser">
            <USwitch v-model="state.is_superuser" />
          </UFormField>
        </div>

        <div class="flex justify-end gap-2">
          <UButton label="Cancel" color="neutral" variant="subtle" @click="open = false" />
          <UButton label="Save Changes" color="primary" type="submit" />
        </div>
      </UForm>
    </template>
  </UModal>
</template>
