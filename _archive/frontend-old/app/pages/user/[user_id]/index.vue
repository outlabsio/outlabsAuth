<template>
  <div v-if="userDetailsStore.loading" class="space-y-8">
    <!-- Hero Skeleton -->
    <div class="relative overflow-hidden bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-neutral-900 dark:to-neutral-800 rounded-3xl p-8">
      <div class="flex flex-col md:flex-row items-center gap-8">
        <USkeleton class="size-32 rounded-full shrink-0" />
        <div class="flex-grow space-y-4 text-center md:text-left">
          <USkeleton class="h-10 w-1/3 mx-auto md:mx-0" />
          <USkeleton class="h-6 w-2/3 mx-auto md:mx-0" />
          <div class="flex flex-wrap justify-center md:justify-start gap-2">
            <USkeleton v-for="_ in 3" class="h-8 w-20" />
          </div>
        </div>
      </div>
    </div>
    <!-- Stats Skeleton -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <USkeleton v-for="_ in 3" class="h-24 rounded-2xl" />
    </div>
    <!-- Content Skeleton -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <USkeleton v-for="_ in 4" class="h-96 rounded-2xl" />
    </div>
  </div>

  <div v-else-if="userDetailsStore.user" class="space-y-8">
    <!-- Redesigned Hero Section -->
    <div class="space-y-6">
      <!-- Main User Info -->
      <div class="flex flex-col md:flex-row items-start md:items-center gap-6">
        <!-- Avatar Section -->
        <div class="relative">
          <div class="w-24 h-24 md:w-28 md:h-28 relative">
            <UAvatar
              :src="`https://avatars.dicebear.com/api/initials/${userDetailsStore.user.name || 'User'}.svg`"
              size="3xl"
              class="w-full h-full shadow-lg border-4 border-white dark:border-neutral-800"
            />
            <!-- Status Indicator -->
            <div
              class="absolute -bottom-1 -right-1 w-7 h-7 rounded-full border-3 border-white dark:border-neutral-900 shadow-lg flex items-center justify-center"
              :class="userDetailsStore.user.is_active ? 'bg-emerald-500' : 'bg-red-500'"
            >
              <UIcon :name="userDetailsStore.user.is_active ? 'i-lucide-check' : 'i-lucide-x'" class="w-3.5 h-3.5 text-white" />
            </div>
          </div>
        </div>

        <!-- User Details -->
        <div class="flex-grow">
          <div class="space-y-3">
            <!-- Name and Email -->
            <div>
              <h1 class="text-3xl md:text-4xl font-bold text-neutral-900 dark:text-white mb-1">
                {{ userDetailsStore.user.name || "User Profile" }}
              </h1>
              <p class="text-lg text-neutral-600 dark:text-neutral-400">{{ userDetailsStore.user.email }}</p>
            </div>

            <!-- Status Badges -->
            <div class="flex flex-wrap gap-2">
              <UBadge :color="userDetailsStore.user.is_active ? 'success' : 'error'" variant="subtle" size="md" class="px-3 py-1.5">
                <UIcon :name="userDetailsStore.user.is_active ? 'i-lucide-check-circle' : 'i-lucide-x-circle'" class="w-3.5 h-3.5 mr-1.5" />
                {{ userDetailsStore.user.is_active ? "Active" : "Inactive" }}
              </UBadge>
              <UBadge :color="userDetailsStore.user.is_verified ? 'success' : 'warning'" variant="subtle" size="md" class="px-3 py-1.5">
                <UIcon :name="userDetailsStore.user.is_verified ? 'i-lucide-shield-check' : 'i-lucide-shield-alert'" class="w-3.5 h-3.5 mr-1.5" />
                {{ userDetailsStore.user.is_verified ? "Verified" : "Unverified" }}
              </UBadge>
              <UBadge v-if="userDetailsStore.user.is_superuser" color="secondary" variant="subtle" size="md" class="px-3 py-1.5">
                <UIcon name="i-lucide-crown" class="w-3.5 h-3.5 mr-1.5" />
                Superuser
              </UBadge>
              <UBadge v-if="userDetailsStore.user.is_team_member" color="info" variant="subtle" size="md" class="px-3 py-1.5">
                <UIcon name="i-lucide-users" class="w-3.5 h-3.5 mr-1.5" />
                Team Member
              </UBadge>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Stats Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Member Since -->
        <div class="bg-white dark:bg-neutral-800 rounded-xl p-4 border border-neutral-200 dark:border-neutral-700 shadow-sm">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-blue-50 dark:bg-blue-900/20 rounded-lg flex items-center justify-center">
              <UIcon name="i-lucide-calendar" class="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p class="text-sm text-neutral-500 dark:text-neutral-400">Member Since</p>
              <p class="font-semibold text-neutral-900 dark:text-white">{{ usersStore.formatDate(userDetailsStore.user.created_at) }}</p>
            </div>
          </div>
        </div>

        <!-- Last Login -->
        <div class="bg-white dark:bg-neutral-800 rounded-xl p-4 border border-neutral-200 dark:border-neutral-700 shadow-sm">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-green-50 dark:bg-green-900/20 rounded-lg flex items-center justify-center">
              <UIcon name="i-lucide-clock" class="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p class="text-sm text-neutral-500 dark:text-neutral-400">Last Login</p>
              <p class="font-semibold text-neutral-900 dark:text-white">{{ getRelativeTime(userDetailsStore.user.last_login || "") }}</p>
            </div>
          </div>
        </div>

        <!-- Language -->
        <div class="bg-white dark:bg-neutral-800 rounded-xl p-4 border border-neutral-200 dark:border-neutral-700 shadow-sm">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-purple-50 dark:bg-purple-900/20 rounded-lg flex items-center justify-center">
              <UIcon name="i-lucide-globe" class="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p class="text-sm text-neutral-500 dark:text-neutral-400">Language</p>
              <p class="font-semibold text-neutral-900 dark:text-white">
                {{ userDetailsStore.user.locale === "en" ? "English" : userDetailsStore.user.locale === "es" ? "Spanish" : userDetailsStore.user.locale }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Stats Bar -->
    <div v-if="userDetailsStore.user.account" class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- Token Balance -->
      <div class="relative overflow-hidden bg-gradient-to-br from-emerald-500 to-teal-600 rounded-2xl p-6 text-white shadow-xl">
        <div class="absolute inset-0 bg-white/10 backdrop-blur-sm"></div>
        <div class="relative z-10">
          <div class="flex items-center justify-between mb-4">
            <UIcon name="i-lucide-coins" class="w-8 h-8" />
            <div class="text-right">
              <div class="text-3xl font-bold">{{ userDetailsStore.user.account.token_balance.toLocaleString() }}</div>
              <div class="text-emerald-100 text-sm">Available Tokens</div>
            </div>
          </div>
          <div class="flex items-center justify-between text-sm text-emerald-100">
            <span>Usage: {{ userDetailsStore.user.account.total_tokens_used.toLocaleString() }}</span>
            <div class="flex items-center gap-1">
              <div class="w-2 h-2 rounded-full" :class="userDetailsStore.user.account.has_available_tokens ? 'bg-emerald-300' : 'bg-red-300'"></div>
              <span>{{ userDetailsStore.user.account.has_available_tokens ? "Available" : "Depleted" }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Purchases -->
      <div class="relative overflow-hidden bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl p-6 text-white shadow-xl">
        <div class="absolute inset-0 bg-white/10 backdrop-blur-sm"></div>
        <div class="relative z-10">
          <div class="flex items-center justify-between mb-4">
            <UIcon name="i-lucide-shopping-cart" class="w-8 h-8" />
            <div class="text-right">
              <div class="text-3xl font-bold">{{ userDetailsStore.user.account.total_purchases }}</div>
              <div class="text-blue-100 text-sm">Total Purchases</div>
            </div>
          </div>
          <div class="flex items-center justify-between text-sm text-blue-100">
            <span>{{ userDetailsStore.user.account.payment_methods.length }} Payment Method{{ userDetailsStore.user.account.payment_methods.length !== 1 ? "s" : "" }}</span>
            <div class="flex items-center gap-1">
              <div class="w-2 h-2 rounded-full" :class="userDetailsStore.user.account.has_payment_method ? 'bg-blue-300' : 'bg-red-300'"></div>
              <span>{{ userDetailsStore.user.account.has_payment_method ? "Setup" : "None" }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Account Status -->
      <div class="relative overflow-hidden bg-gradient-to-br from-purple-500 to-pink-600 rounded-2xl p-6 text-white shadow-xl">
        <div class="absolute inset-0 bg-white/10 backdrop-blur-sm"></div>
        <div class="relative z-10">
          <div class="flex items-center justify-between mb-4">
            <UIcon name="i-lucide-activity" class="w-8 h-8" />
            <div class="text-right">
              <div class="text-2xl font-bold">
                {{ userDetailsStore.user.account.is_active ? "Active" : "Inactive" }}
              </div>
              <div class="text-purple-100 text-sm">Account Status</div>
            </div>
          </div>
          <div class="flex items-center justify-between text-sm text-purple-100">
            <span>Auto Top-up: {{ userDetailsStore.user.account.auto_topup.enabled ? "On" : "Off" }}</span>
            <div class="flex items-center gap-1">
              <div class="w-2 h-2 rounded-full" :class="userDetailsStore.user.account.needs_topup ? 'bg-amber-300' : 'bg-purple-300'"></div>
              <span>{{ userDetailsStore.user.account.needs_topup ? "Needs Top-up" : "Good" }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content Bento Grid -->
    <div class="space-y-8">
      <!-- First Row: Token Usage, Reading Stats, Auto Top-up -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Token Usage Chart -->
        <div class="bg-white dark:bg-neutral-800 rounded-2xl p-6 shadow-lg border border-neutral-100 dark:border-neutral-700 flex flex-col">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-lg font-semibold flex items-center gap-2">
              <UIcon name="i-lucide-trending-up" class="w-5 h-5 text-emerald-500" />
              Token Usage
            </h3>
            <UBadge :color="userDetailsStore.user.account?.has_available_tokens ? 'success' : 'error'" variant="soft">
              {{ userDetailsStore.user.account?.has_available_tokens ? "Available" : "Depleted" }}
            </UBadge>
          </div>

          <!-- Usage Progress -->
          <div class="space-y-4 flex-grow">
            <div>
              <div class="flex justify-between text-sm mb-2">
                <span class="text-neutral-600 dark:text-neutral-400">Used</span>
                <span class="font-medium">{{ userDetailsStore.user.account?.total_tokens_used.toLocaleString() }} tokens</span>
              </div>
              <div class="w-full bg-neutral-200 dark:bg-neutral-700 rounded-full h-3">
                <div
                  class="bg-gradient-to-r from-red-500 to-orange-500 h-3 rounded-full transition-all duration-1000"
                  :style="`width: ${Math.min(
                    ((userDetailsStore.user.account?.total_tokens_used || 0) / ((userDetailsStore.user.account?.total_tokens_used || 0) + (userDetailsStore.user.account?.token_balance || 1))) * 100,
                    100
                  )}%`"
                ></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-sm mb-2">
                <span class="text-neutral-600 dark:text-neutral-400">Available</span>
                <span class="font-medium">{{ userDetailsStore.user.account?.token_balance.toLocaleString() }} tokens</span>
              </div>
              <div class="w-full bg-neutral-200 dark:bg-neutral-700 rounded-full h-3">
                <div
                  class="bg-gradient-to-r from-emerald-500 to-teal-500 h-3 rounded-full transition-all duration-1000"
                  :style="`width: ${Math.min(
                    ((userDetailsStore.user.account?.token_balance || 0) / ((userDetailsStore.user.account?.total_tokens_used || 0) + (userDetailsStore.user.account?.token_balance || 1))) * 100,
                    100
                  )}%`"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Reading Statistics -->
        <div v-if="userDetailsStore.accountStats" class="bg-white dark:bg-neutral-800 rounded-2xl p-6 shadow-lg border border-neutral-100 dark:border-neutral-700 flex flex-col">
          <h3 class="text-lg font-semibold mb-6 flex items-center gap-2">
            <UIcon name="i-lucide-book-open" class="w-5 h-5 text-orange-500" />
            Reading Statistics
          </h3>

          <div class="text-center mb-6">
            <div class="text-4xl font-bold text-neutral-900 dark:text-white mb-2">
              {{ userDetailsStore.accountStats.total_readings }}
            </div>
            <div class="text-neutral-500 dark:text-neutral-400">Total Readings</div>
          </div>

          <div class="grid grid-cols-3 gap-4 flex-grow">
            <div class="text-center">
              <div class="w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-xl flex items-center justify-center mx-auto mb-2">
                <UIcon name="i-lucide-zap" class="w-6 h-6 text-amber-600 dark:text-amber-400" />
              </div>
              <div class="font-semibold text-neutral-900 dark:text-white">{{ userDetailsStore.accountStats.basic_readings }}</div>
              <div class="text-xs text-neutral-500 dark:text-neutral-400">Basic</div>
            </div>
            <div class="text-center">
              <div class="w-12 h-12 bg-orange-100 dark:bg-orange-900/30 rounded-xl flex items-center justify-center mx-auto mb-2">
                <UIcon name="i-lucide-flame" class="w-6 h-6 text-orange-600 dark:text-orange-400" />
              </div>
              <div class="font-semibold text-neutral-900 dark:text-white">{{ userDetailsStore.accountStats.advanced_readings }}</div>
              <div class="text-xs text-neutral-500 dark:text-neutral-400">Advanced</div>
            </div>
            <div class="text-center">
              <div class="w-12 h-12 bg-purple-100 dark:bg-purple-900/30 rounded-xl flex items-center justify-center mx-auto mb-2">
                <UIcon name="i-lucide-sparkles" class="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <div class="font-semibold text-neutral-900 dark:text-white">{{ userDetailsStore.accountStats.oracle_readings }}</div>
              <div class="text-xs text-neutral-500 dark:text-neutral-400">Oracle</div>
            </div>
          </div>
        </div>

        <!-- Auto Top-up Settings -->
        <div class="bg-white dark:bg-neutral-800 rounded-2xl p-6 shadow-lg border border-neutral-100 dark:border-neutral-700 flex flex-col">
          <h3 class="text-lg font-semibold mb-6 flex items-center gap-2">
            <UIcon name="i-lucide-repeat" class="w-5 h-5 text-purple-500" />
            Auto Top-up Settings
          </h3>

          <div class="space-y-4 flex-grow">
            <div class="flex items-center justify-between p-4 bg-neutral-50 dark:bg-neutral-700/50 rounded-xl">
              <div class="flex items-center gap-3">
                <div
                  class="w-10 h-10 rounded-full flex items-center justify-center"
                  :class="userDetailsStore.user.account?.auto_topup?.enabled ? 'bg-green-100 dark:bg-green-900/30' : 'bg-neutral-100 dark:bg-neutral-600'"
                >
                  <UIcon
                    :name="userDetailsStore.user.account?.auto_topup?.enabled ? 'i-lucide-check' : 'i-lucide-x'"
                    :class="userDetailsStore.user.account?.auto_topup?.enabled ? 'text-green-600 dark:text-green-400' : 'text-neutral-400'"
                    class="w-5 h-5"
                  />
                </div>
                <div>
                  <div class="font-medium">Auto Top-up</div>
                  <div class="text-sm text-neutral-500 dark:text-neutral-400">
                    {{ userDetailsStore.user.account?.auto_topup?.enabled ? "Enabled" : "Disabled" }}
                  </div>
                </div>
              </div>
              <UBadge :color="userDetailsStore.user.account?.auto_topup?.enabled ? 'success' : 'neutral'" variant="soft">
                {{ userDetailsStore.user.account?.auto_topup?.enabled ? "Active" : "Inactive" }}
              </UBadge>
            </div>

            <div v-if="userDetailsStore.user.account?.auto_topup?.enabled" class="space-y-3">
              <div class="flex justify-between text-sm">
                <span class="text-neutral-600 dark:text-neutral-400">Threshold</span>
                <span class="font-medium">{{ userDetailsStore.user.account.auto_topup.threshold }} tokens</span>
              </div>
              <div v-if="userDetailsStore.user.account.auto_topup.pack_type" class="flex justify-between text-sm">
                <span class="text-neutral-600 dark:text-neutral-400">Pack Type</span>
                <span class="font-medium">{{ userDetailsStore.user.account.auto_topup.pack_type }}</span>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4 pt-4 mt-auto">
              <div class="text-center">
                <div class="text-lg font-semibold" :class="userDetailsStore.user.account?.is_eligible_for_auto_topup ? 'text-green-600 dark:text-green-400' : 'text-neutral-400'">
                  {{ userDetailsStore.user.account?.is_eligible_for_auto_topup ? "Eligible" : "Not Eligible" }}
                </div>
                <div class="text-xs text-neutral-500 dark:text-neutral-400">For Auto Top-up</div>
              </div>
              <div class="text-center">
                <div class="text-lg font-semibold" :class="userDetailsStore.user.account?.needs_topup ? 'text-amber-600 dark:text-amber-400' : 'text-green-600 dark:text-green-400'">
                  {{ userDetailsStore.user.account?.needs_topup ? "Needed" : "Good" }}
                </div>
                <div class="text-xs text-neutral-500 dark:text-neutral-400">Top-up Status</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Second Row: Payment Methods -->
      <div class="space-y-6">
        <h2 class="text-2xl font-bold text-neutral-900 dark:text-white flex items-center gap-3">
          <div class="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
            <UIcon name="i-lucide-credit-card" class="w-4 h-4 text-white" />
          </div>
          Payment Methods
        </h2>

        <div class="bg-white dark:bg-neutral-800 rounded-2xl p-6 shadow-lg border border-neutral-100 dark:border-neutral-700">
          <div v-if="userDetailsStore.user.account?.payment_methods?.length" class="space-y-4">
            <div
              v-for="method in userDetailsStore.user.account.payment_methods"
              :key="method.id"
              class="flex items-center justify-between p-4 border border-neutral-200 dark:border-neutral-600 rounded-xl hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-colors"
            >
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 bg-gradient-to-br from-blue-100 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30 rounded-xl flex items-center justify-center">
                  <UIcon name="i-lucide-credit-card" class="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <div class="font-medium text-neutral-900 dark:text-white">•••• •••• •••• {{ method.last4 }}</div>
                  <div class="text-sm text-neutral-500 dark:text-neutral-400">{{ method.brand.toUpperCase() }} • Expires {{ method.exp_month }}/{{ method.exp_year }}</div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <UBadge v-if="method.is_default" color="primary" variant="soft" size="sm">Default</UBadge>
                <UBadge color="success" variant="soft" size="sm">Active</UBadge>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-8">
            <UIcon name="i-lucide-credit-card" class="w-16 h-16 text-neutral-300 dark:text-neutral-600 mx-auto mb-4" />
            <p class="text-neutral-500 dark:text-neutral-400">No payment methods configured</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Token Grants Section -->
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-2xl font-bold text-neutral-900 dark:text-white flex items-center gap-3">
          <div class="w-8 h-8 bg-gradient-to-br from-amber-500 to-orange-600 rounded-lg flex items-center justify-center">
            <UIcon name="i-lucide-gift" class="w-4 h-4 text-white" />
          </div>
          Token Grants History
        </h2>
        <UButton icon="i-lucide-refresh-cw" variant="ghost" size="sm" :loading="userDetailsStore.grantsLoading" @click="refreshGrants" />
      </div>

      <div v-if="userDetailsStore.grantsLoading" class="bg-white dark:bg-neutral-800 rounded-2xl p-6 shadow-lg border border-neutral-100 dark:border-neutral-700">
        <div class="space-y-4">
          <USkeleton v-for="i in 3" :key="i" class="h-16 w-full" />
        </div>
      </div>

      <div v-else-if="userDetailsStore.grantsError" class="bg-white dark:bg-neutral-800 rounded-2xl p-8 shadow-lg border border-neutral-100 dark:border-neutral-700">
        <UAlert
          icon="i-lucide-alert-triangle"
          color="error"
          variant="subtle"
          title="Error Loading Grants"
          :description="
            typeof userDetailsStore.grantsError === 'string'
              ? userDetailsStore.grantsError
              : userDetailsStore.grantsError instanceof Error
              ? userDetailsStore.grantsError.message
              : 'Could not load token grants.'
          "
        />
      </div>

      <div v-else-if="userDetailsStore.tokenGrants.length > 0" class="bg-white dark:bg-neutral-800 rounded-2xl shadow-lg border border-neutral-100 dark:border-neutral-700 overflow-hidden">
        <!-- Header -->
        <div class="px-6 py-4 bg-neutral-50 dark:bg-neutral-700/50 border-b border-neutral-100 dark:border-neutral-700">
          <div class="grid grid-cols-12 gap-4 text-sm font-medium text-neutral-600 dark:text-neutral-400">
            <div class="col-span-3">Amount & Source</div>
            <div class="col-span-5">Reason & Description</div>
            <div class="col-span-2">Balance After</div>
            <div class="col-span-2">Date</div>
          </div>
        </div>

        <!-- Grants List -->
        <div class="divide-y divide-neutral-100 dark:divide-neutral-700 max-h-96 overflow-y-auto">
          <div v-for="grant in userDetailsStore.tokenGrants" :key="grant.id" class="px-6 py-4 hover:bg-neutral-50 dark:hover:bg-neutral-700/30 transition-colors">
            <div class="grid grid-cols-12 gap-4 items-center">
              <!-- Amount & Source -->
              <div class="col-span-3">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 bg-gradient-to-br from-emerald-100 to-green-100 dark:from-emerald-900/30 dark:to-green-900/30 rounded-lg flex items-center justify-center">
                    <UIcon name="i-lucide-plus" class="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div>
                    <div class="font-bold text-emerald-600 dark:text-emerald-400">+{{ grant.token_amount }}</div>
                    <UBadge :color="getGrantBadgeColor(grant.source)" variant="soft" size="sm" class="capitalize">
                      {{ grant.source || "Grant" }}
                    </UBadge>
                  </div>
                </div>
              </div>

              <!-- Reason & Description -->
              <div class="col-span-5">
                <div class="font-medium text-neutral-900 dark:text-white text-sm mb-1">
                  {{ grant.reason || "Token grant" }}
                </div>
                <div v-if="grant.description" class="text-xs text-neutral-500 dark:text-neutral-400 line-clamp-2">
                  {{ grant.description }}
                </div>
              </div>

              <!-- Balance After -->
              <div class="col-span-2">
                <div class="font-semibold text-neutral-900 dark:text-white">{{ grant.balance_after }} tokens</div>
              </div>

              <!-- Date -->
              <div class="col-span-2">
                <div class="text-sm text-neutral-500 dark:text-neutral-400">
                  {{ formatDate(grant.timestamp) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="bg-white dark:bg-neutral-800 rounded-2xl p-12 shadow-lg border border-neutral-100 dark:border-neutral-700 text-center">
        <UIcon name="i-lucide-gift" class="w-16 h-16 text-neutral-300 dark:text-neutral-600 mx-auto mb-4" />
        <h3 class="text-lg font-semibold text-neutral-900 dark:text-white mb-2">No Token Grants Found</h3>
        <p class="text-neutral-500 dark:text-neutral-400">This user has not received any admin token grants yet.</p>
      </div>
    </div>
  </div>

  <div v-else-if="userDetailsStore.error" class="bg-white dark:bg-neutral-800 rounded-2xl p-12 shadow-lg border border-neutral-100 dark:border-neutral-700 text-center">
    <UIcon name="i-lucide-alert-triangle" class="w-16 h-16 text-red-500 mx-auto mb-4" />
    <h3 class="text-xl font-semibold text-neutral-900 dark:text-white mb-2">Error Loading User</h3>
    <p class="text-neutral-500 dark:text-neutral-400 mb-6">
      {{ typeof userDetailsStore.error === "string" ? userDetailsStore.error : userDetailsStore.error instanceof Error ? userDetailsStore.error.message : "Could not load user details." }}
    </p>
    <UButton label="Back to Users" to="/users" />
  </div>

  <div v-else class="bg-white dark:bg-neutral-800 rounded-2xl p-12 shadow-lg border border-neutral-100 dark:border-neutral-700 text-center">
    <UIcon name="i-lucide-user-x" class="w-16 h-16 text-neutral-400 mx-auto mb-4" />
    <h3 class="text-xl font-semibold text-neutral-900 dark:text-white mb-2">User not found</h3>
    <p class="text-neutral-500 dark:text-neutral-400 mb-6">The user you're looking for doesn't exist or couldn't be loaded.</p>
    <UButton label="Back to Users" to="/users" />
  </div>
</template>

<script setup lang="ts">
// Define User interface based on provided Python model
interface User {
  id: string; // Assuming id is passed via route params or fetched
  email: string;
  hashed_password?: string; // Usually not needed/sent to frontend
  name: string;
  permissions: string[];
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  is_team_member: boolean;
  password_reset_token?: string | null;
  password_reset_token_expires_at?: string | null; // Dates as strings
  pending_email?: string | null;
  email_change_token?: string | null;
  email_change_token_expires_at?: string | null; // Dates as strings
  created_at: string; // Dates as strings
  updated_at?: string | null; // Dates as strings
  locale: string; // 'en' | 'es'
  last_login: string; // Changed to required string
  account?: UserAccount; // Added account property
}

// Interface for User Account data
interface UserAccount {
  token_balance: number;
  is_active: boolean;
  auto_topup: {
    enabled: boolean;
    threshold: number;
    pack_type: string | null;
  };
  payment_methods: any[];
  default_payment_method: any | null;
  total_tokens_used: number;
  total_purchases: number;
  last_purchase: string | null;
  last_login: string;
  has_available_tokens: boolean;
  has_payment_method: boolean;
  is_eligible_for_auto_topup: boolean;
  needs_topup: boolean;
}

// Interface for User Account Statistics
interface UserAccountStats {
  token_balance: number;
  total_token_usage: number;
  total_readings: number;
  basic_readings: number;
  advanced_readings: number;
  oracle_readings: number;
  last_activity_timestamp?: string | null;
}

const route = useRoute();
const toast = useToast();
const usersStore = useUsersStore(); // Keep for helper functions like formatDate, getUserType

// Use the store
const userDetailsStore = useUserDetailsStore();

const userId = computed(() => route.params.user_id as string);

// Helper function to format date
const formatDate = (dateString: string | null | undefined): string => {
  if (!dateString) return "N/A";
  try {
    return new Date(dateString).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (e) {
    return "Invalid Date";
  }
};

// Helper function to get relative time
const getRelativeTime = (dateString: string): string => {
  if (!dateString) return "";
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMs = now.getTime() - date.getTime();
    const diffInSeconds = Math.floor(diffInMs / 1000);
    const diffInMinutes = Math.floor(diffInSeconds / 60);
    const diffInHours = Math.floor(diffInMinutes / 60);
    const diffInDays = Math.floor(diffInHours / 24);
    const diffInWeeks = Math.floor(diffInDays / 7);
    const diffInMonths = Math.floor(diffInDays / 30);
    const diffInYears = Math.floor(diffInDays / 365);

    if (diffInYears > 0) {
      return `${diffInYears} year${diffInYears > 1 ? "s" : ""} ago`;
    } else if (diffInMonths > 0) {
      return `${diffInMonths} month${diffInMonths > 1 ? "s" : ""} ago`;
    } else if (diffInWeeks > 0) {
      return `${diffInWeeks} week${diffInWeeks > 1 ? "s" : ""} ago`;
    } else if (diffInDays > 0) {
      return `${diffInDays} day${diffInDays > 1 ? "s" : ""} ago`;
    } else if (diffInHours > 0) {
      return `${diffInHours} hour${diffInHours > 1 ? "s" : ""} ago`;
    } else if (diffInMinutes > 0) {
      return `${diffInMinutes} minute${diffInMinutes > 1 ? "s" : ""} ago`;
    } else {
      return "Just now";
    }
  } catch (e) {
    return "";
  }
};

// Helper function to get badge color based on grant source
const getGrantBadgeColor = (source: string | null | undefined): "primary" | "secondary" | "success" | "info" | "warning" | "error" | "neutral" => {
  switch (source) {
    case "admin":
      return "primary"; // Main admin actions
    case "compensation":
      return "info"; // Compensation is informational, could also be 'warning' if it implies an issue
    case "system":
      return "secondary"; // System actions can be secondary
    case "promo_code":
      return "success"; // Promo codes are generally positive/successful application
    case "referral":
      return "success"; // Referrals are positive
    case "milestone":
      return "success"; // Milestones are positive achievements
    case "payment": // Though not typically a grant source, good to have
      return "primary";
    case "achievement": // Similar to milestone
      return "success";
    default:
      return "neutral"; // Default for unknown or other sources
  }
};

// Refresh grants
const refreshGrants = () => {
  if (userId.value) {
    userDetailsStore.fetchUserTokenGrants(userId.value);
    // It's good practice to also provide a way to refresh stats if needed,
    // or tie it to a general refresh mechanism for the page.
    // For now, we'll assume stats are fetched with user details or grants.
    // If a separate refresh button for stats is added, call:
    // userDetailsStore.fetchUserAccountStats(userId.value);
  }
};

// Fetch user details using the store action
onMounted(() => {
  if (userId.value) {
    userDetailsStore.fetchUserDetails(userId.value);
    userDetailsStore.fetchUserTokenGrants(userId.value);
    userDetailsStore.fetchUserAccountStats(userId.value); // Fetch stats
  }
});

// Watch for route changes to fetch new user details
watch(
  () => route.params.user_id,
  (newId) => {
    if (newId && typeof newId === "string") {
      userDetailsStore.fetchUserDetails(newId);
      userDetailsStore.fetchUserTokenGrants(newId);
      userDetailsStore.fetchUserAccountStats(newId); // Fetch stats
    } else {
      console.error("Invalid User ID in route params for profile page");
    }
  },
  { immediate: false }
);
</script>
