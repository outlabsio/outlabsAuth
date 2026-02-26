/**
 * ABAC Types
 * Shared condition group and condition contracts for roles/permissions ABAC management.
 */

export type ConditionGroupOperator = "AND" | "OR";
export type ConditionValueType = "string" | "integer" | "float" | "boolean" | "list";

export interface ConditionGroup {
  id: string;
  operator: ConditionGroupOperator;
  description?: string;
  role_id?: string;
  permission_id?: string;
}

export interface AbacCondition {
  id: string;
  attribute: string;
  operator: string;
  value?: string | null;
  value_type: ConditionValueType;
  description?: string;
  condition_group_id?: string | null;
}

export interface ConditionGroupCreateData {
  operator: ConditionGroupOperator;
  description?: string;
}

export interface ConditionGroupUpdateData {
  operator?: ConditionGroupOperator;
  description?: string;
}

export interface AbacConditionCreateData {
  attribute: string;
  operator: string;
  value?: unknown;
  value_type: ConditionValueType;
  description?: string;
  condition_group_id?: string | null;
}

export interface AbacConditionUpdateData {
  attribute?: string;
  operator?: string;
  value?: unknown;
  value_type?: ConditionValueType;
  description?: string;
  condition_group_id?: string | null;
}
