<template>
  <UDashboardPage class="w-full">
    <UDashboardPanel class="flex flex-col h-full w-full max-w-none">
      <UDashboardNavbar title="Translation Management" class="w-full">
        <template #right>
          <div class="flex items-center gap-3">
            <UButton icon="i-lucide-plus-circle" label="Add Translation" color="primary" @click="openCreateDrawer" />
            <UButton icon="i-lucide-upload" label="Bulk Import" variant="outline" @click="showBulkImportModal = true" />
            <UButton icon="i-lucide-download" label="Export" variant="outline" @click="exportTranslations" />
          </div>
        </template>
      </UDashboardNavbar>

      <div class="flex-1 overflow-auto p-6 w-full" style="max-height: calc(100vh - 64px)">
        <div v-if="translationsStore.loading && currentView === 'dashboard'" class="flex items-center justify-center h-full">
          <UIcon name="i-heroicons-arrow-path" class="animate-spin text-4xl text-primary" />
        </div>

        <div v-else-if="translationsStore.error" class="p-4 text-red-500">
          <p>Error loading translations: {{ translationsStore.error.message || translationsStore.error }}</p>
        </div>

        <div v-else class="w-full space-y-6">
          <!-- View Selector -->
          <div class="flex items-center justify-between mb-6">
            <UTabs
              :items="[
                { label: 'Dashboard', slot: 'dashboard', icon: 'i-lucide-bar-chart-3' },
                { label: 'By Key', slot: 'keys', icon: 'i-lucide-key' },
                { label: 'By Language', slot: 'languages', icon: 'i-lucide-globe' },
                { label: 'Search', slot: 'search', icon: 'i-lucide-search' },
              ]"
              v-model="currentViewIndex"
              @change="onViewChange"
              class="w-full"
            />
          </div>

          <!-- Dashboard View -->
          <div v-show="currentView === 'dashboard'" class="space-y-6">
            <!-- Stats Overview -->
            <div v-if="translationsStore.stats" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <UCard class="p-6">
                <div class="flex items-center">
                  <UIcon name="i-lucide-key" class="w-8 h-8 text-primary mr-4" />
                  <div>
                    <h3 class="text-2xl font-bold">{{ translationsStore.stats.totalKeys }}</h3>
                    <p class="text-sm text-gray-500">Total Translation Keys</p>
                  </div>
                </div>
              </UCard>

              <UCard class="p-6">
                <div class="flex items-center">
                  <UIcon name="i-lucide-file-text" class="w-8 h-8 text-green-500 mr-4" />
                  <div>
                    <h3 class="text-2xl font-bold">{{ translationsStore.stats.totalTranslations }}</h3>
                    <p class="text-sm text-gray-500">Total Translations</p>
                  </div>
                </div>
              </UCard>

              <UCard class="p-6">
                <div class="flex items-center">
                  <UIcon name="i-lucide-globe" class="w-8 h-8 text-blue-500 mr-4" />
                  <div>
                    <h3 class="text-2xl font-bold">{{ translationsStore.stats.languages.length }}</h3>
                    <p class="text-sm text-gray-500">Languages</p>
                  </div>
                </div>
              </UCard>

              <UCard class="p-6">
                <div class="flex items-center">
                  <UIcon name="i-lucide-trending-up" class="w-8 h-8 text-orange-500 mr-4" />
                  <div>
                    <h3 class="text-2xl font-bold">{{ getAverageCoverage() }}%</h3>
                    <p class="text-sm text-gray-500">Avg. Coverage</p>
                  </div>
                </div>
              </UCard>
            </div>

            <!-- Languages Overview -->
            <UCard>
              <template #header>
                <h3 class="text-lg font-semibold">Translation Coverage by Language</h3>
              </template>
              <div v-if="translationsStore.stats" class="space-y-4">
                <div v-for="language in translationsStore.stats.languages" :key="language" class="flex items-center justify-between">
                  <div class="flex items-center space-x-3">
                    <UBadge :label="language.toUpperCase()" color="primary" size="sm" />
                    <span class="font-medium">{{ getLanguageName(language) }}</span>
                  </div>
                  <div class="flex items-center space-x-3">
                    <span class="text-sm text-gray-500"> {{ translationsStore.stats.coverageByLanguage[language] }} / {{ translationsStore.stats.totalKeys }} </span>
                    <UProgress :value="getLanguageCoveragePercentage(language)" :max="100" class="w-32" color="primary" />
                    <span class="text-sm font-medium">{{ getLanguageCoveragePercentage(language) }}%</span>
                  </div>
                </div>
              </div>
            </UCard>

            <!-- Key Prefixes Overview -->
            <UCard>
              <template #header>
                <h3 class="text-lg font-semibold">Translation Keys by Category</h3>
              </template>
              <div v-if="translationsStore.stats" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div v-for="(count, prefix) in translationsStore.stats.keysByPrefix" :key="prefix" class="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                  <div class="flex items-center justify-between">
                    <div>
                      <h4 class="font-medium capitalize">{{ prefix }}</h4>
                      <p class="text-sm text-gray-500">{{ getPrefixDescription(prefix) }}</p>
                    </div>
                    <div class="text-right">
                      <span class="text-lg font-bold text-primary">{{ count }}</span>
                      <p class="text-xs text-gray-500">keys</p>
                    </div>
                  </div>
                </div>
              </div>
            </UCard>
          </div>

          <!-- Keys View -->
          <div v-show="currentView === 'keys'" class="space-y-6">
            <div class="flex items-center space-x-4 mb-6">
              <UInput v-model="keyFilter" placeholder="Filter by key..." icon="i-lucide-search" class="flex-1" @input="filterKeys" />
              <USelect v-model="selectedKeyPrefix" :options="keyPrefixOptions" placeholder="Filter by prefix" @change="filterKeys" />
            </div>

            <div v-if="filteredKeys.length === 0" class="text-center py-12">
              <UIcon name="i-lucide-key" class="text-6xl text-gray-400 mb-4" />
              <p class="text-xl text-gray-500">No translation keys found</p>
              <p class="text-gray-400">Try adjusting your filters or create a new translation</p>
            </div>

            <div v-else class="space-y-4">
              <UCard v-for="key in paginatedKeys" :key="key" class="cursor-pointer hover:shadow-lg transition-shadow" @click="openKeyEditDrawer(key)">
                <div class="flex items-center justify-between">
                  <div class="flex-1 min-w-0">
                    <h4 class="font-medium text-gray-900 dark:text-white truncate">{{ key }}</h4>
                    <p class="text-sm text-gray-500">{{ getKeyDescription(key) }}</p>
                  </div>
                  <div class="flex items-center space-x-4">
                    <div class="flex space-x-1">
                      <UBadge v-for="lang in getKeyLanguages(key)" :key="lang" :label="lang.toUpperCase()" color="primary" size="xs" variant="soft" />
                    </div>
                    <UIcon name="i-lucide-chevron-right" class="w-5 h-5 text-gray-400" />
                  </div>
                </div>
              </UCard>

              <!-- Pagination -->
              <div v-if="totalKeyPages > 1" class="flex justify-center">
                <UPagination v-model="currentKeyPage" :page-count="totalKeyPages" :total="filteredKeys.length" />
              </div>
            </div>
          </div>

          <!-- Languages View -->
          <div v-show="currentView === 'languages'" class="space-y-6">
            <div class="flex items-center space-x-4 mb-6">
              <USelect v-model="selectedLanguage" :options="languageOptions" placeholder="Select language" @change="loadLanguageTranslations" />
              <UInput v-model="languageFilter" placeholder="Filter translations..." icon="i-lucide-search" class="flex-1" @input="filterLanguageTranslations" />
            </div>

            <div v-if="selectedLanguage && filteredLanguageTranslations.length === 0" class="text-center py-12">
              <UIcon name="i-lucide-globe" class="text-6xl text-gray-400 mb-4" />
              <p class="text-xl text-gray-500">No translations found for {{ getLanguageName(selectedLanguage) }}</p>
              <p class="text-gray-400">Start by adding some translations for this language</p>
            </div>

            <div v-else-if="selectedLanguage" class="space-y-4">
              <div v-for="translation in paginatedLanguageTranslations" :key="`${translation.key}-${translation.lang}`" class="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <div class="flex items-start justify-between">
                  <div class="flex-1 min-w-0 space-y-2">
                    <div class="flex items-center space-x-2">
                      <code class="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">{{ translation.key }}</code>
                      <UBadge :label="translation.lang.toUpperCase()" color="primary" size="xs" />
                    </div>
                    <div class="relative group">
                      <p class="text-sm text-gray-900 dark:text-white break-words">{{ translation.text }}</p>
                      <UButton
                        icon="i-lucide-edit-3"
                        size="xs"
                        variant="ghost"
                        class="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        @click="openEditDrawer(translation)"
                      />
                    </div>
                  </div>
                  <UButton icon="i-lucide-trash-2" color="error" variant="ghost" size="sm" @click="confirmDeleteTranslation(translation.key, translation.lang)" />
                </div>
              </div>

              <!-- Pagination -->
              <div v-if="totalLanguagePages > 1" class="flex justify-center">
                <UPagination v-model="currentLanguagePage" :page-count="totalLanguagePages" :total="filteredLanguageTranslations.length" />
              </div>
            </div>
          </div>

          <!-- Search View -->
          <div v-show="currentView === 'search'" class="space-y-6">
            <UCard>
              <template #header>
                <h3 class="text-lg font-semibold">Advanced Search</h3>
              </template>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UFormField label="Search in keys" name="searchKey">
                  <UInput v-model="searchForm.key" placeholder="e.g. hexagram:1" />
                </UFormField>
                <UFormField label="Search in text" name="searchText">
                  <UInput v-model="searchForm.search" placeholder="Search content..." />
                </UFormField>
                <UFormField label="Language" name="searchLang">
                  <USelect v-model="searchForm.lang" :options="languageOptions" placeholder="Any language" />
                </UFormField>
                <UFormField label="Key prefix" name="searchPrefix">
                  <USelect v-model="searchForm.prefix" :options="keyPrefixOptions" placeholder="Any prefix" />
                </UFormField>
              </div>
              <div class="flex justify-end mt-4 space-x-2">
                <UButton variant="outline" @click="clearSearch">Clear</UButton>
                <UButton @click="performSearch" :loading="translationsStore.searchLoading">Search</UButton>
              </div>
            </UCard>

            <div v-if="translationsStore.searchResults.length > 0" class="space-y-4">
              <h4 class="text-lg font-semibold">Search Results ({{ translationsStore.searchResults.length }})</h4>
              <div v-for="result in translationsStore.searchResults" :key="`${result.key}-${result.lang}`" class="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <div class="flex items-start justify-between">
                  <div class="flex-1 min-w-0 space-y-2">
                    <div class="flex items-center space-x-2">
                      <code class="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">{{ result.key }}</code>
                      <UBadge :label="result.lang.toUpperCase()" color="primary" size="xs" />
                    </div>
                    <p class="text-sm text-gray-900 dark:text-white break-words">{{ result.text }}</p>
                  </div>
                  <div class="flex space-x-2">
                    <UButton icon="i-lucide-edit-3" variant="ghost" size="sm" @click="openEditDrawer(result)" />
                    <UButton icon="i-lucide-trash-2" color="error" variant="ghost" size="sm" @click="confirmDeleteTranslation(result.key, result.lang)" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </UDashboardPanel>

    <!-- Create/Edit Translation Drawer -->
    <UDrawer v-model:open="isDrawerOpen" direction="right" class="max-w-2xl" handle-only :ui="{ content: 'w-full max-w-2xl' }">
      <template #header>
        <div class="flex justify-between items-center w-full">
          <div>
            <h3 class="text-xl font-bold">
              {{ isCreating ? "Create Translation" : "Edit Translation" }}
            </h3>
            <p class="text-sm text-gray-500">
              {{ isCreating ? "Add a new translation entry" : `Editing: ${selectedTranslation?.key}` }}
            </p>
          </div>
          <UButton icon="i-lucide-save" @click="saveTranslation" :loading="saveLoading" color="primary" :label="isCreating ? 'Create' : 'Save'" />
        </div>
      </template>

      <template #body>
        <div class="p-6">
          <UForm :state="editForm" class="space-y-6">
            <UFormField label="Translation Key" name="key" required>
              <UInput v-model="editForm.key" placeholder="e.g. hexagram:1:name" :disabled="!isCreating" icon="i-lucide-key" :state="validateKey(editForm.key) ? undefined : 'error'" />
              <template #help>
                <div class="text-xs space-y-1">
                  <p>Format: entity_type:entity_identifier:[sub_entity]:field_name</p>
                  <p class="text-gray-500">Example: hexagram:1:line:1:description</p>
                </div>
              </template>
            </UFormField>

            <UFormField label="Language" name="lang" required>
              <USelect v-model="editForm.lang" :options="languageOptions" placeholder="Select language" :disabled="!isCreating" />
            </UFormField>

            <UFormField label="Translation Text" name="text" required>
              <UTextarea v-model="editForm.text" placeholder="Enter translation text..." rows="6" resize />
            </UFormField>

            <!-- Key breakdown display -->
            <div v-if="editForm.key" class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
              <h5 class="text-sm font-medium mb-2">Key Structure:</h5>
              <div class="text-xs space-y-1">
                <div v-for="(part, index) in editForm.key.split(':')" :key="index" class="flex">
                  <span class="w-16 text-gray-500">{{ getKeyPartLabel(index) }}:</span>
                  <code class="bg-white dark:bg-gray-700 px-1 rounded">{{ part }}</code>
                </div>
              </div>
            </div>
          </UForm>
        </div>
      </template>
    </UDrawer>

    <!-- Key Detail Drawer -->
    <UDrawer v-model:open="isKeyDrawerOpen" direction="right" class="max-w-3xl" handle-only :ui="{ content: 'w-full max-w-3xl' }">
      <template #header>
        <div class="flex justify-between items-center w-full">
          <div>
            <h3 class="text-xl font-bold">Translation Key Details</h3>
            <code class="text-sm text-gray-500">{{ selectedKey }}</code>
          </div>
          <UButton icon="i-lucide-plus" label="Add Language" @click="addLanguageForKey" color="primary" />
        </div>
      </template>

      <template #body>
        <div v-if="selectedKey" class="p-6">
          <div class="space-y-6">
            <div v-for="translation in getKeyTranslations(selectedKey)" :key="translation.lang" class="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
              <div class="flex items-start justify-between mb-2">
                <div class="flex items-center space-x-2">
                  <UBadge :label="translation.lang.toUpperCase()" color="primary" />
                  <span class="font-medium">{{ getLanguageName(translation.lang) }}</span>
                </div>
                <div class="flex space-x-2">
                  <UButton icon="i-lucide-edit-3" variant="ghost" size="sm" @click="openEditDrawer(translation)" />
                  <UButton icon="i-lucide-trash-2" color="error" variant="ghost" size="sm" @click="confirmDeleteTranslation(translation.key, translation.lang)" />
                </div>
              </div>
              <p class="text-sm break-words">{{ translation.text }}</p>
            </div>

            <div v-if="getKeyTranslations(selectedKey).length === 0" class="text-center py-8">
              <UIcon name="i-lucide-globe" class="text-4xl text-gray-400 mb-4" />
              <p class="text-gray-500">No translations for this key yet</p>
              <UButton icon="i-lucide-plus" label="Add First Translation" @click="addLanguageForKey" class="mt-4" />
            </div>
          </div>
        </div>
      </template>
    </UDrawer>

    <!-- Bulk Import Modal -->
    <UModal v-model="showBulkImportModal">
      <div class="p-6">
        <h3 class="text-lg font-semibold mb-4">Bulk Import Translations</h3>

        <UFormField label="Import Format" name="format" class="mb-4">
          <USelect
            v-model="bulkImportFormat"
            :options="[
              { label: 'CSV', value: 'CSV' },
              { label: 'JSON', value: 'JSON' },
            ]"
          />
        </UFormField>

        <UFormField label="Upload File" name="file" class="mb-4">
          <input
            type="file"
            :accept="bulkImportFormat === 'CSV' ? '.csv' : '.json'"
            @change="handleFileUpload"
            class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
          />
        </UFormField>

        <div v-if="bulkImportFormat === 'CSV'" class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 mb-4">
          <h5 class="text-sm font-medium mb-2">CSV Format:</h5>
          <code class="text-xs">key,lang,text</code>
          <p class="text-xs text-gray-500 mt-1">Header row required. One translation per row.</p>
        </div>

        <div class="flex justify-end space-x-3">
          <UButton variant="outline" @click="showBulkImportModal = false">Cancel</UButton>
          <UButton @click="performBulkImport" :loading="bulkImportLoading" :disabled="!bulkImportFile"> Import </UButton>
        </div>
      </div>
    </UModal>

    <!-- Delete Confirmation Modal -->
    <UModal v-model="showDeleteModal">
      <div class="p-6">
        <div class="flex items-center space-x-4 mb-4">
          <UIcon name="i-lucide-alert-triangle" class="text-red-500 text-2xl" />
          <div>
            <h3 class="text-lg font-semibold">Delete Translation</h3>
            <p class="text-sm text-gray-500">This action cannot be undone</p>
          </div>
        </div>

        <p class="mb-6">
          Are you sure you want to delete the <strong>{{ deleteTarget?.lang }}</strong> translation for <code class="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">{{ deleteTarget?.key }}</code
          >?
        </p>

        <div class="flex justify-end space-x-3">
          <UButton variant="outline" @click="showDeleteModal = false">Cancel</UButton>
          <UButton color="error" @click="deleteTranslation" :loading="deleteLoading" icon="i-lucide-trash-2"> Delete Translation </UButton>
        </div>
      </div>
    </UModal>
  </UDashboardPage>
</template>

<script setup lang="ts">
interface Translation {
  key: string;
  lang: string;
  text: string;
  created_at?: string;
  updated_at?: string;
}

interface SearchForm {
  key: string;
  lang: string;
  prefix: string;
  search: string;
}

interface EditForm {
  key: string;
  lang: string;
  text: string;
}

definePageMeta({
  title: "Translation Management",
  layout: "default",
});

const translationsStore = useTranslationsStore();
const userStore = useUserStore();

// View management
const currentViewIndex = ref(0);
const currentView = computed(() => {
  const views = ["dashboard", "keys", "languages", "search"];
  return views[currentViewIndex.value] || "dashboard";
});

// Drawer states
const isDrawerOpen = ref(false);
const isKeyDrawerOpen = ref(false);
const isCreating = ref(false);
const selectedTranslation = ref<Translation | null>(null);
const selectedKey = ref<string | null>(null);

// Form states
const editForm = ref<EditForm>({
  key: "",
  lang: "",
  text: "",
});
const searchForm = ref<SearchForm>({
  key: "",
  lang: "",
  prefix: "",
  search: "",
});

// Loading states
const saveLoading = ref(false);
const deleteLoading = ref(false);

// Delete confirmation
const showDeleteModal = ref(false);
const deleteTarget = ref<{ key: string; lang: string } | null>(null);

// Bulk import
const showBulkImportModal = ref(false);
const bulkImportFormat = ref("CSV");
const bulkImportFile = ref<File | null>(null);
const bulkImportLoading = ref(false);

// Keys view
const keyFilter = ref("");
const selectedKeyPrefix = ref("");
const currentKeyPage = ref(1);
const keysPerPage = 20;

// Languages view
const selectedLanguage = ref("");
const languageFilter = ref("");
const currentLanguagePage = ref(1);
const translationsPerPage = 20;

// Computed properties
const keyPrefixOptions = computed(() => {
  if (!translationsStore.stats) return [];
  return [
    { label: "All Prefixes", value: "" },
    ...Object.keys(translationsStore.stats.keysByPrefix).map((prefix) => ({
      label: `${prefix} (${translationsStore.stats!.keysByPrefix[prefix]})`,
      value: prefix,
    })),
  ];
});

const languageOptions = computed(() => {
  return [
    { label: "All Languages", value: "" },
    ...translationsStore.allLanguages.map((lang) => ({
      label: `${getLanguageName(lang)} (${lang})`,
      value: lang,
    })),
  ];
});

const filteredKeys = computed(() => {
  let keys = translationsStore.allKeys;

  if (keyFilter.value) {
    keys = keys.filter((key) => key.toLowerCase().includes(keyFilter.value.toLowerCase()));
  }

  if (selectedKeyPrefix.value) {
    keys = keys.filter((key) => key.startsWith(selectedKeyPrefix.value + ":"));
  }

  return keys.sort();
});

const paginatedKeys = computed(() => {
  const start = (currentKeyPage.value - 1) * keysPerPage;
  const end = start + keysPerPage;
  return filteredKeys.value.slice(start, end);
});

const totalKeyPages = computed(() => {
  return Math.ceil(filteredKeys.value.length / keysPerPage);
});

const filteredLanguageTranslations = computed(() => {
  if (!selectedLanguage.value) return [];

  let translations = translationsStore.translationsByLanguage[selectedLanguage.value] || [];

  if (languageFilter.value) {
    const filter = languageFilter.value.toLowerCase();
    translations = translations.filter((t) => t.key.toLowerCase().includes(filter) || t.text.toLowerCase().includes(filter));
  }

  return translations.sort((a, b) => a.key.localeCompare(b.key));
});

const paginatedLanguageTranslations = computed(() => {
  const start = (currentLanguagePage.value - 1) * translationsPerPage;
  const end = start + translationsPerPage;
  return filteredLanguageTranslations.value.slice(start, end);
});

const totalLanguagePages = computed(() => {
  return Math.ceil(filteredLanguageTranslations.value.length / translationsPerPage);
});

// Helper functions
const getLanguageName = (langCode: string) => {
  const names: Record<string, string> = {
    en: "English",
    es: "Spanish",
    fr: "French",
    de: "German",
    zh: "Chinese",
    ja: "Japanese",
    ko: "Korean",
  };
  return names[langCode] || langCode.toUpperCase();
};

const getPrefixDescription = (prefix: string) => {
  const descriptions: Record<string, string> = {
    hexagram: "I Ching hexagrams",
    trigram: "I Ching trigrams",
    interpretation: "Text interpretations",
    author: "Author information",
    element: "Five elements",
    line_position: "Line positions (1-6)",
    season: "Four seasons",
  };
  return descriptions[prefix] || "General translations";
};

const getKeyDescription = (key: string) => {
  const parts = key.split(":");
  if (parts.length >= 2) {
    return `${getPrefixDescription(parts[0])} - ${parts[1]}`;
  }
  return key;
};

const getKeyLanguages = (key: string) => {
  const translations = translationsStore.translationsByKey[key] || [];
  return translations.map((t) => t.lang);
};

const getKeyTranslations = (key: string) => {
  return translationsStore.translationsByKey[key] || [];
};

const getAverageCoverage = () => {
  if (!translationsStore.stats || translationsStore.stats.languages.length === 0) return 0;
  const statsRef = translationsStore.stats;
  const total = Object.values(statsRef.coverageByLanguage).reduce((sum, count) => sum + count, 0);
  const average = total / (statsRef.languages.length * statsRef.totalKeys);
  return Math.round(average * 100);
};

const getLanguageCoveragePercentage = (lang: string) => {
  if (!translationsStore.stats) return 0;
  const statsRef = translationsStore.stats;
  const coverage = statsRef.coverageByLanguage[lang] || 0;
  const percentage = (coverage / statsRef.totalKeys) * 100;
  return Math.round(percentage);
};

const validateKey = (key: string) => {
  if (!key) return false;
  // Basic validation for key format
  const parts = key.split(":");
  return parts.length >= 2 && parts.every((part) => part.length > 0);
};

const getKeyPartLabel = (index: number) => {
  const labels = ["Type", "ID", "Sub-Type", "Sub-ID", "Field"];
  return labels[index] || `Part ${index + 1}`;
};

// Actions
const onViewChange = (index: number) => {
  currentViewIndex.value = index;

  // Load data for specific views
  if (currentView.value === "keys" && translationsStore.allKeys.length === 0) {
    translationsStore.fetchAllKeys();
  }
  if (currentView.value === "languages" && translationsStore.allLanguages.length === 0) {
    translationsStore.fetchAllLanguages();
  }
};

const openCreateDrawer = () => {
  isCreating.value = true;
  selectedTranslation.value = null;
  editForm.value = {
    key: "",
    lang: userStore.language || "en",
    text: "",
  };
  isDrawerOpen.value = true;
};

const openEditDrawer = (translation: Translation) => {
  isCreating.value = false;
  selectedTranslation.value = translation;
  editForm.value = {
    key: translation.key,
    lang: translation.lang,
    text: translation.text,
  };
  isDrawerOpen.value = true;
};

const openKeyEditDrawer = async (key: string) => {
  selectedKey.value = key;
  // Load translations for this key if not already loaded
  await translationsStore.fetchTranslationsByKey(key);
  isKeyDrawerOpen.value = true;
};

const addLanguageForKey = () => {
  if (!selectedKey.value) return;
  isCreating.value = true;
  selectedTranslation.value = null;
  editForm.value = {
    key: selectedKey.value,
    lang: "",
    text: "",
  };
  isKeyDrawerOpen.value = false;
  isDrawerOpen.value = true;
};

const saveTranslation = async () => {
  if (!validateKey(editForm.value.key) || !editForm.value.lang || !editForm.value.text) {
    return;
  }

  try {
    saveLoading.value = true;

    if (isCreating.value) {
      await translationsStore.createTranslation(editForm.value);
    } else {
      await translationsStore.updateTranslation(editForm.value);
    }

    isDrawerOpen.value = false;

    // Refresh stats and data
    await translationsStore.generateStats();
  } catch (error) {
    console.error("Error saving translation:", error);
  } finally {
    saveLoading.value = false;
  }
};

const confirmDeleteTranslation = (key: string, lang: string) => {
  deleteTarget.value = { key, lang };
  showDeleteModal.value = true;
};

const deleteTranslation = async () => {
  if (!deleteTarget.value) return;

  try {
    deleteLoading.value = true;
    await translationsStore.deleteTranslation(deleteTarget.value.key, deleteTarget.value.lang);
    showDeleteModal.value = false;

    // Refresh stats
    await translationsStore.generateStats();
  } catch (error) {
    console.error("Error deleting translation:", error);
  } finally {
    deleteLoading.value = false;
  }
};

const filterKeys = () => {
  currentKeyPage.value = 1;
};

const loadLanguageTranslations = async () => {
  if (!selectedLanguage.value) return;
  await translationsStore.fetchTranslationsByLanguage(selectedLanguage.value);
  currentLanguagePage.value = 1;
};

const filterLanguageTranslations = () => {
  currentLanguagePage.value = 1;
};

const performSearch = async () => {
  const filters = {
    key: searchForm.value.key || undefined,
    lang: searchForm.value.lang || undefined,
    prefix: searchForm.value.prefix || undefined,
    search: searchForm.value.search || undefined,
  };

  // Remove undefined values
  const cleanFilters = Object.fromEntries(Object.entries(filters).filter(([_, value]) => value !== undefined));

  await translationsStore.searchTranslations(cleanFilters);
};

const clearSearch = () => {
  searchForm.value = {
    key: "",
    lang: "",
    prefix: "",
    search: "",
  };
  translationsStore.clearSearch();
};

const handleFileUpload = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (file) {
    bulkImportFile.value = file;
  }
};

const performBulkImport = async () => {
  if (!bulkImportFile.value) return;

  try {
    bulkImportLoading.value = true;

    const text = await bulkImportFile.value.text();
    let translations: any[] = [];

    if (bulkImportFormat.value === "CSV") {
      const lines = text.split("\n");
      const headers = lines[0].split(",").map((h) => h.trim());

      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(",").map((v) => v.trim());
        if (values.length >= 3) {
          translations.push({
            key: values[0],
            lang: values[1],
            text: values[2],
          });
        }
      }
    } else {
      translations = JSON.parse(text);
    }

    await translationsStore.bulkCreateTranslations({ translations });

    showBulkImportModal.value = false;
    bulkImportFile.value = null;

    // Refresh data
    await translationsStore.loadInitialData();
  } catch (error) {
    console.error("Error importing translations:", error);
  } finally {
    bulkImportLoading.value = false;
  }
};

const exportTranslations = () => {
  const data = translationsStore.translations.map((t) => ({
    key: t.key,
    lang: t.lang,
    text: t.text,
  }));

  const csvContent = "key,lang,text\n" + data.map((row) => `"${row.key}","${row.lang}","${row.text.replace(/"/g, '""')}"`).join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);
  link.setAttribute("href", url);
  link.setAttribute("download", "translations.csv");
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

// Initialize data
onMounted(async () => {
  await translationsStore.loadInitialData();
});
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
