import { useQuery } from '@tanstack/react-query';
import { authenticatedFetch } from '@/lib/auth';
import { EntityTypeSuggestion } from '@/types/entity';

interface EntityTypesResponse {
  suggestions: EntityTypeSuggestion[];
  total: number;
}

interface UseEntityTypesOptions {
  platformId?: string;
  entityClass?: string;
  enabled?: boolean;
}

export function useEntityTypes({
  platformId,
  entityClass,
  enabled = true
}: UseEntityTypesOptions = {}) {
  return useQuery({
    queryKey: ['entity-types', platformId, entityClass],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (platformId) params.append('platform_id', platformId);
      if (entityClass) params.append('entity_class', entityClass);
      
      const response = await authenticatedFetch(
        `/v1/entities/entity-types?${params.toString()}`
      );
      
      if (!response.ok) {
        throw new Error('Failed to fetch entity types');
      }
      
      return response.json() as Promise<EntityTypesResponse>;
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (was cacheTime in v4)
  });
}