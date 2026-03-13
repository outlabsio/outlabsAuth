import { createAPIClient } from "./client";
import type {
  AbacTargetType,
  ConditionGroup,
  ConditionGroupCreateData,
  ConditionGroupUpdateData,
  AbacCondition,
  AbacConditionCreateData,
  AbacConditionUpdateData,
} from "~/types/abac";

function resolveTargetPath(targetType: AbacTargetType, targetId: string): string {
  const base = targetType === "role" ? "/v1/roles" : "/v1/permissions";
  return `${base}/${targetId}`;
}

export function createAbacAPI() {
  const client = createAPIClient();

  return {
    async listConditionGroups(
      targetType: AbacTargetType,
      targetId: string,
    ): Promise<ConditionGroup[]> {
      return client.call<ConditionGroup[]>(
        `${resolveTargetPath(targetType, targetId)}/condition-groups`,
      );
    },

    async createConditionGroup(
      targetType: AbacTargetType,
      targetId: string,
      data: ConditionGroupCreateData,
    ): Promise<ConditionGroup> {
      return client.call<ConditionGroup>(
        `${resolveTargetPath(targetType, targetId)}/condition-groups`,
        {
          method: "POST",
          body: data,
        },
      );
    },

    async updateConditionGroup(
      targetType: AbacTargetType,
      targetId: string,
      groupId: string,
      data: ConditionGroupUpdateData,
    ): Promise<ConditionGroup> {
      return client.call<ConditionGroup>(
        `${resolveTargetPath(targetType, targetId)}/condition-groups/${groupId}`,
        {
          method: "PATCH",
          body: data,
        },
      );
    },

    async deleteConditionGroup(
      targetType: AbacTargetType,
      targetId: string,
      groupId: string,
    ): Promise<void> {
      return client.call<void>(
        `${resolveTargetPath(targetType, targetId)}/condition-groups/${groupId}`,
        {
          method: "DELETE",
        },
      );
    },

    async listConditions(
      targetType: AbacTargetType,
      targetId: string,
    ): Promise<AbacCondition[]> {
      return client.call<AbacCondition[]>(
        `${resolveTargetPath(targetType, targetId)}/conditions`,
      );
    },

    async createCondition(
      targetType: AbacTargetType,
      targetId: string,
      data: AbacConditionCreateData,
    ): Promise<AbacCondition> {
      return client.call<AbacCondition>(
        `${resolveTargetPath(targetType, targetId)}/conditions`,
        {
          method: "POST",
          body: data,
        },
      );
    },

    async updateCondition(
      targetType: AbacTargetType,
      targetId: string,
      conditionId: string,
      data: AbacConditionUpdateData,
    ): Promise<AbacCondition> {
      return client.call<AbacCondition>(
        `${resolveTargetPath(targetType, targetId)}/conditions/${conditionId}`,
        {
          method: "PATCH",
          body: data,
        },
      );
    },

    async deleteCondition(
      targetType: AbacTargetType,
      targetId: string,
      conditionId: string,
    ): Promise<void> {
      return client.call<void>(
        `${resolveTargetPath(targetType, targetId)}/conditions/${conditionId}`,
        {
          method: "DELETE",
        },
      );
    },
  };
}
