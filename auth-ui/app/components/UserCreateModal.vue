<script setup lang="ts">
import { useCreateUserMutation } from '~/queries/users'

const open = defineModel<boolean>('open', { default: false })

// Form state
const state = reactive({
  email: '',
  password: '',
  first_name: '',
  last_name: '',
  is_superuser: false
})

// Password strength indicator
function checkStrength(str: string) {
  if (!str) return []

  const requirements = [
    { regex: /.{8,}/, text: 'At least 8 characters' },
    { regex: /\d/, text: 'At least 1 number' },
    { regex: /[a-z]/, text: 'At least 1 lowercase letter' },
    { regex: /[A-Z]/, text: 'At least 1 uppercase letter' }
  ]

  return requirements.map(req => ({ met: req.regex.test(str), text: req.text }))
}

const strength = computed(() => checkStrength(state.password || ''))
const score = computed(() => strength.value.filter(req => req.met).length)

const passwordColor = computed(() => {
  if (score.value === 0) return 'neutral'
  if (score.value <= 1) return 'error'
  if (score.value <= 2) return 'warning'
  if (score.value === 3) return 'warning'
  return 'success'
})

// Mutation for creating users
const { mutate: createUser, isLoading: isSubmitting } = useCreateUserMutation()

// Submit handler
async function handleSubmit() {
  try {
    await createUser(state)
    // Close modal and reset form on success
    open.value = false
    Object.assign(state, {
      email: '',
      password: '',
      first_name: '',
      last_name: '',
      is_superuser: false
    })
  } catch (error) {
    // Error handling is done by the mutation
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Create User"
    description="Add a new user to your organization"
  >
    <template #body>
      <div class="space-y-4">
        <!-- Grid layout for names -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-sm font-medium">First Name</label>
            <UInput
              v-model="state.first_name"
              placeholder="John"
              icon="i-lucide-user"
            />
          </div>

          <div class="space-y-2">
            <label class="block text-sm font-medium">Last Name</label>
            <UInput
              v-model="state.last_name"
              placeholder="Doe"
              icon="i-lucide-user"
            />
          </div>
        </div>

        <!-- Email -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Email</label>
          <UInput
            v-model="state.email"
            type="email"
            placeholder="john@example.com"
            icon="i-lucide-mail"
          />
        </div>

        <!-- Password with strength indicator -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Password</label>
          <UInput
            v-model="state.password"
            type="password"
            placeholder="Enter a strong password"
            icon="i-lucide-lock"
            :color="passwordColor"
          />

          <!-- Password Strength -->
          <div v-if="state.password" class="space-y-2 mt-2">
            <UProgress
              :color="passwordColor"
              :model-value="score"
              :max="4"
              size="sm"
            />
            <ul class="space-y-1">
              <li
                v-for="(req, index) in strength"
                :key="index"
                class="flex items-center gap-1.5 text-xs"
                :class="req.met ? 'text-success' : 'text-muted'"
              >
                <UIcon :name="req.met ? 'i-lucide-check-circle' : 'i-lucide-circle'" class="w-3 h-3" />
                {{ req.text }}
              </li>
            </ul>
          </div>
        </div>

        <USeparator label="Permissions" />

        <!-- Switches -->
        <div class="space-y-4">
          <UCheckbox
            v-model="state.is_superuser"
            label="Superuser"
            help="Full system access and admin privileges"
          />
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          label="Cancel"
          color="neutral"
          variant="outline"
          @click="open = false"
          :disabled="isSubmitting"
        />
        <UButton
          label="Create User"
          icon="i-lucide-user-plus"
          :loading="isSubmitting"
          @click="handleSubmit"
        />
      </div>
    </template>
  </UModal>
</template>
