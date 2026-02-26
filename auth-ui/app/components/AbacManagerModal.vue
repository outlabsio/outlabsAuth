<script setup lang="ts">
import { createPermissionsAPI } from "~/api/permissions";
import { createRolesAPI } from "~/api/roles";
import type {
  AbacCondition,
  ConditionGroup,
  ConditionGroupOperator,
  ConditionValueType,
} from "~/types/abac";

const props = withDefaults(
  defineProps<{
    subjectType: "role" | "permission";
    subjectId: string;
    subjectName?: string;
    canRead?: boolean;
    canUpdate?: boolean;
  }>(),
  {
    subjectName: "",
    canRead: true,
    canUpdate: true,
  },
);

const open = defineModel<boolean>("open", { default: false });

const toast = useToast();

const state = reactive({
  groups: [] as ConditionGroup[],
  conditions: [] as AbacCondition[],
  isLoading: false,
  error: null as string | null,
  isSavingGroup: false,
  isSavingCondition: false,
});

const groupForm = reactive({
  id: "",
  operator: "AND" as ConditionGroupOperator,
  description: "",
});

const conditionForm = reactive({
  id: "",
  attribute: "",
  operator: "",
  value: "",
  value_type: "string" as ConditionValueType,
  description: "",
  condition_group_id: "",
});

const subjectLabel = computed(() =>
  props.subjectType === "role" ? "Role" : "Permission",
);

const modalTitle = computed(() => `${subjectLabel.value} ABAC`);

const groupOperatorOptions = [
  { label: "AND", value: "AND" },
  { label: "OR", value: "OR" },
];

const valueTypeOptions = [
  { label: "String", value: "string" },
  { label: "Integer", value: "integer" },
  { label: "Float", value: "float" },
  { label: "Boolean", value: "boolean" },
  { label: "List (JSON array)", value: "list" },
];

const conditionGroupOptions = computed(() => [
  { label: "No Group", value: "" },
  ...state.groups.map((group) => ({
    label: `${group.operator}${group.description ? ` - ${group.description}` : ""}`,
    value: group.id,
  })),
]);

const isEditingGroup = computed(() => !!groupForm.id);
const isEditingCondition = computed(() => !!conditionForm.id);
const conditionValuePlaceholder = computed(() => {
  if (conditionForm.value_type === "list") {
    return '["a", "b"]';
  }

  if (conditionForm.value_type === "boolean") {
    return "true or false";
  }

  return "Condition value";
});

function resetGroupForm() {
  groupForm.id = "";
  groupForm.operator = "AND";
  groupForm.description = "";
}

function resetConditionForm() {
  conditionForm.id = "";
  conditionForm.attribute = "";
  conditionForm.operator = "";
  conditionForm.value = "";
  conditionForm.value_type = "string";
  conditionForm.description = "";
  conditionForm.condition_group_id = "";
}

function toConditionInputValue(condition: AbacCondition): string {
  if (!condition.value) {
    return "";
  }

  if (condition.value_type === "list") {
    try {
      const parsed = JSON.parse(condition.value);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return condition.value;
    }
  }

  return condition.value;
}

function parseConditionValue(rawValue: string, valueType: ConditionValueType): unknown {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return null;
  }

  if (valueType === "integer") {
    const parsed = Number.parseInt(trimmed, 10);
    if (Number.isNaN(parsed)) {
      throw new Error("Value must be a valid integer.");
    }
    return parsed;
  }

  if (valueType === "float") {
    const parsed = Number.parseFloat(trimmed);
    if (Number.isNaN(parsed)) {
      throw new Error("Value must be a valid number.");
    }
    return parsed;
  }

  if (valueType === "boolean") {
    const normalized = trimmed.toLowerCase();
    if (normalized === "true") {
      return true;
    }
    if (normalized === "false") {
      return false;
    }
    throw new Error("Value must be true or false for boolean type.");
  }

  if (valueType === "list") {
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      throw new Error("List value must be valid JSON.");
    }

    if (!Array.isArray(parsed)) {
      throw new Error("List value must be a JSON array.");
    }
    return parsed;
  }

  return trimmed;
}

async function fetchGroups(): Promise<ConditionGroup[]> {
  if (props.subjectType === "role") {
    return createRolesAPI().fetchConditionGroups(props.subjectId);
  }
  return createPermissionsAPI().fetchConditionGroups(props.subjectId);
}

async function fetchConditions(): Promise<AbacCondition[]> {
  if (props.subjectType === "role") {
    return createRolesAPI().fetchConditions(props.subjectId);
  }
  return createPermissionsAPI().fetchConditions(props.subjectId);
}

async function loadAbacState() {
  if (!open.value || !props.subjectId || !props.canRead) {
    return;
  }

  state.isLoading = true;
  state.error = null;

  try {
    const [groups, conditions] = await Promise.all([
      fetchGroups(),
      fetchConditions(),
    ]);
    state.groups = groups;
    state.conditions = conditions;
  } catch (error: any) {
    state.error = error.data?.detail || error.message || "Failed to load ABAC data";
  } finally {
    state.isLoading = false;
  }
}

async function submitGroup() {
  if (!props.canUpdate) {
    return;
  }

  state.isSavingGroup = true;
  state.error = null;

  const payload = {
    operator: groupForm.operator,
    description: groupForm.description.trim() || undefined,
  };

  try {
    if (groupForm.id) {
      if (props.subjectType === "role") {
        await createRolesAPI().updateConditionGroup(
          props.subjectId,
          groupForm.id,
          payload,
        );
      } else {
        await createPermissionsAPI().updateConditionGroup(
          props.subjectId,
          groupForm.id,
          payload,
        );
      }
      toast.add({
        title: "Condition group updated",
        color: "success",
      });
    } else {
      if (props.subjectType === "role") {
        await createRolesAPI().createConditionGroup(props.subjectId, payload);
      } else {
        await createPermissionsAPI().createConditionGroup(props.subjectId, payload);
      }
      toast.add({
        title: "Condition group created",
        color: "success",
      });
    }

    resetGroupForm();
    await loadAbacState();
  } catch (error: any) {
    toast.add({
      title: "Failed to save condition group",
      description: error.data?.detail || error.message || "Unknown error",
      color: "error",
    });
  } finally {
    state.isSavingGroup = false;
  }
}

function editGroup(group: ConditionGroup) {
  groupForm.id = group.id;
  groupForm.operator = group.operator as ConditionGroupOperator;
  groupForm.description = group.description || "";
}

async function deleteGroup(group: ConditionGroup) {
  if (!props.canUpdate) {
    return;
  }

  if (!confirm("Delete this condition group?")) {
    return;
  }

  try {
    if (props.subjectType === "role") {
      await createRolesAPI().deleteConditionGroup(props.subjectId, group.id);
    } else {
      await createPermissionsAPI().deleteConditionGroup(props.subjectId, group.id);
    }

    if (groupForm.id === group.id) {
      resetGroupForm();
    }

    toast.add({
      title: "Condition group deleted",
      color: "success",
    });
    await loadAbacState();
  } catch (error: any) {
    toast.add({
      title: "Failed to delete condition group",
      description: error.data?.detail || error.message || "Unknown error",
      color: "error",
    });
  }
}

async function submitCondition() {
  if (!props.canUpdate) {
    return;
  }

  if (!conditionForm.attribute.trim() || !conditionForm.operator.trim()) {
    toast.add({
      title: "Validation error",
      description: "Attribute and operator are required.",
      color: "warning",
    });
    return;
  }

  let parsedValue: unknown = null;
  try {
    parsedValue = parseConditionValue(conditionForm.value, conditionForm.value_type);
  } catch (error: any) {
    toast.add({
      title: "Invalid condition value",
      description: error.message || "Invalid value",
      color: "warning",
    });
    return;
  }

  const payload = {
    attribute: conditionForm.attribute.trim(),
    operator: conditionForm.operator.trim(),
    value: parsedValue,
    value_type: conditionForm.value_type,
    description: conditionForm.description.trim() || undefined,
    condition_group_id: conditionForm.condition_group_id || null,
  };

  state.isSavingCondition = true;

  try {
    if (conditionForm.id) {
      if (props.subjectType === "role") {
        await createRolesAPI().updateCondition(
          props.subjectId,
          conditionForm.id,
          payload,
        );
      } else {
        await createPermissionsAPI().updateCondition(
          props.subjectId,
          conditionForm.id,
          payload,
        );
      }
      toast.add({
        title: "Condition updated",
        color: "success",
      });
    } else {
      if (props.subjectType === "role") {
        await createRolesAPI().createCondition(props.subjectId, payload);
      } else {
        await createPermissionsAPI().createCondition(props.subjectId, payload);
      }
      toast.add({
        title: "Condition created",
        color: "success",
      });
    }

    resetConditionForm();
    await loadAbacState();
  } catch (error: any) {
    toast.add({
      title: "Failed to save condition",
      description: error.data?.detail || error.message || "Unknown error",
      color: "error",
    });
  } finally {
    state.isSavingCondition = false;
  }
}

function editCondition(condition: AbacCondition) {
  conditionForm.id = condition.id;
  conditionForm.attribute = condition.attribute;
  conditionForm.operator = condition.operator;
  conditionForm.value = toConditionInputValue(condition);
  conditionForm.value_type = condition.value_type;
  conditionForm.description = condition.description || "";
  conditionForm.condition_group_id = condition.condition_group_id || "";
}

async function deleteCondition(condition: AbacCondition) {
  if (!props.canUpdate) {
    return;
  }

  if (!confirm("Delete this condition?")) {
    return;
  }

  try {
    if (props.subjectType === "role") {
      await createRolesAPI().deleteCondition(props.subjectId, condition.id);
    } else {
      await createPermissionsAPI().deleteCondition(props.subjectId, condition.id);
    }

    if (conditionForm.id === condition.id) {
      resetConditionForm();
    }

    toast.add({
      title: "Condition deleted",
      color: "success",
    });
    await loadAbacState();
  } catch (error: any) {
    toast.add({
      title: "Failed to delete condition",
      description: error.data?.detail || error.message || "Unknown error",
      color: "error",
    });
  }
}

watch(
  () => open.value,
  (isOpen) => {
    if (isOpen) {
      resetGroupForm();
      resetConditionForm();
      void loadAbacState();
    }
  },
);

watch(
  () => props.subjectId,
  () => {
    if (open.value) {
      resetGroupForm();
      resetConditionForm();
      void loadAbacState();
    }
  },
);
</script>

<template>
  <UModal
    v-model:open="open"
    :title="modalTitle"
    :description="subjectName ? `${subjectLabel}: ${subjectName}` : 'Manage ABAC condition groups and conditions'"
    fullscreen
  >
    <template #body>
      <div v-if="!canRead" class="py-12">
        <UAlert
          icon="i-lucide-lock"
          color="warning"
          variant="subtle"
          title="Not authorized"
          description="You do not have permission to view ABAC conditions."
        />
      </div>

      <div v-else-if="state.isLoading" class="flex items-center justify-center py-20">
        <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
      </div>

      <div v-else-if="state.error" class="py-8">
        <UAlert
          icon="i-lucide-alert-circle"
          color="error"
          variant="subtle"
          title="Failed to load ABAC data"
          :description="state.error"
        />
      </div>

      <div v-else class="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <UCard>
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <div>
                <h3 class="font-semibold">Condition Groups</h3>
                <p class="text-sm text-muted">Logical grouping blocks (AND/OR)</p>
              </div>
              <UBadge color="neutral" variant="subtle">{{ state.groups.length }}</UBadge>
            </div>
          </template>

          <form class="space-y-3 mb-4" @submit.prevent="submitGroup">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <USelect
                v-model="groupForm.operator"
                :items="groupOperatorOptions"
                :disabled="!canUpdate || state.isSavingGroup"
              />
              <UInput
                v-model="groupForm.description"
                placeholder="Description (optional)"
                :disabled="!canUpdate || state.isSavingGroup"
              />
            </div>
            <div class="flex items-center gap-2">
              <UButton
                type="submit"
                :label="isEditingGroup ? 'Update Group' : 'Add Group'"
                icon="i-lucide-save"
                color="primary"
                :loading="state.isSavingGroup"
                :disabled="!canUpdate"
              />
              <UButton
                v-if="isEditingGroup"
                type="button"
                label="Cancel"
                color="neutral"
                variant="ghost"
                @click="resetGroupForm"
              />
            </div>
          </form>

          <div class="space-y-2 max-h-80 overflow-y-auto">
            <div
              v-for="group in state.groups"
              :key="group.id"
              class="flex items-center justify-between gap-3 p-3 border border-default rounded-lg"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <UBadge color="info" variant="subtle">{{ group.operator }}</UBadge>
                  <p class="text-xs text-muted truncate">{{ group.id }}</p>
                </div>
                <p class="text-sm text-muted mt-1">{{ group.description || "No description" }}</p>
              </div>
              <div class="flex items-center gap-1">
                <UButton
                  icon="i-lucide-pencil"
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  :disabled="!canUpdate"
                  @click="editGroup(group)"
                />
                <UButton
                  icon="i-lucide-trash-2"
                  color="error"
                  variant="ghost"
                  size="xs"
                  :disabled="!canUpdate"
                  @click="deleteGroup(group)"
                />
              </div>
            </div>
            <p v-if="state.groups.length === 0" class="text-sm text-muted">No condition groups yet.</p>
          </div>
        </UCard>

        <UCard>
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <div>
                <h3 class="font-semibold">Conditions</h3>
                <p class="text-sm text-muted">Attribute comparisons used by policy evaluation</p>
              </div>
              <UBadge color="neutral" variant="subtle">{{ state.conditions.length }}</UBadge>
            </div>
          </template>

          <form class="space-y-3 mb-4" @submit.prevent="submitCondition">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <UInput
                v-model="conditionForm.attribute"
                placeholder="Attribute (e.g. user.department)"
                :disabled="!canUpdate || state.isSavingCondition"
              />
              <UInput
                v-model="conditionForm.operator"
                placeholder="Operator (e.g. eq, in, contains)"
                :disabled="!canUpdate || state.isSavingCondition"
              />
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
              <USelect
                v-model="conditionForm.value_type"
                :items="valueTypeOptions"
                :disabled="!canUpdate || state.isSavingCondition"
              />
              <USelect
                v-model="conditionForm.condition_group_id"
                :items="conditionGroupOptions"
                :disabled="!canUpdate || state.isSavingCondition"
              />
              <UInput
                v-model="conditionForm.description"
                placeholder="Description (optional)"
                :disabled="!canUpdate || state.isSavingCondition"
              />
            </div>

            <UTextarea
              v-model="conditionForm.value"
              :rows="conditionForm.value_type === 'list' ? 3 : 1"
              :placeholder="conditionValuePlaceholder"
              :disabled="!canUpdate || state.isSavingCondition"
            />

            <div class="flex items-center gap-2">
              <UButton
                type="submit"
                :label="isEditingCondition ? 'Update Condition' : 'Add Condition'"
                icon="i-lucide-save"
                color="primary"
                :loading="state.isSavingCondition"
                :disabled="!canUpdate"
              />
              <UButton
                v-if="isEditingCondition"
                type="button"
                label="Cancel"
                color="neutral"
                variant="ghost"
                @click="resetConditionForm"
              />
            </div>
          </form>

          <div class="space-y-2 max-h-80 overflow-y-auto">
            <div
              v-for="condition in state.conditions"
              :key="condition.id"
              class="p-3 border border-default rounded-lg"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <UBadge color="primary" variant="subtle">{{ condition.attribute }}</UBadge>
                    <UBadge color="neutral" variant="outline">{{ condition.operator }}</UBadge>
                    <UBadge color="info" variant="subtle">{{ condition.value_type }}</UBadge>
                    <UBadge v-if="condition.condition_group_id" color="secondary" variant="subtle">
                      Group
                    </UBadge>
                  </div>
                  <p class="text-sm mt-2 break-all">{{ condition.value || "(null)" }}</p>
                  <p class="text-xs text-muted mt-1">{{ condition.description || "No description" }}</p>
                </div>
                <div class="flex items-center gap-1">
                  <UButton
                    icon="i-lucide-pencil"
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    :disabled="!canUpdate"
                    @click="editCondition(condition)"
                  />
                  <UButton
                    icon="i-lucide-trash-2"
                    color="error"
                    variant="ghost"
                    size="xs"
                    :disabled="!canUpdate"
                    @click="deleteCondition(condition)"
                  />
                </div>
              </div>
            </div>
            <p v-if="state.conditions.length === 0" class="text-sm text-muted">No conditions yet.</p>
          </div>
        </UCard>
      </div>
    </template>
  </UModal>
</template>
