interface TranslationField {
  translationKey: string | null;
  translatedText: string;
}

export function useTranslations() {
  const userStore = useUserStore();
  const translationsStore = useTranslationsStore();
  const currentLanguage = computed(() => userStore.language);

  /**
   * Gets a translated field from an entity
   * @param entity - The entity object containing both translated text and tkey fields
   * @param field - The base field name (without '_tkey' suffix)
   * @returns Both the translated text and the translation key
   */
  function getTranslatedField(entity: any, field: string): TranslationField {
    const translationKey = entity?.[`${field}_tkey`] || null;
    const translatedText = entity?.[field] || "";

    return {
      translationKey,
      translatedText,
    };
  }

  /**
   * Updates a translation for a specific entity field
   * @param key - The translation key
   * @param text - The new translated text
   */
  async function updateTranslation(key: string, text: string): Promise<any> {
    if (!key) return;

    const authStore = useAuthStore();
    try {
      const response = await authStore.apiCall("/translations", {
        method: "PUT",
        query: {
          key,
          lang: currentLanguage.value,
        },
        body: {
          text,
        },
      });
      return response;
    } catch (error) {
      console.error("Error updating translation:", error);
      throw error;
    }
  }

  /**
   * Updates multiple translations at once using the new batch API
   * @param updates - Array of objects containing key and text
   */
  async function batchUpdateTranslations(updates: Array<{ key: string; text: string }>): Promise<any> {
    if (!updates || updates.length === 0) return;

    const batchData = {
      updates: updates.map((update) => ({
        key: update.key,
        text: update.text,
        lang: currentLanguage.value,
      })),
    };

    return await translationsStore.batchUpdateTranslations(batchData);
  }

  /**
   * Updates multiple translations at once (legacy method)
   * @param updates - Array of objects containing key and text
   */
  async function legacyBatchUpdateTranslations(updates: Array<{ key: string; text: string }>): Promise<any> {
    if (!updates || updates.length === 0) return;

    const authStore = useAuthStore();
    try {
      const response = await authStore.apiCall("/translations/batch", {
        method: "PUT",
        body: {
          updates: updates.map((update) => ({
            key: update.key,
            text: update.text,
            lang: currentLanguage.value,
          })),
        },
      });
      return response;
    } catch (error) {
      console.error("Error batch updating translations:", error);
      throw error;
    }
  }

  /**
   * Creates a new translation
   * @param key - The translation key
   * @param text - The translated text
   * @param lang - Optional language (defaults to current language)
   */
  async function createTranslation(key: string, text: string, lang?: string): Promise<any> {
    if (!key) return;

    return await translationsStore.createTranslation({
      key,
      text,
      lang: lang || currentLanguage.value,
    });
  }

  /**
   * Deletes a translation
   * @param key - The translation key
   * @param lang - Optional language (defaults to current language)
   */
  async function deleteTranslation(key: string, lang?: string): Promise<any> {
    if (!key) return;

    return await translationsStore.deleteTranslation(key, lang || currentLanguage.value);
  }

  return {
    currentLanguage,
    getTranslatedField,
    updateTranslation,
    batchUpdateTranslations,
    legacyBatchUpdateTranslations,
    createTranslation,
    deleteTranslation,
  };
}
