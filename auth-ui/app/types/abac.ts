export type AbacTargetType = "role" | "permission";

export type ConditionGroupOperator = "AND" | "OR";

export type AbacValueType = "string" | "integer" | "float" | "boolean" | "list";
export type ConditionValueType = AbacValueType;

export interface ConditionGroup {
  id: string;
  operator: ConditionGroupOperator;
  description?: string | null;
  role_id?: string | null;
  permission_id?: string | null;
}

export interface ConditionGroupCreateData {
  operator: ConditionGroupOperator;
  description?: string;
}

export interface ConditionGroupUpdateData {
  operator?: ConditionGroupOperator;
  description?: string | null;
}

export interface AbacCondition {
  id: string;
  attribute: string;
  operator: string;
  value?: string | null;
  value_type: AbacValueType;
  description?: string | null;
  condition_group_id?: string | null;
}

export interface AbacConditionCreateData {
  attribute: string;
  operator: string;
  value?: string | number | boolean | string[] | null;
  value_type: AbacValueType;
  description?: string;
  condition_group_id?: string | null;
}

export interface AbacConditionUpdateData {
  attribute?: string;
  operator?: string;
  value?: string | number | boolean | string[] | null;
  value_type?: AbacValueType;
  description?: string | null;
  condition_group_id?: string | null;
}
