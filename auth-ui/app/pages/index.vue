<script setup lang="ts">
// Redirect to dashboard (middleware will handle auth check)
definePageMeta({
  middleware: [
    function () {
      return navigateTo('/dashboard')
    }
  ]
})
</script>

<template>
  <div />
</template>
