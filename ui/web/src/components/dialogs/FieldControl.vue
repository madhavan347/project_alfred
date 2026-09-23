<script setup lang="ts">
import { computed, useId } from 'vue'
import type { ActionContext, FieldSpec, Values } from '@/lib/actions'
import FormField from '@/components/base/FormField.vue'
import TextInput from '@/components/base/TextInput.vue'
import TextArea from '@/components/base/TextArea.vue'
import SelectInput from '@/components/base/SelectInput.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import ToggleSwitch from '@/components/base/ToggleSwitch.vue'
import CheckList from '@/components/base/CheckList.vue'

/** Render one catalog field with the matching control. */
const props = defineProps<{ field: FieldSpec; values: Values; context: ActionContext; invalid?: boolean }>()
const id = useId()
const options = computed(() => props.field.options?.(props.context) ?? [])

const text = computed({
  get: () => String(props.values[props.field.key] ?? ''),
  set: (value: string) => {
    props.values[props.field.key] = value
  },
})
const toggle = computed({
  get: () => Boolean(props.values[props.field.key]),
  set: (value: boolean) => {
    props.values[props.field.key] = value
  },
})
const list = computed({
  get: () => (props.values[props.field.key] as string[]) ?? [],
  set: (value: string[]) => {
    props.values[props.field.key] = value
  },
})
</script>

<template>
  <ToggleSwitch v-if="field.kind === 'toggle'" :id="id" v-model="toggle" :label="field.label" :help="field.help" />
  <FormField
    v-else
    :label="field.label"
    :help="field.help"
    :required="field.required"
    :for-id="field.kind === 'segmented' || field.kind === 'checklist' ? undefined : id"
  >
    <TextArea
      v-if="field.kind === 'textarea'"
      :id="id"
      v-model="text"
      :rows="field.rows"
      :placeholder="field.placeholder"
      :mono="field.mono"
      :invalid="invalid"
    />
    <SelectInput v-else-if="field.kind === 'select'" :id="id" v-model="text" :options="options" :invalid="invalid" />
    <SegmentedControl v-else-if="field.kind === 'segmented'" v-model="text" :options="options" :label="field.label" />
    <CheckList v-else-if="field.kind === 'checklist'" v-model="list" :options="options" :label="field.label" />
    <TextInput
      v-else
      :id="id"
      v-model="text"
      :type="field.kind === 'number' ? 'number' : 'text'"
      :placeholder="field.placeholder"
      :mono="field.mono"
      :invalid="invalid"
    />
  </FormField>
</template>
