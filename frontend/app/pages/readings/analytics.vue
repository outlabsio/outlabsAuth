<script setup lang="ts">
// Simple coming soon page - no complex analytics logic needed
</script>

<template>
  <div class="flex items-center justify-center min-h-[60vh]">
    <div class="text-center space-y-8 max-w-lg mx-auto">
      <!-- Icon -->
      <div class="flex justify-center">
        <div class="w-24 h-24 bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-2xl flex items-center justify-center">
          <UIcon name="i-lucide-bar-chart-3" class="w-12 h-12 text-blue-600 dark:text-blue-400" />
        </div>
      </div>

      <!-- Content -->
      <div class="space-y-4">
        <h2 class="text-3xl font-bold text-gray-900 dark:text-white">Analytics Coming Soon</h2>
        <p class="text-lg text-gray-600 dark:text-gray-400 leading-relaxed">
          We're working on comprehensive analytics and insights for your readings data. Check back soon for detailed charts, trends, and statistics.
        </p>
      </div>

      <!-- Features preview -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-8">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="flex items-center gap-3 mb-2">
            <UIcon name="i-lucide-trending-up" class="w-5 h-5 text-green-600" />
            <span class="font-medium text-gray-900 dark:text-white">Usage Trends</span>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-400">Track reading patterns over time</p>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="flex items-center gap-3 mb-2">
            <UIcon name="i-lucide-pie-chart" class="w-5 h-5 text-blue-600" />
            <span class="font-medium text-gray-900 dark:text-white">Type Distribution</span>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-400">Breakdown by reading types</p>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="flex items-center gap-3 mb-2">
            <UIcon name="i-lucide-users" class="w-5 h-5 text-purple-600" />
            <span class="font-medium text-gray-900 dark:text-white">User Insights</span>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-400">User engagement metrics</p>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="flex items-center gap-3 mb-2">
            <UIcon name="i-lucide-activity" class="w-5 h-5 text-orange-600" />
            <span class="font-medium text-gray-900 dark:text-white">Performance</span>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-400">System performance stats</p>
        </div>
      </div>

      <!-- CTA -->
      <div class="pt-6">
        <UBadge color="primary" variant="subtle" size="lg" class="px-4 py-2">
          <UIcon name="i-lucide-clock" class="w-4 h-4 mr-2" />
          Feature in Development
        </UBadge>
      </div>
    </div>
  </div>
</template>
