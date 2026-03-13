import { defineQueryOptions, useMutation, useQueryCache } from "@pinia/colada";
import { createAbacAPI } from "~/api/abac";
import type {
  AbacTargetType,
  ConditionGroup,
  ConditionGroupCreateData,
  ConditionGroupUpdateData,
  AbacCondition,
  AbacConditionCreateData,
  AbacConditionUpdateData,
} from "~/types/abac";

export const ABAC_KEYS = {
  all: ["abac"] as const,
  scope: (targetType: AbacTargetType, targetId: string) =>
    [...ABAC_KEYS.all, targetType, targetId] as const,
  groups: (targetType: AbacTargetType, targetId: string) =>
    [...ABAC_KEYS.scope(targetType, targetId), "groups"] as const,
  conditions: (targetType: AbacTargetType, targetId: string) =>
    [...ABAC_KEYS.scope(targetType, targetId), "conditions"] as const,
};

function invalidateAbac(
  queryCache: ReturnType<typeof useQueryCache>,
  targetType: AbacTargetType,
  targetId: string,
) {
  queryCache.invalidateQueries({ key: ABAC_KEYS.groups(targetType, targetId) });
  queryCache.invalidateQueries({
    key: ABAC_KEYS.conditions(targetType, targetId),
  });
}

function extractErrorMessage(error: any, fallback: string): string {
  if (error?.data?.detail) {
    if (Array.isArray(error.data.detail)) {
      return error.data.detail
        .map((detail: any) => detail.msg || JSON.stringify(detail))
        .join(", ");
    }
    return error.data.detail;
  }

  return error?.message || fallback;
}

export const abacQueries = {
  groups: (targetType: AbacTargetType, targetId: string) =>
    defineQueryOptions({
      key: ABAC_KEYS.groups(targetType, targetId),
      query: async () => {
        const abacAPI = createAbacAPI();
        return abacAPI.listConditionGroups(targetType, targetId);
      },
      staleTime: 10000,
    }),

  conditions: (targetType: AbacTargetType, targetId: string) =>
    defineQueryOptions({
      key: ABAC_KEYS.conditions(targetType, targetId),
      query: async () => {
        const abacAPI = createAbacAPI();
        return abacAPI.listConditions(targetType, targetId);
      },
      staleTime: 10000,
    }),
};

export function useCreateConditionGroupMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      targetType,
      targetId,
      data,
    }: {
      targetType: AbacTargetType;
      targetId: string;
      data: ConditionGroupCreateData;
    }): Promise<ConditionGroup> => {
      const abacAPI = createAbacAPI();
      return abacAPI.createConditionGroup(targetType, targetId, data);
    },
    onSuccess: (_data, variables) => {
      invalidateAbac(queryCache, variables.targetType, variables.targetId);
      toast.add({
        title: "Condition group created",
        description: "The ABAC condition group was created successfully.",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error creating condition group",
        description: extractErrorMessage(
          error,
          "Failed to create condition group.",
        ),
        color: "error",
      });
    },
  });
}

export function useUpdateConditionGroupMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      targetType,
      targetId,
      groupId,
      data,
    }: {
      targetType: AbacTargetType;
      targetId: string;
      groupId: string;
      data: ConditionGroupUpdateData;
    }): Promise<ConditionGroup> => {
      const abacAPI = createAbacAPI();
      return abacAPI.updateConditionGroup(targetType, targetId, groupId, data);
    },
    onSuccess: (_data, variables) => {
      invalidateAbac(queryCache, variables.targetType, variables.targetId);
      toast.add({
        title: "Condition group updated",
        description: "The ABAC condition group was updated successfully.",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error updating condition group",
        description: extractErrorMessage(
          error,
          "Failed to update condition group.",
        ),
        color: "error",
      });
    },
  });
}

export function useDeleteConditionGroupMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      targetType,
      targetId,
      groupId,
    }: {
      targetType: AbacTargetType;
      targetId: string;
      groupId: string;
    }): Promise<void> => {
      const abacAPI = createAbacAPI();
      return abacAPI.deleteConditionGroup(targetType, targetId, groupId);
    },
    onSuccess: (_data, variables) => {
      invalidateAbac(queryCache, variables.targetType, variables.targetId);
      toast.add({
        title: "Condition group deleted",
        description: "The ABAC condition group was deleted successfully.",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error deleting condition group",
        description: extractErrorMessage(
          error,
          "Failed to delete condition group.",
        ),
        color: "error",
      });
    },
  });
}

export function useCreateConditionMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      targetType,
      targetId,
      data,
    }: {
      targetType: AbacTargetType;
      targetId: string;
      data: AbacConditionCreateData;
    }): Promise<AbacCondition> => {
      const abacAPI = createAbacAPI();
      return abacAPI.createCondition(targetType, targetId, data);
    },
    onSuccess: (_data, variables) => {
      invalidateAbac(queryCache, variables.targetType, variables.targetId);
      toast.add({
        title: "Condition created",
        description: "The ABAC condition was created successfully.",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error creating condition",
        description: extractErrorMessage(error, "Failed to create condition."),
        color: "error",
      });
    },
  });
}

export function useUpdateConditionMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      targetType,
      targetId,
      conditionId,
      data,
    }: {
      targetType: AbacTargetType;
      targetId: string;
      conditionId: string;
      data: AbacConditionUpdateData;
    }): Promise<AbacCondition> => {
      const abacAPI = createAbacAPI();
      return abacAPI.updateCondition(
        targetType,
        targetId,
        conditionId,
        data,
      );
    },
    onSuccess: (_data, variables) => {
      invalidateAbac(queryCache, variables.targetType, variables.targetId);
      toast.add({
        title: "Condition updated",
        description: "The ABAC condition was updated successfully.",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error updating condition",
        description: extractErrorMessage(error, "Failed to update condition."),
        color: "error",
      });
    },
  });
}

export function useDeleteConditionMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      targetType,
      targetId,
      conditionId,
    }: {
      targetType: AbacTargetType;
      targetId: string;
      conditionId: string;
    }): Promise<void> => {
      const abacAPI = createAbacAPI();
      return abacAPI.deleteCondition(targetType, targetId, conditionId);
    },
    onSuccess: (_data, variables) => {
      invalidateAbac(queryCache, variables.targetType, variables.targetId);
      toast.add({
        title: "Condition deleted",
        description: "The ABAC condition was deleted successfully.",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error deleting condition",
        description: extractErrorMessage(error, "Failed to delete condition."),
        color: "error",
      });
    },
  });
}
