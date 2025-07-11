interface ChallengeProgression {
  hexagram: number;
  value: number;
}

interface ChallengesData {
  aspect_distribution: Record<string, number>;
  quality_distribution: Record<string, number>;
  state_distribution: Record<string, number>;
  intensity_progression: ChallengeProgression[];
  difficulty_progression: ChallengeProgression[];
  solvability_progression: ChallengeProgression[];
}

interface SphereCoOccurrence {
  mental_spirit: number;
  mental_character: number;
  spirit_character: number;
  spirit_physical: number;
  character_physical: number;
}

interface SphereStrengths {
  mental: number;
  spirit: number;
  character: number;
  physical: number;
  emotional: number;
}

interface SphereHierarchy {
  mental_influence: number;
  spirit_influence: number;
  character_influence: number;
  physical_influence: number;
  emotional_influence: number;
}

interface SphereAnalytics {
  distribution: Record<string, number>;
  progression: Array<{ hexagram: number; sphere: string }>;
  primary_spheres: Record<string, number>;
  secondary_spheres: Record<string, number>;
  sphere_combinations: Record<string, number>;
  sphere_relationships: Record<string, Record<string, number>>;
  temporal_patterns: {
    by_sphere: Record<string, Record<string, number>>;
    overall: Record<string, number>;
  };
}

interface TemporalAnalytics {
  sequence_patterns: {
    patterns: Array<{ hexagram: number; pattern: string }>;
    transitions: Record<string, number>;
    cycle_detection: Record<string, number>;
  };
  pattern_distributions: {
    by_pattern: Record<string, number>;
    by_quality: Record<string, number>;
    by_duration: Record<string, number>;
  };
  urgency_mapping: {
    sequence: Array<{
      hexagram: number;
      value: number;
      normalized_value: number;
    }>;
    peaks: Array<{
      hexagram: number;
      value: number;
    }>;
  };
}

interface AnalyticsResponse {
  flow_patterns?: {
    nature_distribution: Record<string, number>;
    quality_distribution: Record<string, number>;
    direction_distribution: Record<string, number>;
    power_progression: number[];
    momentum_progression: number[];
    stability_progression: number[];
    freedom_progression: number[];
    acceleration_progression: number[];
  };
  challenges?: ChallengesData;
  aspect_distribution?: Record<string, number>;
  quality_distribution?: Record<string, number>;
  state_distribution?: Record<string, number>;
  intensity_progression?: ChallengeProgression[];
  difficulty_progression?: ChallengeProgression[];
  solvability_progression?: ChallengeProgression[];
  spheres?: SphereAnalytics;
  temporal_patterns?: TemporalAnalytics;
}

export const useAnalyticsStore = defineStore("analytics", () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const analyticsData = ref<AnalyticsResponse | null>(null);
  const authStore = useAuthStore();

  async function fetchAnalytics(type: string, timeRange: string) {
    loading.value = true;
    error.value = null;

    try {
      const data = await authStore.apiCall<AnalyticsResponse>(`/analytics/${type}`, {
        method: "GET",
        query: { timeRange },
      });

      console.log("API Response:", data);
      analyticsData.value = data;
    } catch (e) {
      error.value = "Failed to fetch analytics data";
      console.error(e);
    } finally {
      loading.value = false;
    }
  }

  function getChartData(type: string, chartType: string) {
    console.log("getChartData called with:", { type, chartType });
    console.log("Full analyticsData:", analyticsData.value);

    if (!analyticsData.value) return [];

    switch (type) {
      case "flow": {
        const flowData = analyticsData.value.flow_patterns;
        if (!flowData) return [];

        switch (chartType) {
          case "line": {
            return [
              {
                name: "Power",
                data: flowData.power_progression.map((y, i) => ({
                  x: Number(i + 1),
                  y: Number(y),
                })),
              },
              {
                name: "Momentum",
                data: flowData.momentum_progression.map((y, i) => ({
                  x: Number(i + 1),
                  y: Number(y),
                })),
              },
              {
                name: "Stability",
                data: flowData.stability_progression.map((y, i) => ({
                  x: Number(i + 1),
                  y: Number(y * 10),
                })),
              },
              {
                name: "Freedom",
                data: flowData.freedom_progression.map((y, i) => ({
                  x: Number(i + 1),
                  y: Number(y * 10),
                })),
              },
              {
                name: "Acceleration",
                data: flowData.acceleration_progression.map((y, i) => ({
                  x: Number(i + 1),
                  y: Number(y),
                })),
              },
            ];
          }
          case "radar": {
            return [
              {
                name: "Nature Distribution",
                data: Object.entries(flowData.nature_distribution).map(([key, value]) => ({
                  x: key,
                  y: value,
                })),
              },
            ];
          }
          default:
            return [];
        }
      }
      case "challenges": {
        const challengeData = analyticsData.value?.challenges || analyticsData.value;
        console.log("Raw challenge data:", challengeData);

        if (!challengeData?.intensity_progression) {
          console.log("No challenge data found");
          return [];
        }

        switch (chartType) {
          case "line": {
            const sortByHexagram = (a: ChallengeProgression, b: ChallengeProgression) => a.hexagram - b.hexagram;

            const progressionData = [
              {
                name: "Intensity",
                data: [...challengeData.intensity_progression].sort(sortByHexagram).map((item) => ({
                  x: item.hexagram,
                  y: item.value,
                })),
              },
              {
                name: "Difficulty",
                data: [...challengeData.difficulty_progression].sort(sortByHexagram).map((item) => ({
                  x: item.hexagram,
                  y: item.value * 10,
                })),
              },
              {
                name: "Solvability",
                data: [...challengeData.solvability_progression].sort(sortByHexagram).map((item) => ({
                  x: item.hexagram,
                  y: item.value * 10,
                })),
              },
            ];

            console.log("Final progression data:", progressionData);
            return progressionData;
          }
          case "distribution": {
            const distributionData = [
              {
                name: "Aspect",
                data: Object.entries(challengeData.aspect_distribution).map(([key, value]) => ({
                  x: key,
                  y: value,
                })),
              },
              {
                name: "Quality",
                data: Object.entries(challengeData.quality_distribution).map(([key, value]) => ({
                  x: key,
                  y: value,
                })),
              },
              {
                name: "State",
                data: Object.entries(challengeData.state_distribution).map(([key, value]) => ({
                  x: key,
                  y: value,
                })),
              },
            ];
            console.log("distribution chart data:", distributionData);
            return distributionData;
          }
          default:
            return [];
        }
      }
      case "spheres": {
        const sphereData = analyticsData.value;
        if (!sphereData) return [];

        switch (chartType) {
          case "matrix": {
            // Transform sphere_relationships into treemap format
            const relationships = Object.entries(sphereData.sphere_relationships || {}).map(([sphere, relations]) => ({
              x: sphere,
              y: Object.values(relations)[0] || 0,
            }));
            return [
              {
                data: relationships,
              },
            ];
          }
          case "strengths": {
            // Return distribution data for polar area chart
            return Object.values(sphereData.distribution || {});
          }
          case "hierarchy": {
            // Return temporal patterns for radial bars
            if (!sphereData.temporal_patterns?.overall) return [];
            const total = Object.values(sphereData.temporal_patterns.overall).reduce((a, b) => a + b, 0);
            return Object.values(sphereData.temporal_patterns.overall).map((value) => (value / total) * 100);
          }
          default:
            return [];
        }
      }
      case "temporal": {
        const temporalData = analyticsData.value;
        if (!temporalData) return [];

        switch (chartType) {
          case "distribution": {
            // Return pattern distribution data
            return [
              {
                name: "Pattern Distribution",
                data: Object.entries(temporalData.pattern_distributions.by_pattern).map(([key, value]) => ({
                  x: key.charAt(0).toUpperCase() + key.slice(1),
                  y: value,
                })),
              },
            ];
          }
          case "types": {
            // Return pattern types data for donut chart
            const patterns = temporalData.pattern_distributions.by_pattern;
            return Object.values(patterns);
          }
          case "progression": {
            // Transform sequence patterns into line series by pattern type
            const allPatterns = temporalData.sequence_patterns.patterns;
            const patternTypes = ["progressive", "cyclical", "continuous", "sequential", "singular"];

            // Create a series for each pattern type
            return patternTypes.map((patternType) => ({
              name: patternType.charAt(0).toUpperCase() + patternType.slice(1),
              data: Array.from({ length: 64 }, (_, i) => {
                const hexNum = i + 1;
                const found = allPatterns.find((p) => p.hexagram === hexNum && p.pattern === patternType);
                return {
                  x: hexNum,
                  y: found ? 1 : 0,
                };
              }),
            }));
          }
          default:
            return [];
        }
      }
      default:
        return [];
    }
  }

  return {
    loading,
    error,
    analyticsData,
    fetchAnalytics,
    getChartData,
  };
});
