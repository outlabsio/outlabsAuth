<script setup lang="ts">
import { useCreateUserMutation } from '~/queries/users'

const open = defineModel<boolean>('open', { default: false })

// Form state
const state = reactive({
  username: '',
  email: '',
  password: '',
  full_name: '',
  is_active: true,
  is_superuser: false
})

// Auto-generate username from email
watch(() => state.email, (newEmail) => {
  if (newEmail && !state.username) {
    const emailPrefix = newEmail.split('@')[0]
    if (emailPrefix) {
      state.username = emailPrefix.toLowerCase().replace(/[^a-z0-9_-]/g, '')
    }
  }
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
const { mutate: createUser, isPending } = useCreateUserMutation()

// Submit handler
async function handleSubmit() {
  try {
    await createUser(state, {
      onSuccess: () => {
        // Close modal and reset form
        open.value = false
        Object.assign(state, {
          username: '',
          email: '',
          password: '',
          full_name: '',
          is_active: true,
          is_superuser: false
        })
      }
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
            <label class="block text-sm font-medium">Full Name</label>
            <UInput
              v-model="state.full_name"
              placeholder="John Doe"
              icon="i-lucide-user"
            />
          </div>

          <div class="space-y-2">
            <label class="block text-sm font-medium">Username</label>
            <UInput
              v-model="state.username"
              placeholder="johndoe"
              icon="i-lucide-at-sign"
            />
            <p class="text-xs text-muted">Lowercase, no spaces</p>
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

        <UDivider label="Permissions" />

        <!-- Switches in grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <UCheckbox
            v-model="state.is_active"
            label="Active"
            help="User can log in and access the system"
          />

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
          :disabled="isPending"
        />
        <UButton
          label="Create User"
          icon="i-lucide-user-plus"
          :loading="isPending"
          @click="handleSubmit"
        />
      </div>
    </template>
  </UModal>
</template>
