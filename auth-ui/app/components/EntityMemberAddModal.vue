<script setup lang="ts">
import { useQuery } from "@pinia/colada";
import { rolesQueries } from "~/queries/roles";
import { useAddMemberMutation } from "~/queries/memberships";
import { useCreateUserMutation, useInviteUserMutation } from "~/queries/users";
import { createUsersAPI } from "~/api/users";
import type { User } from "~/types/auth";
import type { Role } from "~/types/role";

const props = defineProps<{
    entityId: string;
}>();

const open = defineModel<boolean>("open", { default: false });

const authStore = useAuthStore();
const invitationsEnabled = computed(() => authStore.features.invitations);

// Mode: search existing user, create new, or invite
const mode = ref<'search' | 'create' | 'invite'>('search');
const modeItems = computed(() => {
    const items = [
        { value: 'search', label: 'Existing User' },
        { value: 'create', label: 'Create New' },
    ];
    if (invitationsEnabled.value) {
        items.push({ value: 'invite', label: 'Invite' });
    }
    return items;
});

// ──────────────────────────────────────────────
// Search mode state
// ──────────────────────────────────────────────
const searchQuery = ref("");
const searchResults = ref<User[]>([]);
const isSearching = ref(false);
let searchTimeout: ReturnType<typeof setTimeout> | null = null;

async function searchUsers(query: string) {
    searchQuery.value = query;

    if (searchTimeout) clearTimeout(searchTimeout);

    if (!query || query.length < 1) {
        searchTimeout = setTimeout(async () => {
            isSearching.value = true;
            try {
                const usersAPI = createUsersAPI();
                const result = await usersAPI.fetchUsers({}, { page: 1, limit: 20 });
                searchResults.value = result.items;
            } finally {
                isSearching.value = false;
            }
        }, 100);
        return;
    }

    searchTimeout = setTimeout(async () => {
        isSearching.value = true;
        try {
            const usersAPI = createUsersAPI();
            const result = await usersAPI.fetchUsers(
                { search: query },
                { page: 1, limit: 20 },
            );
            searchResults.value = result.items;
        } finally {
            isSearching.value = false;
        }
    }, 300);
}

// ──────────────────────────────────────────────
// Create mode state
// ──────────────────────────────────────────────
const newUser = reactive({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
});

// Password strength
function checkStrength(str: string) {
    if (!str) return [];
    const requirements = [
        { regex: /.{8,}/, text: 'At least 8 characters' },
        { regex: /\d/, text: 'At least 1 number' },
        { regex: /[a-z]/, text: 'At least 1 lowercase letter' },
        { regex: /[A-Z]/, text: 'At least 1 uppercase letter' },
    ];
    return requirements.map(req => ({ met: req.regex.test(str), text: req.text }));
}

const strength = computed(() => checkStrength(newUser.password));
const score = computed(() => strength.value.filter(r => r.met).length);
const passwordColor = computed(() => {
    if (score.value === 0) return 'neutral';
    if (score.value <= 2) return 'error';
    if (score.value === 3) return 'warning';
    return 'success';
});

const isNewUserValid = computed(() => {
    return newUser.email.trim() !== '' && newUser.password.trim() !== '' && score.value >= 3;
});

// ──────────────────────────────────────────────
// Invite mode state
// ──────────────────────────────────────────────
const inviteData = reactive({
    email: '',
    first_name: '',
    last_name: '',
});

const isInviteValid = computed(() => {
    return inviteData.email.trim() !== '' && inviteData.email.includes('@');
});

// ──────────────────────────────────────────────
// Shared state
// ──────────────────────────────────────────────
const state = reactive({
    user_id: "" as string,
    role_ids: [] as string[],
});

const selectedUser = ref<User | null>(null);

// Reset everything when modal opens
watch(open, (isOpen) => {
    if (isOpen) {
        mode.value = 'search';
        state.user_id = "";
        state.role_ids = [];
        selectedUser.value = null;
        searchResults.value = [];
        Object.assign(newUser, { email: '', password: '', first_name: '', last_name: '' });
        Object.assign(inviteData, { email: '', first_name: '', last_name: '' });
        searchUsers("");
    }
});

// Fetch available roles for this entity
const { data: rolesData, isLoading: isLoadingRoles } = useQuery(() => ({
    ...rolesQueries.list(
        { for_entity_id: props.entityId },
        { page: 1, limit: 100 },
    ),
    enabled: open.value && !!props.entityId,
}));

const { mutateAsync: addMember, isLoading: isAddingMember } = useAddMemberMutation();
const { mutateAsync: createUser, isLoading: isCreatingUser } = useCreateUserMutation();
const { mutateAsync: inviteUser, isLoading: isInviting } = useInviteUserMutation();

const isSubmitting = computed(() => isAddingMember.value || isCreatingUser.value || isInviting.value);

// Build items for UInputMenu
const userItems = computed(() => {
    return searchResults.value.map((user: User) => {
        const name =
            user.first_name && user.last_name
                ? `${user.first_name} ${user.last_name}`
                : null;
        return {
            label: name || user.email,
            description: name ? user.email : undefined,
            avatar: {
                text: name
                    ? `${user.first_name![0]}${user.last_name![0]}`
                    : user.email[0].toUpperCase(),
            },
            value: user.id,
            user,
        };
    });
});

function onUserSelect(item: any) {
    if (item) {
        state.user_id = item.value;
        selectedUser.value = item.user;
    } else {
        state.user_id = "";
        selectedUser.value = null;
    }
}

// Role options for multi-select
const roleOptions = computed(() => {
    const roles = rolesData.value?.items || [];
    return roles.map((role: Role) => ({
        label: role.display_name || role.name,
        value: role.id,
    }));
});

// Form validation
const isFormValid = computed(() => {
    if (mode.value === 'search') return state.user_id !== '';
    if (mode.value === 'invite') return isInviteValid.value;
    return isNewUserValid.value;
});

// Submit handler
async function handleSubmit() {
    try {
        if (mode.value === 'invite') {
            // Invite user — single API call handles user creation + membership
            await inviteUser({
                email: inviteData.email,
                first_name: inviteData.first_name || undefined,
                last_name: inviteData.last_name || undefined,
                entity_id: props.entityId,
                role_ids: state.role_ids.length > 0 ? state.role_ids : undefined,
            });
            open.value = false;
            return;
        }

        let userId = state.user_id;

        // If creating a new user, do that first
        if (mode.value === 'create') {
            const created = await createUser({
                email: newUser.email,
                password: newUser.password,
                first_name: newUser.first_name || undefined,
                last_name: newUser.last_name || undefined,
            });
            userId = (created as any).id;
        }

        // Add as member
        await addMember({
            entity_id: props.entityId,
            user_id: userId,
            role_ids: state.role_ids,
        });

        open.value = false;
    } catch (error: any) {
        console.error("Failed to add member:", error);
    }
}

function switchToInvite(email?: string) {
    mode.value = 'invite';
    if (email) inviteData.email = email;
}
</script>

<template>
    <UModal
        v-model:open="open"
        title="Add Member"
        description="Add an existing user, create a new one, or send an invite"
        :ui="{ content: 'sm:max-w-xl' }"
    >
        <template #body>
            <div class="space-y-5">
                <!-- Mode toggle -->
                <UTabs
                    v-model="mode"
                    :items="modeItems"
                    variant="pill"
                />

                <!-- Search existing user -->
                <template v-if="mode === 'search'">
                    <UFormField label="User" required>
                        <UInputMenu
                            :model-value="selectedUser ? userItems.find(i => i.value === state.user_id) : undefined"
                            :items="userItems"
                            placeholder="Search by name or email..."
                            icon="i-lucide-search"
                            :loading="isSearching"
                            :search-input="{ debounce: 0 }"
                            class="w-full"
                            by="value"
                            @update:search-term="searchUsers"
                            @update:model-value="onUserSelect"
                        >
                            <template #item="{ item }">
                                <UAvatar
                                    :text="item.avatar?.text"
                                    size="sm"
                                />
                                <div class="flex flex-col min-w-0">
                                    <span class="truncate font-medium">{{ item.label }}</span>
                                    <span v-if="item.description" class="truncate text-xs text-muted">{{ item.description }}</span>
                                </div>
                            </template>

                            <template #empty>
                                <div class="flex flex-col items-center gap-1 py-3">
                                    <UIcon name="i-lucide-user-search" class="size-5 text-muted" />
                                    <span class="text-sm text-muted">
                                        {{ searchQuery ? 'No users found' : 'Start typing to search' }}
                                    </span>
                                    <div v-if="searchQuery" class="flex flex-col items-center gap-1">
                                        <UButton
                                            label="Create this user instead"
                                            variant="link"
                                            size="xs"
                                            @click="mode = 'create'; newUser.email = searchQuery"
                                        />
                                        <UButton
                                            v-if="invitationsEnabled"
                                            label="Invite this person instead"
                                            variant="link"
                                            size="xs"
                                            icon="i-lucide-mail"
                                            @click="switchToInvite(searchQuery)"
                                        />
                                    </div>
                                </div>
                            </template>
                        </UInputMenu>

                        <!-- Selected user preview -->
                        <div
                            v-if="selectedUser"
                            class="mt-2 flex items-center gap-3 rounded-md bg-elevated/50 px-3 py-2"
                        >
                            <UAvatar
                                :text="selectedUser.first_name && selectedUser.last_name
                                    ? `${selectedUser.first_name[0]}${selectedUser.last_name[0]}`
                                    : selectedUser.email[0].toUpperCase()"
                                size="sm"
                            />
                            <div class="flex flex-col min-w-0 flex-1">
                                <span class="text-sm font-medium truncate">
                                    {{ selectedUser.first_name && selectedUser.last_name
                                        ? `${selectedUser.first_name} ${selectedUser.last_name}`
                                        : selectedUser.email }}
                                </span>
                                <span v-if="selectedUser.first_name" class="text-xs text-muted truncate">
                                    {{ selectedUser.email }}
                                </span>
                            </div>
                            <UBadge :label="selectedUser.status" :color="selectedUser.status === 'active' ? 'success' : 'warning'" variant="subtle" size="xs" />
                            <UButton
                                icon="i-lucide-x"
                                size="xs"
                                color="neutral"
                                variant="ghost"
                                @click="state.user_id = ''; selectedUser = null"
                            />
                        </div>
                    </UFormField>
                </template>

                <!-- Create new user -->
                <template v-else-if="mode === 'create'">
                    <div class="space-y-4">
                        <div class="grid grid-cols-2 gap-3">
                            <UFormField label="First Name">
                                <UInput
                                    v-model="newUser.first_name"
                                    placeholder="John"
                                    icon="i-lucide-user"
                                    class="w-full"
                                />
                            </UFormField>
                            <UFormField label="Last Name">
                                <UInput
                                    v-model="newUser.last_name"
                                    placeholder="Doe"
                                    icon="i-lucide-user"
                                    class="w-full"
                                />
                            </UFormField>
                        </div>

                        <UFormField label="Email" required>
                            <UInput
                                v-model="newUser.email"
                                type="email"
                                placeholder="john@example.com"
                                icon="i-lucide-mail"
                                class="w-full"
                            />
                        </UFormField>

                        <UFormField label="Password" required>
                            <UInput
                                v-model="newUser.password"
                                type="password"
                                placeholder="Enter a strong password"
                                icon="i-lucide-lock"
                                class="w-full"
                            />

                            <!-- Password strength -->
                            <template #description>
                                <div v-if="newUser.password" class="space-y-2 mt-1">
                                    <UProgress
                                        :color="passwordColor"
                                        :model-value="score"
                                        :max="4"
                                        size="sm"
                                    />
                                    <ul class="space-y-0.5">
                                        <li
                                            v-for="(req, index) in strength"
                                            :key="index"
                                            class="flex items-center gap-1.5 text-xs"
                                            :class="req.met ? 'text-success' : 'text-muted'"
                                        >
                                            <UIcon :name="req.met ? 'i-lucide-check-circle' : 'i-lucide-circle'" class="size-3" />
                                            {{ req.text }}
                                        </li>
                                    </ul>
                                </div>
                            </template>
                        </UFormField>
                    </div>
                </template>

                <!-- Invite user -->
                <template v-else-if="mode === 'invite'">
                    <div class="space-y-4">
                        <UAlert
                            color="info"
                            icon="i-lucide-mail"
                            title="They'll receive a link to set their password"
                        />

                        <UFormField label="Email" required>
                            <UInput
                                v-model="inviteData.email"
                                type="email"
                                placeholder="john@example.com"
                                icon="i-lucide-mail"
                                class="w-full"
                            />
                        </UFormField>

                        <div class="grid grid-cols-2 gap-3">
                            <UFormField label="First Name">
                                <UInput
                                    v-model="inviteData.first_name"
                                    placeholder="John"
                                    icon="i-lucide-user"
                                    class="w-full"
                                />
                            </UFormField>
                            <UFormField label="Last Name">
                                <UInput
                                    v-model="inviteData.last_name"
                                    placeholder="Doe"
                                    icon="i-lucide-user"
                                    class="w-full"
                                />
                            </UFormField>
                        </div>
                    </div>
                </template>

                <USeparator />

                <!-- Role Selection (shared between all modes) -->
                <UFormField label="Roles" hint="Optional">
                    <USelectMenu
                        v-model="state.role_ids"
                        :items="roleOptions"
                        placeholder="Select roles..."
                        :loading="isLoadingRoles"
                        multiple
                        searchable
                        value-key="value"
                        class="w-full"
                    />
                    <template #description>
                        Assign roles to this member. Auto-assigned roles will be added automatically.
                    </template>
                </UFormField>
            </div>
        </template>

        <template #footer>
            <div class="flex justify-end gap-2">
                <UButton
                    label="Cancel"
                    color="neutral"
                    variant="outline"
                    :disabled="isSubmitting"
                    @click="open = false"
                />
                <UButton
                    :label="mode === 'invite' ? 'Send Invite' : mode === 'create' ? 'Create & Add' : 'Add Member'"
                    :icon="mode === 'invite' ? 'i-lucide-send' : 'i-lucide-user-plus'"
                    :loading="isSubmitting"
                    :disabled="!isFormValid || isSubmitting"
                    @click="handleSubmit"
                />
            </div>
        </template>
    </UModal>
</template>
