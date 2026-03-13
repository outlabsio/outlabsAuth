<script setup lang="ts">
import { useQuery } from "@pinia/colada";
import {
  abacQueries,
  useCreateConditionGroupMutation,
  useUpdateConditionGroupMutation,
  useDeleteConditionGroupMutation,
  useCreateConditionMutation,
  useUpdateConditionMutation,
  useDeleteConditionMutation,
} from "~/queries/abac";
import type {
  AbacCondition,
  AbacTargetType,
  AbacValueType,
  ConditionGroup,
  ConditionGroupOperator,
} from "~/types/abac";

const props = withDefaults(
  defineProps<{
    targetType: AbacTargetType;
    targetId: string;
    active?: boolean;
  }>(),
  {
    active: true,
  },
);

const toast = useToast();
const targetLabel = computed(() =>
  props.targetType === "role" ? "role" : "permission",
);
const queryEnabled = computed(() => props.active && !!props.targetId);

const {
  data: groupsData,
  isLoading: isLoadingGroups,
  error: groupsError,
} = useQuery(() => ({
  ...abacQueries.groups(props.targetType, props.targetId),
  enabled: queryEnabled.value,
}));

const {
  data: conditionsData,
  isLoading: isLoadingConditions,
  error: conditionsError,
} = useQuery(() => ({
  ...abacQueries.conditions(props.targetType, props.targetId),
  enabled: queryEnabled.value,
}));

const groups = computed(() => groupsData.value || []);
const conditions = computed(() => conditionsData.value || []);

const groupOptions = computed(() => [
  { label: "Ungrouped", value: "" },
  ...groups.value.map((group) => ({
    label:
      group.description?.trim() ||
      `${group.operator} group ${group.id.slice(0, 8)}`,
    value: group.id,
  })),
]);

const groupOperatorOptions = [
  { label: "AND", value: "AND" },
  { label: "OR", value: "OR" },
];

const valueTypeOptions = [
  { label: "String", value: "string" },
  { label: "Integer", value: "integer" },
  { label: "Float", value: "float" },
  { label: "Boolean", value: "boolean" },
  { label: "List", value: "list" },
];

const booleanOptions = [
  { label: "True", value: "true" },
  { label: "False", value: "false" },
];

const showGroupModal = ref(false);
const showConditionModal = ref(false);

const editingGroup = ref<ConditionGroup | null>(null);
const editingCondition = ref<AbacCondition | null>(null);

const groupState = reactive({
  operator: "AND" as ConditionGroupOperator,
  description: "",
});

const conditionState = reactive({
  attribute: "",
  operator: "eq",
  value_type: "string" as AbacValueType,
  value_text: "",
  value_boolean: "true",
  description: "",
  condition_group_id: "",
});

const pendingDelete = ref<
  | {
      type: "group" | "condition";
      id: string;
      label: string;
    }
  | null
>(null);
const isDeleting = ref(false);
const deleteDialogOpen = computed({
  get: () => Boolean(pendingDelete.value),
  set: (value: boolean) => {
    if (!value && !isDeleting.value) {
      pendingDelete.value = null;
    }
  },
});

const createGroupMutation = useCreateConditionGroupMutation();
const updateGroupMutation = useUpdateConditionGroupMutation();
const deleteGroupMutation = useDeleteConditionGroupMutation();
const createConditionMutation = useCreateConditionMutation();
const updateConditionMutation = useUpdateConditionMutation();
const deleteConditionMutation = useDeleteConditionMutation();

const isLoading = computed(
  () => isLoadingGroups.value || isLoadingConditions.value,
);

const combinedErrorMessage = computed(() => {
  const error = groupsError.value || conditionsError.value;
  if (!error) {
    return "";
  }

  return error instanceof Error ? error.message : String(error);
});

const totalUngroupedConditions = computed(
  () => conditions.value.filter((condition) => !condition.condition_group_id).length,
);

const canSubmitGroup = computed(() => groupState.operator === "AND" || groupState.operator === "OR");

const canSubmitCondition = computed(() => {
  if (conditionState.attribute.trim().length < 3) {
    return false;
  }

  if (conditionState.operator.trim().length < 2) {
    return false;
  }

  if (conditionState.value_type === "boolean") {
    return true;
  }

  return conditionState.value_text.trim().length > 0;
});

function resetGroupForm() {
  editingGroup.value = null;
  groupState.operator = "AND";
  groupState.description = "";
}

function openCreateGroupModal() {
  resetGroupForm();
  showGroupModal.value = true;
}

function openEditGroupModal(group: ConditionGroup) {
  editingGroup.value = group;
  groupState.operator = group.operator;
  groupState.description = group.description || "";
  showGroupModal.value = true;
}

function formatListValue(rawValue?: string | null): string {
  if (!rawValue) {
    return "";
  }

  try {
    const parsed = JSON.parse(rawValue);
    if (Array.isArray(parsed)) {
      return parsed.map((item) => String(item)).join("\n");
    }
  } catch {
    return rawValue;
  }

  return rawValue;
}

function resetConditionForm() {
  editingCondition.value = null;
  conditionState.attribute = "";
  conditionState.operator = "eq";
  conditionState.value_type = "string";
  conditionState.value_text = "";
  conditionState.value_boolean = "true";
  conditionState.description = "";
  conditionState.condition_group_id = "";
}

function openCreateConditionModal() {
  resetConditionForm();
  showConditionModal.value = true;
}

function openEditConditionModal(condition: AbacCondition) {
  editingCondition.value = condition;
  conditionState.attribute = condition.attribute;
  conditionState.operator = condition.operator;
  conditionState.value_type = condition.value_type;
  conditionState.description = condition.description || "";
  conditionState.condition_group_id = condition.condition_group_id || "";

  if (condition.value_type === "boolean") {
    conditionState.value_boolean =
      String(condition.value).toLowerCase() === "false" ? "false" : "true";
    conditionState.value_text = "";
  } else if (condition.value_type === "list") {
    conditionState.value_text = formatListValue(condition.value);
    conditionState.value_boolean = "true";
  } else {
    conditionState.value_text = condition.value || "";
    conditionState.value_boolean = "true";
  }

  showConditionModal.value = true;
}

function groupLabel(conditionGroupId?: string | null): string {
  if (!conditionGroupId) {
    return "Ungrouped";
  }

  const group = groups.value.find((item) => item.id === conditionGroupId);
  if (!group) {
    return "Unknown group";
  }

  return group.description?.trim() || `${group.operator} group`;
}

function conditionValueSummary(condition: AbacCondition): string {
  if (condition.value_type === "list") {
    const listText = formatListValue(condition.value);
    if (!listText) {
      return "[]";
    }
    return listText.split("\n").join(", ");
  }

  return condition.value || "No value";
}

function parseConditionValue() {
  if (conditionState.value_type === "boolean") {
    return conditionState.value_boolean === "true";
  }

  if (conditionState.value_type === "integer") {
    const parsed = Number.parseInt(conditionState.value_text.trim(), 10);
    if (Number.isNaN(parsed)) {
      throw new Error("Integer values must be whole numbers.");
    }
    return parsed;
  }

  if (conditionState.value_type === "float") {
    const parsed = Number.parseFloat(conditionState.value_text.trim());
    if (Number.isNaN(parsed)) {
      throw new Error("Float values must be numeric.");
    }
    return parsed;
  }

  if (conditionState.value_type === "list") {
    const items = conditionState.value_text
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);

    if (!items.length) {
      throw new Error("List values require at least one line item.");
    }

    return items;
  }

  const value = conditionState.value_text.trim();
  if (!value) {
    throw new Error("Condition values cannot be empty.");
  }
  return value;
}

async function submitGroup() {
  if (!canSubmitGroup.value) {
    return;
  }

  const description = groupState.description.trim();
  const payload = {
    operator: groupState.operator,
    description: editingGroup.value
      ? description || null
      : description || undefined,
  };

  if (editingGroup.value) {
    await updateGroupMutation.mutateAsync({
      targetType: props.targetType,
      targetId: props.targetId,
      groupId: editingGroup.value.id,
      data: payload,
    });
  } else {
    await createGroupMutation.mutateAsync({
      targetType: props.targetType,
      targetId: props.targetId,
      data: payload,
    });
  }

  showGroupModal.value = false;
  resetGroupForm();
}

async function submitCondition() {
  if (!canSubmitCondition.value) {
    return;
  }

  let parsedValue: string | number | boolean | string[];

  try {
    parsedValue = parseConditionValue();
  } catch (error: any) {
    toast.add({
      title: "Invalid condition value",
      description: error.message || "Check the condition value and try again.",
      color: "error",
    });
    return;
  }

  const description = conditionState.description.trim();
  const conditionGroupId = conditionState.condition_group_id || null;

  const payload = {
    attribute: conditionState.attribute.trim(),
    operator: conditionState.operator.trim(),
    value: parsedValue,
    value_type: conditionState.value_type,
    description: editingCondition.value
      ? description || null
      : description || undefined,
    condition_group_id: editingCondition.value
      ? conditionGroupId
      : conditionState.condition_group_id || undefined,
  };

  if (editingCondition.value) {
    await updateConditionMutation.mutateAsync({
      targetType: props.targetType,
      targetId: props.targetId,
      conditionId: editingCondition.value.id,
      data: payload,
    });
  } else {
    await createConditionMutation.mutateAsync({
      targetType: props.targetType,
      targetId: props.targetId,
      data: payload,
    });
  }

  showConditionModal.value = false;
  resetConditionForm();
}

function requestDeleteGroup(group: ConditionGroup) {
  pendingDelete.value = {
    type: "group",
    id: group.id,
    label: group.description?.trim() || `${group.operator} group`,
  };
}

function requestDeleteCondition(condition: AbacCondition) {
  pendingDelete.value = {
    type: "condition",
    id: condition.id,
    label: `${condition.attribute} ${condition.operator}`,
  };
}

async function confirmDelete() {
  if (!pendingDelete.value) {
    return;
  }

  isDeleting.value = true;
  try {
    if (pendingDelete.value.type === "group") {
      await deleteGroupMutation.mutateAsync({
        targetType: props.targetType,
        targetId: props.targetId,
        groupId: pendingDelete.value.id,
      });
    } else {
      await deleteConditionMutation.mutateAsync({
        targetType: props.targetType,
        targetId: props.targetId,
        conditionId: pendingDelete.value.id,
      });
    }
    pendingDelete.value = null;
  } finally {
    isDeleting.value = false;
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-1">
        <h3 class="text-lg font-semibold flex items-center gap-2">
          <UIcon name="i-lucide-git-branch-plus" class="w-5 h-5" />
          ABAC Conditions
        </h3>
        <p class="text-sm text-muted">
          Attach attribute-based conditions directly to this {{ targetLabel }}. Condition groups let you cluster related rules with an AND or OR operator.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <UBadge color="neutral" variant="subtle">
          {{ groups.length }} group{{ groups.length === 1 ? "" : "s" }}
        </UBadge>
        <UBadge color="neutral" variant="subtle">
          {{ conditions.length }} condition{{ conditions.length === 1 ? "" : "s" }}
        </UBadge>
        <UBadge color="neutral" variant="subtle">
          {{ totalUngroupedConditions }} ungrouped
        </UBadge>
      </div>
    </div>

    <UAlert
      color="info"
      variant="subtle"
      icon="i-lucide-info"
      title="ABAC is additive to the base permission model"
      description="Use conditions to narrow when a role or permission applies. Values are persisted exactly as the backend stores them, including list-typed condition payloads."
    />

    <UAlert
      v-if="combinedErrorMessage"
      color="error"
      variant="subtle"
      icon="i-lucide-alert-circle"
      title="Unable to load ABAC rules"
      :description="combinedErrorMessage"
    />

    <div v-if="isLoading" class="flex items-center justify-center py-10">
      <UIcon name="i-lucide-loader-2" class="w-7 h-7 animate-spin text-primary" />
    </div>

    <div v-else class="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <div>
              <h4 class="font-semibold">Condition Groups</h4>
              <p class="text-sm text-muted">Logical containers for related conditions.</p>
            </div>
            <UButton
              icon="i-lucide-plus"
              label="Add Group"
              size="sm"
              variant="outline"
              @click="openCreateGroupModal"
            />
          </div>
        </template>

        <div v-if="groups.length" class="space-y-3">
          <div
            v-for="group in groups"
            :key="group.id"
            class="rounded-xl border border-default p-4 space-y-3"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="space-y-2">
                <div class="flex items-center gap-2">
                  <UBadge color="primary" variant="subtle">{{ group.operator }}</UBadge>
                  <span class="text-sm text-muted font-mono">{{ group.id.slice(0, 8) }}</span>
                </div>
                <p class="text-sm font-medium">
                  {{ group.description || "No description provided" }}
                </p>
              </div>

              <div class="flex items-center gap-1">
                <UButton
                  icon="i-lucide-pencil"
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  @click="openEditGroupModal(group)"
                />
                <UButton
                  icon="i-lucide-trash-2"
                  color="error"
                  variant="ghost"
                  size="xs"
                  @click="requestDeleteGroup(group)"
                />
              </div>
            </div>
          </div>
        </div>

        <div v-else class="py-10 text-center text-muted space-y-2">
          <UIcon name="i-lucide-folder-tree" class="w-10 h-10 mx-auto opacity-50" />
          <p>No condition groups yet.</p>
          <p class="text-sm">Create a group if you want to bundle related conditions under a named AND/OR operator.</p>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <div>
              <h4 class="font-semibold">Conditions</h4>
              <p class="text-sm text-muted">Attribute checks evaluated by the backend.</p>
            </div>
            <UButton
              icon="i-lucide-plus"
              label="Add Condition"
              size="sm"
              variant="outline"
              @click="openCreateConditionModal"
            />
          </div>
        </template>

        <div v-if="conditions.length" class="space-y-3">
          <div
            v-for="condition in conditions"
            :key="condition.id"
            class="rounded-xl border border-default p-4 space-y-3"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="space-y-2">
                <div class="flex flex-wrap items-center gap-2">
                  <code class="text-xs bg-elevated px-2 py-1 rounded">{{ condition.attribute }}</code>
                  <UBadge color="neutral" variant="subtle">{{ condition.operator }}</UBadge>
                  <UBadge color="primary" variant="subtle">{{ condition.value_type }}</UBadge>
                  <UBadge color="neutral" variant="outline">{{ groupLabel(condition.condition_group_id) }}</UBadge>
                </div>
                <p class="text-sm">{{ conditionValueSummary(condition) }}</p>
                <p v-if="condition.description" class="text-sm text-muted">
                  {{ condition.description }}
                </p>
              </div>

              <div class="flex items-center gap-1">
                <UButton
                  icon="i-lucide-pencil"
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  @click="openEditConditionModal(condition)"
                />
                <UButton
                  icon="i-lucide-trash-2"
                  color="error"
                  variant="ghost"
                  size="xs"
                  @click="requestDeleteCondition(condition)"
                />
              </div>
            </div>
          </div>
        </div>

        <div v-else class="py-10 text-center text-muted space-y-2">
          <UIcon name="i-lucide-filter" class="w-10 h-10 mx-auto opacity-50" />
          <p>No ABAC conditions yet.</p>
          <p class="text-sm">Add a condition to restrict when this {{ targetLabel }} applies.</p>
        </div>
      </UCard>
    </div>

    <UModal
      v-model:open="showGroupModal"
      :title="editingGroup ? 'Update Condition Group' : 'Create Condition Group'"
      :description="editingGroup ? 'Adjust the logical container for related conditions.' : 'Create a logical container for related conditions.'"
      :ui="{ width: 'sm:max-w-lg' }"
    >
      <template #body>
        <div class="space-y-4">
          <UFormField label="Operator" name="operator">
            <USelect
              v-model="groupState.operator"
              :items="groupOperatorOptions"
            />
          </UFormField>

          <UFormField label="Description" name="description">
            <UTextarea
              v-model="groupState.description"
              :rows="3"
              placeholder="Finance approvals for regional managers"
            />
          </UFormField>
        </div>
      </template>

      <template #footer>
        <div class="flex justify-end gap-2 w-full">
          <UButton
            label="Cancel"
            color="neutral"
            variant="outline"
            @click="showGroupModal = false"
          />
          <UButton
            :label="editingGroup ? 'Save Group' : 'Create Group'"
            icon="i-lucide-save"
            :loading="createGroupMutation.isPending || updateGroupMutation.isPending"
            :disabled="!canSubmitGroup"
            @click="submitGroup"
          />
        </div>
      </template>
    </UModal>

    <UModal
      v-model:open="showConditionModal"
      :title="editingCondition ? 'Update Condition' : 'Create Condition'"
      :description="editingCondition ? 'Update the attribute check persisted for this resource.' : 'Define a new attribute check for this resource.'"
      :ui="{ width: 'sm:max-w-2xl' }"
    >
      <template #body>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <UFormField label="Attribute" name="attribute">
            <UInput
              v-model="conditionState.attribute"
              placeholder="context.entity_id"
            />
          </UFormField>

          <UFormField label="Operator" name="operator">
            <UInput
              v-model="conditionState.operator"
              placeholder="eq"
            />
          </UFormField>

          <UFormField label="Value Type" name="value_type">
            <USelect
              v-model="conditionState.value_type"
              :items="valueTypeOptions"
            />
          </UFormField>

          <UFormField label="Condition Group" name="condition_group_id">
            <USelect
              v-model="conditionState.condition_group_id"
              :items="groupOptions"
            />
          </UFormField>

          <UFormField
            v-if="conditionState.value_type === 'boolean'"
            label="Value"
            name="value_boolean"
            class="md:col-span-2"
          >
            <USelect
              v-model="conditionState.value_boolean"
              :items="booleanOptions"
            />
          </UFormField>

          <UFormField
            v-else-if="conditionState.value_type === 'list'"
            label="Value"
            name="value_text"
            class="md:col-span-2"
          >
            <UTextarea
              v-model="conditionState.value_text"
              :rows="4"
              placeholder="north-america&#10;latam&#10;emea"
            />
            <p class="text-xs text-muted mt-1">Enter one list item per line.</p>
          </UFormField>

          <UFormField
            v-else
            label="Value"
            name="value_text"
            class="md:col-span-2"
          >
            <UInput
              v-model="conditionState.value_text"
              :type="conditionState.value_type === 'string' ? 'text' : 'number'"
              placeholder="Enter the comparison value"
            />
          </UFormField>

          <UFormField label="Description" name="description" class="md:col-span-2">
            <UTextarea
              v-model="conditionState.description"
              :rows="3"
              placeholder="Only allow access when the request comes from an approved region"
            />
          </UFormField>
        </div>
      </template>

      <template #footer>
        <div class="flex justify-between gap-2 w-full">
          <p class="text-xs text-muted max-w-md">
            Common attribute examples include request context, entity identifiers, or owner references already understood by your backend evaluator.
          </p>
          <div class="flex gap-2">
            <UButton
              label="Cancel"
              color="neutral"
              variant="outline"
              @click="showConditionModal = false"
            />
            <UButton
              :label="editingCondition ? 'Save Condition' : 'Create Condition'"
              icon="i-lucide-save"
              :loading="createConditionMutation.isPending || updateConditionMutation.isPending"
              :disabled="!canSubmitCondition"
              @click="submitCondition"
            />
          </div>
        </div>
      </template>
    </UModal>

    <ConfirmActionModal
      v-model:open="deleteDialogOpen"
      :title="pendingDelete?.type === 'group' ? 'Delete condition group?' : 'Delete condition?'"
      :description="pendingDelete ? `This will permanently delete '${pendingDelete.label}'.` : ''"
      :confirm-label="pendingDelete?.type === 'group' ? 'Delete group' : 'Delete condition'"
      :loading="isDeleting"
      @confirm="confirmDelete"
      @cancel="pendingDelete = null"
    />
  </div>
</template>
