interface DebugState {
  enabled: boolean;
  panelOpen: boolean;
}

export const useDebugStore = defineStore('debug', () => {
  const state = reactive<DebugState>({
    enabled: false,
    panelOpen: false
  });

  // Load debug state from localStorage
  const loadDebugState = () => {
    if (process.client) {
      const stored = localStorage.getItem('outlabs-debug-enabled');
      if (stored === 'true') {
        state.enabled = true;
      }
    }
  };

  // Toggle debug mode
  const toggleDebug = () => {
    state.enabled = !state.enabled;
    if (process.client) {
      localStorage.setItem('outlabs-debug-enabled', state.enabled.toString());
    }
    // Close panel when disabling debug
    if (!state.enabled) {
      state.panelOpen = false;
    }
  };

  // Toggle panel visibility
  const togglePanel = () => {
    if (state.enabled) {
      state.panelOpen = !state.panelOpen;
    }
  };


  // Initialize on mount
  onMounted(() => {
    loadDebugState();
  });

  return {
    // State - return reactive refs directly for v-model compatibility
    enabled: computed(() => state.enabled),
    panelOpen: computed(() => state.panelOpen),
    
    // Actions
    toggleDebug,
    togglePanel,
    loadDebugState
  };
});