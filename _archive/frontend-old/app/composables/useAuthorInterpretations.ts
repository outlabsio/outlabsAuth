interface AuthorInterpretation {
  key: string;
  lang: string;
  text: string;
  entityType: string;
  entityId: string;
  created_at?: string;
  updated_at?: string;
}

interface InterpretationStats {
  totalInterpretations: number;
  byEntityType: Record<string, number>;
  byLanguage: Record<string, number>;
  recentlyUpdated: AuthorInterpretation[];
}

interface InterpretationFilter {
  entityType?: string;
  search?: string;
  lang?: string;
}

export const useAuthorInterpretations = () => {
  const authStore = useAuthStore();
  const authorsStore = useAuthorsStore();
  const translationsStore = useTranslationsStore();
  const userStore = useUserStore();
  const toast = useToast();

  const loading = ref(false);
  const interpretations = ref<AuthorInterpretation[]>([]);
  const stats = ref<InterpretationStats | null>(null);
  const groupedInterpretations = ref<any>(null);

  /**
   * Parse interpretation key to extract entity information
   */
  const parseInterpretationKey = (key: string) => {
    const parts = key.split(":");
    if (parts.length >= 5 && parts[0] === "interpretation") {
      return {
        authorId: parts[1],
        entityType: parts[2],
        entityId: parts[3],
        property: parts[4], // Usually 'text'
      };
    }
    return null;
  };

  /**
   * Fetch all interpretations by a specific author using the new API
   */
  const fetchAuthorInterpretations = async (authorIdentifier: string, filters: InterpretationFilter = {}) => {
    try {
      loading.value = true;

      const options = {
        entity_type: filters.entityType,
        lang: filters.lang || userStore.language || "en",
        include_metadata: true,
        page_size: 100, // Get more results per page
      };

      const response = await authorsStore.fetchAuthorInterpretations(authorIdentifier, options);

      if (response && "interpretations" in response) {
        // Convert API response to our local format
        interpretations.value = response.interpretations.map((interp) => ({
          key: interp.key,
          lang: interp.lang,
          text: interp.text,
          entityType: interp.entity_type,
          entityId: interp.entity_id,
          created_at: interp.created_at,
          updated_at: interp.updated_at,
        }));

        // Generate stats from the response
        generateStatsFromResponse(response);
      } else {
        interpretations.value = [];
      }

      return interpretations.value;
    } catch (error: any) {
      console.error("Error fetching author interpretations:", error);
      // Fallback to legacy search method
      return await legacyFetchAuthorInterpretations(authorIdentifier, filters);
    } finally {
      loading.value = false;
    }
  };

  /**
   * Fetch interpretations grouped by entity using the new API
   */
  const fetchInterpretationsGroupedByEntity = async (authorIdentifier: string, filters: InterpretationFilter = {}) => {
    try {
      loading.value = true;

      const options = {
        entity_type: filters.entityType,
        lang: filters.lang || userStore.language || "en",
        group_by: "entity",
        include_metadata: true,
      };

      const response = await authorsStore.fetchAuthorInterpretations(authorIdentifier, options);

      if (response && "interpretations_by_entity" in response) {
        groupedInterpretations.value = response;
        return response;
      }

      return null;
    } catch (error: any) {
      console.error("Error fetching grouped interpretations:", error);
      toast.add({
        title: "Error Loading Grouped Interpretations",
        description: error.message || "Failed to fetch grouped interpretations",
        icon: "i-lucide-alert-circle",
        color: "error",
      });
    } finally {
      loading.value = false;
    }
  };

  /**
   * Get comprehensive statistics for author interpretations
   */
  const fetchAuthorInterpretationStats = async (authorIdentifier: string, lang?: string) => {
    try {
      loading.value = true;

      const response = await authorsStore.fetchAuthorInterpretationStats(authorIdentifier, lang);

      if (response) {
        // Convert API stats to our local format
        stats.value = {
          totalInterpretations: response.overview.total_interpretations,
          byEntityType: Object.fromEntries(Object.entries(response.by_entity_type).map(([type, data]) => [type, data.count])),
          byLanguage: Object.fromEntries(Object.entries(response.by_language).map(([lang, data]) => [lang, data.interpretations])),
          recentlyUpdated: [], // This would need to be extracted from response if available
        };
      }

      return response;
    } catch (error: any) {
      console.error("Error fetching interpretation stats:", error);
      toast.add({
        title: "Error Loading Statistics",
        description: error.message || "Failed to fetch interpretation statistics",
        icon: "i-lucide-alert-circle",
        color: "error",
      });
    } finally {
      loading.value = false;
    }
  };

  /**
   * Get language coverage for author interpretations
   */
  const fetchAuthorLanguageCoverage = async (authorIdentifier: string) => {
    try {
      loading.value = true;

      const response = await authorsStore.fetchAuthorInterpretationLanguages(authorIdentifier);
      return response;
    } catch (error: any) {
      console.error("Error fetching language coverage:", error);
      toast.add({
        title: "Error Loading Language Coverage",
        description: error.message || "Failed to fetch language coverage",
        icon: "i-lucide-alert-circle",
        color: "error",
      });
    } finally {
      loading.value = false;
    }
  };

  /**
   * Legacy implementation as fallback
   */
  const legacyFetchAuthorInterpretations = async (authorIdentifier: string, filters: InterpretationFilter = {}) => {
    try {
      // Search for translations with the interpretation prefix for this author
      const searchPrefix = `interpretation:${authorIdentifier}:`;
      const searchFilters = {
        prefix: searchPrefix,
        lang: filters.lang || userStore.language || "en",
        search: filters.search,
        interpretation_author: authorIdentifier,
        entity_type: filters.entityType,
      };

      const results = await translationsStore.searchTranslations(searchFilters);

      if (!results) {
        interpretations.value = [];
        return;
      }

      // Parse and structure the interpretations
      const parsedInterpretations: AuthorInterpretation[] = results
        .map((translation) => {
          const parsed = parseInterpretationKey(translation.key);
          if (!parsed) return null;

          return {
            key: translation.key,
            lang: translation.lang,
            text: translation.text,
            entityType: parsed.entityType,
            entityId: parsed.entityId,
            created_at: translation.created_at,
            updated_at: translation.updated_at,
          };
        })
        .filter(Boolean) as AuthorInterpretation[];

      // Filter by entity type if specified
      if (filters.entityType) {
        interpretations.value = parsedInterpretations.filter((interp) => interp.entityType === filters.entityType);
      } else {
        interpretations.value = parsedInterpretations;
      }

      // Generate stats
      generateStats();

      return interpretations.value;
    } catch (error: any) {
      console.error("Error in legacy fetch:", error);
      toast.add({
        title: "Error Loading Interpretations",
        description: error.message || "Failed to fetch author interpretations",
        icon: "i-lucide-alert-circle",
        color: "error",
      });
    }
  };

  /**
   * Generate statistics from API response
   */
  const generateStatsFromResponse = (response: any) => {
    if (response.meta) {
      stats.value = {
        totalInterpretations: response.meta.total_interpretations || response.interpretations.length,
        byEntityType: {},
        byLanguage: {},
        recentlyUpdated: [],
      };

      // Generate entity type breakdown
      interpretations.value.forEach((interp) => {
        stats.value!.byEntityType[interp.entityType] = (stats.value!.byEntityType[interp.entityType] || 0) + 1;
        stats.value!.byLanguage[interp.lang] = (stats.value!.byLanguage[interp.lang] || 0) + 1;
      });

      // Get recently updated (last 10)
      const recentlyUpdated = [...interpretations.value]
        .sort((a, b) => {
          const dateA = new Date(a.updated_at || a.created_at || 0);
          const dateB = new Date(b.updated_at || b.created_at || 0);
          return dateB.getTime() - dateA.getTime();
        })
        .slice(0, 10);

      stats.value.recentlyUpdated = recentlyUpdated;
    }
  };

  /**
   * Generate statistics for the current interpretations (legacy)
   */
  const generateStats = () => {
    const totalInterpretations = interpretations.value.length;

    const byEntityType: Record<string, number> = {};
    const byLanguage: Record<string, number> = {};

    interpretations.value.forEach((interp) => {
      byEntityType[interp.entityType] = (byEntityType[interp.entityType] || 0) + 1;
      byLanguage[interp.lang] = (byLanguage[interp.lang] || 0) + 1;
    });

    // Get recently updated (last 10)
    const recentlyUpdated = [...interpretations.value]
      .sort((a, b) => {
        const dateA = new Date(a.updated_at || a.created_at || 0);
        const dateB = new Date(b.updated_at || b.created_at || 0);
        return dateB.getTime() - dateA.getTime();
      })
      .slice(0, 10);

    stats.value = {
      totalInterpretations,
      byEntityType,
      byLanguage,
      recentlyUpdated,
    };
  };

  /**
   * Get entity type display name
   */
  const getEntityTypeDisplayName = (entityType: string): string => {
    const displayNames: Record<string, string> = {
      hexagram: "Hexagrams",
      trigram: "Trigrams",
      line: "Lines",
      line_position: "Line Positions",
      judgment: "Judgments",
      image: "Images",
      element: "Elements",
      season: "Seasons",
      direction: "Directions",
    };
    return displayNames[entityType] || entityType.charAt(0).toUpperCase() + entityType.slice(1);
  };

  /**
   * Get entity type icon
   */
  const getEntityTypeIcon = (entityType: string): string => {
    const icons: Record<string, string> = {
      hexagram: "i-lucide-hexagon",
      trigram: "i-lucide-triangle",
      line: "i-lucide-minus",
      line_position: "i-lucide-layers-3",
      judgment: "i-lucide-scale",
      image: "i-lucide-image",
      element: "i-lucide-atom",
      season: "i-lucide-calendar",
      direction: "i-lucide-compass",
    };
    return icons[entityType] || "i-lucide-file-text";
  };

  /**
   * Get entity type color
   */
  const getEntityTypeColor = (entityType: string): string => {
    const colors: Record<string, string> = {
      hexagram: "primary",
      trigram: "success",
      line: "warning",
      line_position: "info",
      judgment: "error",
      image: "purple",
      element: "orange",
      season: "green",
      direction: "blue",
    };
    return colors[entityType] || "neutral";
  };

  /**
   * Format entity ID for display
   */
  const formatEntityId = (entityType: string, entityId: string): string => {
    if (entityType === "hexagram" && /^\d+$/.test(entityId)) {
      return `Hexagram ${entityId}`;
    }
    if (entityType === "line_position" && /^\d+$/.test(entityId)) {
      return `Position ${entityId}`;
    }
    return entityId.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  };

  /**
   * Update an interpretation
   */
  const updateInterpretation = async (interpretation: AuthorInterpretation, newText: string) => {
    try {
      loading.value = true;

      const translations = useTranslations();
      await translations.updateTranslation(interpretation.key, newText);

      // Update local state
      const index = interpretations.value.findIndex((i) => i.key === interpretation.key && i.lang === interpretation.lang);
      if (index !== -1) {
        const interpretationToUpdate = interpretations.value[index];
        if (interpretationToUpdate) {
          interpretationToUpdate.text = newText;
          interpretationToUpdate.updated_at = new Date().toISOString();
        }
      }

      toast.add({
        title: "Interpretation Updated",
        description: "The interpretation has been successfully updated",
        icon: "i-lucide-check-circle",
        color: "success",
      });
    } catch (error: any) {
      console.error("Error updating interpretation:", error);
      toast.add({
        title: "Error Updating Interpretation",
        description: error.message || "Failed to update interpretation",
        icon: "i-lucide-alert-circle",
        color: "error",
      });
    } finally {
      loading.value = false;
    }
  };

  /**
   * Create a new interpretation
   */
  const createInterpretation = async (authorIdentifier: string, entityType: string, entityId: string, text: string, lang?: string) => {
    try {
      loading.value = true;

      const interpretationKey = `interpretation:${authorIdentifier}:${entityType}:${entityId}:text`;
      const language = lang || userStore.language || "en";

      const translations = useTranslations();
      await translations.updateTranslation(interpretationKey, text);

      // Add to local state
      const newInterpretation: AuthorInterpretation = {
        key: interpretationKey,
        lang: language,
        text,
        entityType,
        entityId,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      interpretations.value.push(newInterpretation);
      generateStats();

      toast.add({
        title: "Interpretation Created",
        description: "New interpretation has been successfully created",
        icon: "i-lucide-check-circle",
        color: "success",
      });

      return newInterpretation;
    } catch (error: any) {
      console.error("Error creating interpretation:", error);
      toast.add({
        title: "Error Creating Interpretation",
        description: error.message || "Failed to create interpretation",
        icon: "i-lucide-alert-circle",
        color: "error",
      });
    } finally {
      loading.value = false;
    }
  };

  /**
   * Get all available languages for a specific entity
   */
  const getAvailableLanguagesForEntity = async (authorIdentifier: string, entityType: string, entityId: string) => {
    try {
      const response = await authorsStore.getEntityLanguageVersions(authorIdentifier, entityType, entityId);

      if (response) {
        return response.languages.map((lang) => lang.lang);
      }

      return [];
    } catch (error: any) {
      console.error("Error fetching available languages:", error);
      // Fallback to legacy method
      return await legacyGetAvailableLanguagesForEntity(authorIdentifier, entityType, entityId);
    }
  };

  /**
   * Legacy method for getting available languages
   */
  const legacyGetAvailableLanguagesForEntity = async (authorIdentifier: string, entityType: string, entityId: string) => {
    try {
      // Search for all interpretations for this specific entity
      const searchPrefix = `interpretation:${authorIdentifier}:${entityType}:${entityId}:`;
      const searchFilters = {
        prefix: searchPrefix,
      };

      const results = await translationsStore.searchTranslations(searchFilters);

      if (!results) return [];

      const languages = new Set<string>();
      results.forEach((translation) => {
        languages.add(translation.lang);
      });

      return Array.from(languages);
    } catch (error: any) {
      console.error("Error fetching available languages:", error);
      return [];
    }
  };

  /**
   * Get interpretation for specific entity in a specific language
   */
  const getInterpretationForEntityInLanguage = async (authorIdentifier: string, entityType: string, entityId: string, language: string) => {
    try {
      const response = await authorsStore.getEntityLanguageVersions(authorIdentifier, entityType, entityId);

      if (response) {
        const langData = response.languages.find((l) => l.lang === language);
        if (langData) {
          // Return the first interpretation found (could be enhanced to specify property)
          const firstProperty = Object.keys(langData.interpretations)[0];
          if (firstProperty) {
            const interpretation = langData.interpretations[firstProperty];
            if (interpretation) {
              return {
                key: interpretation.key,
                lang: language,
                text: interpretation.text,
                entityType,
                entityId,
                updated_at: interpretation.updated_at,
              } as AuthorInterpretation;
            }
          }
        }
      }

      return null;
    } catch (error: any) {
      console.error("Error fetching interpretation for language:", error);
      // Fallback to legacy method
      return await legacyGetInterpretationForEntityInLanguage(authorIdentifier, entityType, entityId, language);
    }
  };

  /**
   * Legacy method for getting interpretation in specific language
   */
  const legacyGetInterpretationForEntityInLanguage = async (authorIdentifier: string, entityType: string, entityId: string, language: string) => {
    try {
      const key = `interpretation:${authorIdentifier}:${entityType}:${entityId}:text`;
      const translation = await translationsStore.fetchTranslation(key, language);

      if (!translation) return null;

      return {
        key: translation.key,
        lang: translation.lang,
        text: translation.text,
        entityType,
        entityId,
        created_at: translation.created_at,
        updated_at: translation.updated_at,
      } as AuthorInterpretation;
    } catch (error: any) {
      console.error("Error fetching interpretation for language:", error);
      return null;
    }
  };

  /**
   * Get all available entity types for a specific author
   */
  const getAvailableEntityTypes = async (authorIdentifier: string) => {
    try {
      const response = await authorsStore.fetchAuthorInterpretations(authorIdentifier, {
        group_by: "entity",
        include_metadata: true,
      });

      if (response && "interpretations_by_entity" in response) {
        // Extract entity types from the grouped response
        const entityTypes = Object.keys(response.interpretations_by_entity);

        // Return structured data for select inputs
        return entityTypes.map((entityType) => ({
          value: entityType,
          label: getEntityTypeDisplayName(entityType),
          icon: getEntityTypeIcon(entityType),
          color: getEntityTypeColor(entityType),
          count: response.summary?.by_entity_type?.[entityType] || 0,
        }));
      }

      return [];
    } catch (error: any) {
      console.error("Error fetching available entity types:", error);
      return [];
    }
  };

  /**
   * Get all available entities for a specific author and entity type
   */
  const getAvailableEntities = async (authorIdentifier: string, entityType?: string) => {
    try {
      const response = await authorsStore.fetchAuthorInterpretations(authorIdentifier, {
        group_by: "entity",
        entity_type: entityType,
        include_metadata: true,
      });

      if (response && "interpretations_by_entity" in response) {
        const entities: Array<{
          value: string;
          label: string;
          entityType: string;
          entityId: string;
          availableLanguages: string[];
          interpretationCount: number;
        }> = [];

        // Extract entities from the grouped response
        Object.entries(response.interpretations_by_entity).forEach(([type, entitiesOfType]) => {
          if (!entityType || type === entityType) {
            Object.entries(entitiesOfType as any).forEach(([entityId, entityData]: [string, any]) => {
              entities.push({
                value: `${type}:${entityId}`,
                label: entityData.entity_info?.name || formatEntityId(type, entityId),
                entityType: type,
                entityId: entityId,
                availableLanguages: entityData.available_languages || [],
                interpretationCount: Object.keys(entityData.interpretations || {}).length,
              });
            });
          }
        });

        // Sort entities by type and then by ID
        entities.sort((a, b) => {
          if (a.entityType !== b.entityType) {
            return a.entityType.localeCompare(b.entityType);
          }

          // For hexagrams, sort numerically
          if (a.entityType === "hexagram" && b.entityType === "hexagram") {
            const aNum = parseInt(a.entityId);
            const bNum = parseInt(b.entityId);
            if (!isNaN(aNum) && !isNaN(bNum)) {
              return aNum - bNum;
            }
          }

          return a.entityId.localeCompare(b.entityId);
        });

        return entities;
      }

      return [];
    } catch (error: any) {
      console.error("Error fetching available entities:", error);
      return [];
    }
  };

  return {
    loading: readonly(loading),
    interpretations: readonly(interpretations),
    groupedInterpretations: readonly(groupedInterpretations),
    stats: readonly(stats),
    fetchAuthorInterpretations,
    fetchInterpretationsGroupedByEntity,
    fetchAuthorInterpretationStats,
    fetchAuthorLanguageCoverage,
    getAvailableLanguagesForEntity,
    getInterpretationForEntityInLanguage,
    updateInterpretation,
    createInterpretation,
    getEntityTypeDisplayName,
    getEntityTypeIcon,
    getEntityTypeColor,
    formatEntityId,
    getAvailableEntityTypes,
    getAvailableEntities,
  };
};
