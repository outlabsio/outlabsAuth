<template>
  <div class="language-selector">
    <UDropdownMenu :items="languageItems">
      <UButton color="neutral" variant="ghost" size="sm" class="flex items-center gap-2">
        <span class="text-lg">{{ getLanguageFlag(currentLanguage) }}</span>
        <span>{{ selectedLanguageName }}</span>
      </UButton>
    </UDropdownMenu>
  </div>
</template>

<script setup lang="ts">
interface Language {
  code: string;
  name: string;
}

// Props
const props = defineProps<{
  value: string;
}>();

// Available languages - easily extendable
const availableLanguages = ref<Language[]>([
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
]);

const emit = defineEmits<{
  change: [value: string];
}>();

// Use the prop value as the current language
const currentLanguage = computed(() => props.value || "en");

// Get flag emoji for language code
const getLanguageFlag = (code: string): string => {
  const flags: Record<string, string> = {
    en: "🇬🇧",
    es: "🇪🇸",
    // Add more language flags as needed
  };

  return flags[code] || "🌐";
};

// Get the name of the selected language
const selectedLanguageName = computed(() => {
  const language = availableLanguages.value.find((lang) => lang.code === currentLanguage.value);
  return language ? language.name : "English";
});

// Create dropdown menu items with the language options
const languageItems = computed(() => {
  return availableLanguages.value.map((language) => ({
    label: language.name,
    icon: getLanguageFlag(language.code),
    active: currentLanguage.value === language.code,
    onSelect: () => {
      if (currentLanguage.value !== language.code) {
        emit("change", language.code);
      }
    },
  }));
});
</script>

<style scoped>
.language-selector {
  min-width: 120px;
}
</style>
