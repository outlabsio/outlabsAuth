<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

// Redirect to dashboard
await navigateTo('/dashboard')
</script>

<template>
  <div>
    <!-- Redirecting to dashboard -->
  </div>
</template>