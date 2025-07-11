interface EditorState {
  dirtyFields: Set<string>;
}

export const useEditorStore = defineStore("editor", () => {
  const state = reactive<EditorState>({
    dirtyFields: new Set(),
  });

  // Simple tracking of which fields have been modified
  const markFieldDirty = (fieldId: string) => {
    state.dirtyFields.add(fieldId);
  };

  const clearDirtyFields = () => {
    state.dirtyFields.clear();
  };

  const isDirty = (fieldId: string) => state.dirtyFields.has(fieldId);

  const hasChanges = computed(() => state.dirtyFields.size > 0);

  return {
    isDirty,
    hasChanges,
    markFieldDirty,
    clearDirtyFields,
  };
});
