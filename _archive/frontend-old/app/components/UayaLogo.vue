<script setup lang="ts">
defineProps<{
  collapsed?: boolean;
}>();

const colorMode = useColorMode();
const isDark = computed(() => colorMode.value === "dark");
</script>

<template>
  <div class="flex items-center gap-2" :class="{ 'px-2 py-2': !collapsed }">
    <div v-if="!collapsed" class="flex items-center gap-2 bg-primary-500 rounded-full p-2">
      <img src="/uayaSymbol.svg" alt="Uaya Symbol" class="h-6 w-6 invert" :class="{ 'dark:invert-0': isDark }" />
    </div>

    <img v-else src="/uayaSymbol.svg" alt="Uaya Symbol" class="h-7 w-7" :class="{ 'dark:invert': isDark }" />

    <img v-if="!collapsed" src="/uayaWord.svg" alt="Uaya" class="h-5 mt-3" />
  </div>
</template>
