<script setup lang="ts">
import type { Condition, OperatorType } from '~/types/auth.types'

const props = defineProps<{
  modelValue: Condition
  index: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Condition]
  remove: []
}>()

// Attribute categories
const attributeCategories = [
  {
    label: 'User Attributes',
    icon: 'i-lucide-user',
    prefix: 'user.',
    attributes: [
      { value: 'user.id', label: 'User ID', type: 'string' },
      { value: 'user.email', label: 'Email', type: 'string' },
      { value: 'user.department', label: 'Department', type: 'string' },
      { value: 'user.level', label: 'Level', type: 'number' },
      { value: 'user.role', label: 'Role', type: 'string' },
      { value: 'user.is_active', label: 'Is Active', type: 'boolean' },
    ]
  },
  {
    label: 'Resource Attributes',
    icon: 'i-lucide-file',
    prefix: 'resource.',
    attributes: [
      { value: 'resource.id', label: 'Resource ID', type: 'string' },
      { value: 'resource.type', label: 'Type', type: 'string' },
      { value: 'resource.status', label: 'Status', type: 'string' },
      { value: 'resource.value', label: 'Value', type: 'number' },
      { value: 'resource.owner', label: 'Owner', type: 'string' },
      { value: 'resource.department', label: 'Department', type: 'string' },
      { value: 'resource.created_at', label: 'Created At', type: 'datetime' },
    ]
  },
  {
    label: 'Entity Attributes',
    icon: 'i-lucide-building',
    prefix: 'entity.',
    attributes: [
      { value: 'entity.id', label: 'Entity ID', type: 'string' },
      { value: 'entity.type', label: 'Entity Type', type: 'string' },
      { value: 'entity.name', label: 'Entity Name', type: 'string' },
      { value: 'entity.location', label: 'Location', type: 'string' },
      { value: 'entity.status', label: 'Status', type: 'string' },
    ]
  },
  {
    label: 'Environment',
    icon: 'i-lucide-globe',
    prefix: 'environment.',
    attributes: [
      { value: 'environment.time', label: 'Current Time', type: 'datetime' },
      { value: 'environment.day_of_week', label: 'Day of Week', type: 'string' },
      { value: 'environment.ip', label: 'IP Address', type: 'string' },
      { value: 'environment.country', label: 'Country', type: 'string' },
    ]
  }
]

// Operators by type
const operatorsByType: Record<string, Array<{ value: OperatorType; label: string }>> = {
  string: [
    { value: 'EQUALS', label: 'equals' },
    { value: 'NOT_EQUALS', label: 'does not equal' },
    { value: 'STARTS_WITH', label: 'starts with' },
    { value: 'ENDS_WITH', label: 'ends with' },
    { value: 'CONTAINS', label: 'contains' },
    { value: 'REGEX_MATCH', label: 'matches pattern' },
  ],
  number: [
    { value: 'EQUALS', label: 'equals' },
    { value: 'NOT_EQUALS', label: 'does not equal' },
    { value: 'LESS_THAN', label: 'is less than' },
    { value: 'LESS_THAN_OR_EQUAL', label: 'is less than or equal' },
    { value: 'GREATER_THAN', label: 'is greater than' },
    { value: 'GREATER_THAN_OR_EQUAL', label: 'is greater than or equal' },
  ],
  boolean: [
    { value: 'EQUALS', label: 'is' },
    { value: 'NOT_EQUALS', label: 'is not' },
  ],
  datetime: [
    { value: 'LESS_THAN', label: 'is before' },
    { value: 'GREATER_THAN', label: 'is after' },
    { value: 'EQUALS', label: 'is exactly' },
  ],
  array: [
    { value: 'IN', label: 'is in' },
    { value: 'NOT_IN', label: 'is not in' },
    { value: 'CONTAINS', label: 'contains' },
    { value: 'NOT_CONTAINS', label: 'does not contain' },
  ],
  existence: [
    { value: 'EXISTS', label: 'exists' },
    { value: 'NOT_EXISTS', label: 'does not exist' },
  ]
}

// State
const condition = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Find attribute type
const selectedAttributeType = computed(() => {
  const allAttributes = attributeCategories.flatMap(cat => cat.attributes)
  const attr = allAttributes.find(a => a.value === condition.value.attribute)
  return attr?.type || 'string'
})

// Available operators for selected attribute
const availableOperators = computed(() => {
  return operatorsByType[selectedAttributeType.value] || operatorsByType.string
})

// Update handlers
function updateAttribute(value: string) {
  condition.value = {
    ...condition.value,
    attribute: value,
    // Reset operator if not valid for new type
    operator: availableOperators.value[0].value
  }
}

function updateOperator(value: OperatorType) {
  condition.value = {
    ...condition.value,
    operator: value
  }
}

function updateValue(value: any) {
  condition.value = {
    ...condition.value,
    value: value
  }
}

// Get human-readable condition preview
const conditionPreview = computed(() => {
  if (!condition.value.attribute) return 'Select an attribute'
  
  const attrLabel = condition.value.attribute
  const opLabel = availableOperators.value.find(op => op.value === condition.value.operator)?.label || condition.value.operator
  
  if (condition.value.operator === 'EXISTS' || condition.value.operator === 'NOT_EXISTS') {
    return `${attrLabel} ${opLabel}`
  }
  
  return `${attrLabel} ${opLabel} ${JSON.stringify(condition.value.value)}`
})
</script>

<template>
  <UCard class="p-4">
    <div class="space-y-4">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-filter" class="h-4 w-4 text-primary" />
          <span class="font-medium">Condition {{ index + 1 }}</span>
        </div>
        <UButton
          size="xs"
          variant="ghost"
          icon="i-lucide-x"
          color="error"
          @click="emit('remove')"
        />
      </div>

      <!-- Condition Builder -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <!-- Attribute -->
        <div>
          <label class="text-sm font-medium mb-1 block">Attribute</label>
          <UInput
            :model-value="condition.attribute"
            @update:model-value="updateAttribute"
            placeholder="e.g., user.department, resource.value"
            class="font-mono text-sm"
          />
        </div>

        <!-- Operator -->
        <div>
          <label class="text-sm font-medium mb-1 block">Operator</label>
          <USelectMenu
            :model-value="condition.operator"
            @update:model-value="updateOperator"
            :options="availableOperators"
            value-attribute="value"
            option-attribute="label"
            placeholder="Select operator..."
          />
        </div>

        <!-- Value -->
        <div v-if="condition.operator !== 'EXISTS' && condition.operator !== 'NOT_EXISTS'">
          <label class="text-sm font-medium mb-1 block">Value</label>
          
          <!-- Boolean value -->
          <USelectMenu
            v-if="selectedAttributeType === 'boolean'"
            :model-value="condition.value"
            @update:model-value="updateValue"
            :options="[
              { label: 'True', value: true },
              { label: 'False', value: false }
            ]"
            value-attribute="value"
            option-attribute="label"
          />
          
          <!-- Number value -->
          <UInput
            v-else-if="selectedAttributeType === 'number'"
            :model-value="condition.value"
            @update:model-value="updateValue"
            type="number"
            placeholder="Enter number..."
          />
          
          <!-- Array value (for IN/NOT_IN) -->
          <UTextarea
            v-else-if="condition.operator === 'IN' || condition.operator === 'NOT_IN'"
            :model-value="Array.isArray(condition.value) ? condition.value.join(', ') : ''"
            @update:model-value="(val) => updateValue(val.split(',').map(v => v.trim()).filter(v => v))"
            placeholder="Enter comma-separated values..."
            :rows="2"
          />
          
          <!-- Default string value -->
          <UInput
            v-else
            :model-value="condition.value"
            @update:model-value="updateValue"
            placeholder="Enter value..."
          />
        </div>
      </div>

      <!-- Preview -->
      <div class="text-sm text-muted-foreground bg-gray-50 dark:bg-gray-900 p-2 rounded">
        <UIcon name="i-lucide-eye" class="h-3 w-3 inline mr-1" />
        {{ conditionPreview }}
      </div>
    </div>
  </UCard>
</template>