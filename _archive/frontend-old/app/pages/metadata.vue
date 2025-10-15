<template>
  <div>
    <StickyHeader title="Metadata" icon="lucide:database">
      <template #actions>
        <button class="btn btn-sm btn-ghost" @click="store.resetBulkImport">
          <Icon name="lucide:refresh-ccw" class="w-4 h-4" />
          Start Over
        </button>
      </template>
    </StickyHeader>

    <div class="p-4">
      <div class="grid grid-cols-12 gap-6">
        <!-- Left Column - Selection -->
        <div class="col-span-4">
          <MetadataSelectionPanel />
        </div>

        <!-- Right Column - JSON Input and Response -->
        <div class="col-span-8 space-y-4">
          <!-- Selection Summary -->
          <div class="card shadow-sm">
            <div class="card-body">
              <!-- No Selection State -->
              <div v-if="!state.collection" class="py-8 text-center text-base-content/70">
                <Icon name="lucide:folder-search" class="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>Select a collection to begin</p>
              </div>

              <!-- Selection Progress -->
              <div v-else class="flex gap-8">
                <!-- Element ID Section (Left) -->
                <div class="flex-1">
                  <div v-if="selectedDocument" class="space-y-4">
                    <!-- Element ID and Status -->
                    <div class="flex items-center gap-3">
                      <Icon name="lucide:fingerprint" class="w-8 h-8 text-primary" />
                      <div class="flex-1">
                        <div class="text-sm text-base-content/70">Element ID</div>
                        <div class="flex items-center gap-2">
                          <h2 class="text-2xl font-bold">
                            {{ formatElementId(selectedDocument.element_id) }}
                          </h2>
                          <!-- Metadata Status Icon -->
                          <div v-if="selectedPathInfo" class="tooltip" :data-tip="getMetadataStatusTooltip">
                            <div class="flex items-center">
                              <template v-if="selectedPathInfo.exists">
                                <template v-if="selectedPathInfo.is_default">
                                  <Icon name="lucide:alert-triangle" class="w-5 h-5 text-error" />
                                </template>
                                <template v-else>
                                  <Icon name="lucide:check-circle" class="w-5 h-5 text-success" />
                                </template>
                              </template>
                              <template v-else>
                                <Icon name="lucide:circle-off" class="w-5 h-5 text-warning" />
                              </template>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Document Completion Status -->
                    <div class="pl-11">
                      <div class="space-y-2">
                        <div class="flex items-center">
                          <div class="flex-1 h-2 bg-base-300 rounded-full overflow-hidden">
                            <div class="h-full transition-all duration-300 bg-success" :style="{ width: `${getDocumentCompletionPercentage}%` }"></div>
                          </div>
                        </div>
                        <!-- Section Status -->
                        <div class="text-xs text-base-content/70 flex flex-wrap gap-2">
                          <span v-for="(status, path) in getCompletedSections" :key="path" class="inline-flex items-center gap-1">
                            <Icon
                              :name="status.partial ? 'lucide:minus' : status.exists ? 'lucide:check' : 'lucide:x'"
                              class="w-3 h-3"
                              :class="{
                                'text-success': status.exists,
                                'text-warning': status.partial,
                                'text-base-content/30': !status.exists && !status.partial,
                              }"
                            />
                            {{ store.formatFieldName(path) }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Selection Details (Right) -->
                <div class="flex-[2] grid grid-cols-2 gap-x-8">
                  <!-- Left Column -->
                  <div class="space-y-4">
                    <!-- Collection -->
                    <div class="space-y-1">
                      <div class="text-sm text-base-content/70">Collection</div>
                      <div class="flex items-center gap-2">
                        <Icon name="lucide:database" class="w-4 h-4 text-primary" />
                        <span class="font-medium">{{ store.formatFieldName(state.collection) }}</span>
                        <span class="text-sm text-base-content/70">({{ state.collections[state.collection]?.document_count }} documents)</span>
                      </div>
                    </div>

                    <!-- Document -->
                    <div class="space-y-1">
                      <div class="text-sm text-base-content/70">Document</div>
                      <div v-if="state.documentId" class="flex items-center gap-2">
                        <Icon name="lucide:file" class="w-4 h-4 text-primary" />
                        <span class="font-medium">{{ state.documentId }}</span>
                      </div>
                      <div v-else class="text-base-content/50 text-sm italic">No document selected</div>
                    </div>
                  </div>

                  <!-- Right Column -->
                  <div class="space-y-4">
                    <!-- Path -->
                    <div class="space-y-1">
                      <div class="text-sm text-base-content/70">Path</div>
                      <div v-if="state.path">
                        <div class="flex items-center gap-2">
                          <Icon :name="getSelectedPathIcon" class="w-4 h-4 text-primary" />
                          <span class="font-medium">{{ store.formatFieldName(state.path) }}</span>
                        </div>
                      </div>
                      <div v-else class="text-base-content/50 text-sm italic">No path selected</div>
                    </div>

                    <!-- Full Path -->
                    <div class="p-3 bg-base-300 rounded-lg font-mono text-sm break-all">
                      {{ fullPath }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- JSON Input -->
          <div class="card bg-base-200 shadow-sm">
            <div class="card-body">
              <h3 class="card-title text-lg flex justify-between items-center">
                <div class="flex items-center gap-2">
                  <span>JSON Data</span>
                  <!-- Status badge -->
                  <div v-if="jsonData.trim()" class="flex items-center gap-2">
                    <div class="badge gap-1" :class="jsonError ? 'badge-error' : 'badge-success'">
                      <Icon :name="jsonError ? 'lucide:alert-triangle' : 'lucide:check'" class="w-3.5 h-3.5" />
                      {{ jsonError || "Valid JSON" }}
                    </div>
                    <span class="text-sm text-base-content/70"> ({{ getJsonSize }}) </span>
                  </div>
                  <div v-else class="badge badge-neutral gap-1">
                    <Icon name="lucide:file" class="w-3.5 h-3.5" />
                    No JSON
                  </div>
                </div>
                <div class="flex items-center gap-4">
                  <!-- JSON Management Buttons -->
                  <div class="join">
                    <button class="join-item btn btn-sm" @click="pasteFromClipboard" :class="{ 'btn-primary': !jsonData.trim() }">
                      <Icon name="lucide:clipboard-paste" class="w-4 h-4" />
                      <span class="ml-1">Paste</span>
                    </button>
                    <!-- Copy button -->
                    <button class="join-item btn btn-sm btn-ghost" @click="copyToClipboard" :disabled="!jsonData.trim()">
                      <Icon name="lucide:copy" class="w-4 h-4" />
                      <span class="ml-1">Copy</span>
                    </button>
                    <button class="join-item btn btn-sm btn-ghost" @click="clearEditor" :disabled="!jsonData.trim()">
                      <Icon name="lucide:trash-2" class="w-4 h-4" />
                      <span class="ml-1">Clear</span>
                    </button>
                  </div>

                  <!-- Action Buttons -->
                  <div class="flex gap-2">
                    <!-- Edit in Form - enabled if we have JSON and it's valid -->
                    <MetadataEditorButton :path="state.path" :metadata="state.formData" @save="handleMetadataUpdate" :disabled="!jsonData.trim() || !isValidJson">
                      <template #default>
                        <Icon name="lucide:edit" class="w-4 h-4 mr-1" />
                        Edit in Form
                      </template>
                    </MetadataEditorButton>

                    <!-- Validate - enabled if we have JSON and a path selected -->
                    <button class="btn btn-sm btn-ghost" @click="validateJson" :disabled="!jsonData.trim() || !state.path">
                      <Icon v-if="!state.validating" name="lucide:check-circle" class="w-4 h-4 mr-1" />
                      <span v-else class="loading loading-spinner loading-xs mr-1"></span>
                      Validate
                    </button>
                  </div>
                </div>
              </h3>
            </div>
          </div>

          <!-- Response Section -->
          <div class="card bg-base-200 shadow-sm" v-if="response || state.validating">
            <div class="card-body">
              <!-- Loading State -->
              <template v-if="state.validating">
                <div class="flex justify-between items-center mb-4">
                  <div class="skeleton h-8 w-32"></div>
                  <div class="skeleton h-8 w-24"></div>
                </div>
                <div class="space-y-2">
                  <div class="skeleton h-4 w-full"></div>
                  <div class="skeleton h-4 w-3/4"></div>
                  <div class="skeleton h-4 w-5/6"></div>
                  <div class="skeleton h-4 w-2/3"></div>
                </div>
              </template>

              <!-- Response Content -->
              <template v-else>
                <h3 class="card-title text-lg flex justify-between items-center">
                  <div class="flex items-center gap-4">
                    <span>Response</span>
                    <UiBadge :color="response.success ? '#10b981' : '#ef4444'" variant="subtle" :animate="true" :glow="true">
                      <div class="flex items-center gap-2">
                        <Icon :name="response.success ? 'lucide:check-circle' : 'lucide:alert-triangle'" class="w-4 h-4" />
                        {{ response.success ? "Validation Succeeded" : "Validation Failed" }}
                      </div>
                    </UiBadge>
                  </div>
                  <div class="flex items-center gap-2">
                    <!-- Submit to Database button only -->
                    <button v-if="response.success" class="btn btn-sm btn-success" @click="handleDatabaseSubmit" :disabled="importing">
                      <Icon v-if="!importing" name="lucide:database" class="w-4 h-4 mr-1" />
                      <span v-else class="loading loading-spinner loading-xs mr-1"></span>
                      Submit to Database
                    </button>
                    <!-- Copy Button -->
                    <button class="btn btn-sm btn-ghost" @click="copyResponse" :class="{ 'btn-success': copied }">
                      <Icon :name="copied ? 'lucide:check' : 'lucide:copy'" class="w-4 h-4 mr-1" />
                      {{ copied ? "Copied!" : "Copy" }}
                    </button>
                    <!-- Reset Button -->
                    <button class="btn btn-sm btn-ghost" @click="resetResponse">
                      <Icon name="lucide:x" class="w-4 h-4 mr-1" />
                      Reset
                    </button>
                  </div>
                </h3>
                <pre class="bg-base-300 p-4 rounded-lg overflow-x-auto text-sm"><code>{{ formattedResponse }}</code></pre>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add loading state for import operation -->
    <div v-if="importing" class="fixed inset-0 bg-base-300/50 flex items-center justify-center z-50">
      <div class="card bg-base-100 shadow-xl">
        <div class="card-body items-center text-center">
          <span class="loading loading-spinner loading-lg"></span>
          <h3 class="mt-4">Importing Metadata...</h3>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const store = useMetadataStore();
const state = store.bulkImportState;

// Load collections on mount
onMounted(() => {
  store.loadCollections();
});

// Helper functions
const isNestedStatus = (status) => {
  if (!status) return false;
  // Check if it's the lines object
  if (status.line_1) return true;
  // Check if it's a regular metadata status object
  return !("exists" in status);
};

const getStatusTooltip = (status) => {
  if (!status) return "Unknown status";

  const parts = [];

  // Status part
  if (!status.exists) {
    parts.push("Missing metadata");
  } else if (status.is_default) {
    parts.push("Using default values");
  } else {
    parts.push("Custom metadata");
  }

  // Reasoning part
  if (status.has_reasoning) {
    parts.push("Has reasoning");
  }

  // Patterns part
  if (status.patterns?.length) {
    parts.push(`Patterns: ${status.patterns.join(", ")}`);
  }

  return parts.join("\n");
};

// Update the status check functions to be simpler and agnostic
const isIncomplete = (status) => {
  // If it's a nested object (like lines), check all its values
  if (typeof status === "object" && !("exists" in status)) {
    return Object.values(status).some(isIncomplete);
  }

  // For direct status objects
  return !status.exists || !status.has_reasoning;
};

const getStatusColor = (status) => {
  if (isIncomplete(status)) {
    return "#ef4444"; // Red for any incomplete metadata
  }
  return "#10b981"; // Green for complete
};

// Computed for full path
const fullPath = computed(() => {
  if (!state.collection && !state.path) return "";
  if (!state.path) return state.collection;
  return `${state.collection}/${state.path}`;
});

// Helper function to get the appropriate icon for each path type
const getPathIcon = (pathInfo) => {
  if (pathInfo.path.includes("judgment")) return "lucide:scale";
  if (pathInfo.path.includes("image")) return "lucide:image";
  if (pathInfo.path.includes("trigram")) return "lucide:triangle";
  return "lucide:file-text";
};

// Add these computed properties
const selectedDocument = computed(() => {
  return state.documents.find((doc) => doc.id === state.documentId);
});

const selectedPathInfo = computed(() => {
  if (!state.path || !state.availablePaths) return null;

  // Handle lines paths
  if (state.path.includes("lines")) {
    const lineMatch = state.path.match(/lines\.(\d+)\.metadata/);
    if (lineMatch && state.availablePaths.lines?.lines) {
      const lineKey = `line_${lineMatch[1]}`;
      return state.availablePaths.lines.lines[lineKey] || null;
    }
  }

  // Handle regular paths
  const foundPath = Object.entries(state.availablePaths).find(([key, info]) => {
    return "path" in info && info.path === state.path;
  });

  return foundPath ? foundPath[1] : null;
});

const getSelectedPathIcon = computed(() => {
  if (!state.path) return "lucide:file-text";
  if (state.path.includes("judgment")) return "lucide:scale";
  if (state.path.includes("image")) return "lucide:image";
  if (state.path.includes("trigram")) return "lucide:triangle";
  if (state.path.includes("lines")) return "lucide:minus";
  return "lucide:file-text";
});

const isLinePath = computed(() => {
  return state.path?.includes("lines");
});

const getLineNumber = computed(() => {
  if (!isLinePath.value) return null;
  const match = state.path?.match(/lines\.(\d+)\.metadata/);
  return match ? `Line ${match[1]}` : null;
});

const isFullscreen = ref(false);

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value;
  if (state.editor) {
    state.editor.layout();
  }
};

// Add these new refs and functions

const jsonError = ref("");

const handleJsonInput = () => {
  // Clear error state
  jsonError.value = "";

  // Try to parse JSON if there's content
  if (state.jsonData.trim()) {
    try {
      JSON.parse(state.jsonData);
    } catch (e) {
      jsonError.value = "Invalid JSON format";
    }
  }
};

// Add/update these refs
const response = computed(() => state.validationResponse);
const validationErrors = ref([]);

// Update the validateJson function
const validateJson = async () => {
  if (!jsonData.value.trim() || !state.path) return;

  state.validating = true;
  jsonError.value = ""; // Clear any JSON format errors

  try {
    // First validate JSON format
    const parsedData = JSON.parse(jsonData.value);

    // Then validate metadata
    await store.validateMetadata(parsedData);

    // Update validation errors for the form
    validationErrors.value = store.bulkImportState.formErrors;
  } catch (e) {
    // Handle JSON parsing errors
    jsonError.value = "Invalid JSON format";
    store.setValidationResponse({
      success: false,
      message: "Invalid JSON format",
      details: { errors: [{ message: e instanceof Error ? e.message : "Unknown error" }] },
      timestamp: new Date().toISOString(),
    });
  } finally {
    state.validating = false;
  }
};

// Update the formattedResponse computed property
const formattedResponse = computed(() => {
  if (!state.validationResponse) return "";
  return JSON.stringify(state.validationResponse.details, null, 2);
});

// Update handleMetadataUpdate to properly handle the form submission
const handleMetadataUpdate = async (metadata) => {
  try {
    // Update both formData and jsonData
    state.formData = metadata;
    state.jsonData = JSON.stringify(metadata, null, 2);

    const toast = useToast();
    toast.addToast({
      type: "success",
      title: "Success",
      description: "Metadata updated successfully",
    });
  } catch (error) {
    console.error("Failed to update metadata:", error);
    const toast = useToast();
    toast.addToast({
      type: "error",
      title: "Error",
      description: "Failed to update metadata",
    });
  }
};

// Add importing ref
const importing = ref(false);

const handleDatabaseSubmit = async () => {
  if (!jsonData.value) return;

  importing.value = true;
  const toast = useToast();

  try {
    const metadata = JSON.parse(jsonData.value);
    const result = await store.submitMetadataToDatabase(metadata);

    // Check for success status
    if (result.status === "success") {
      toast.addToast({
        type: "success",
        title: "Metadata Updated",
        description: result.message || `Successfully updated metadata for ${state.documentId}`,
        time: 2.5,
        position: "bottom-right",
      });

      // Clear validation display after successful submission
      store.resetValidationState();
    } else {
      // Show error in toast
      toast.addToast({
        type: "error",
        title: "Update Failed",
        description: result.message || "Unknown error occurred",
        position: "bottom-right",
        hasAcceptButton: true,
      });

      // Display the error response in the validation area
      store.setValidationResponse({
        success: false,
        message: "Database Update Failed",
        details: result, // Show the full API response
        timestamp: new Date().toISOString(),
      });
    }
  } catch (error) {
    console.error("Failed to submit metadata:", error);

    // Show error in toast
    toast.addToast({
      type: "error",
      title: "Update Failed",
      description: error instanceof Error ? error.message : "Failed to update metadata",
      position: "bottom-right",
      hasAcceptButton: true,
    });

    // Display the error in the validation area
    store.setValidationResponse({
      success: false,
      message: "Database Update Failed",
      details: {
        errors: [
          {
            message: error instanceof Error ? error.message : "Unknown error occurred",
            response: error, // Include the full error response
          },
        ],
      },
      timestamp: new Date().toISOString(),
    });
  } finally {
    importing.value = false;
  }
};

const fileInput = ref(null);

const handleImport = () => {
  fileInput.value?.click();
};

const onFileSelect = async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  try {
    const reader = new FileReader();
    reader.onload = async (e) => {
      const content = e.target?.result;
      if (typeof content === "string") {
        state.jsonData = content;
        formatJson(); // Format the imported content
      }
    };
    reader.readAsText(file);
  } catch (error) {
    console.error("Error reading file:", error);
  } finally {
    // Reset file input
    if (event.target) {
      event.target.value = "";
    }
  }
};

const copied = ref(false);

const copyResponse = async () => {
  try {
    await navigator.clipboard.writeText(formattedResponse.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000); // Reset after 2 seconds
  } catch (err) {
    console.error("Failed to copy:", err);
  }
};

const clearEditor = () => {
  store.bulkImportState.formData = {};
  jsonError.value = "";
};

// Add submitMetadata function (placeholder for now)
const submitMetadata = async () => {
  // We'll implement this later
  console.log("Submit metadata to database");
};

// Add new refs for the modal
const showMetadataEditor = ref(false);
const currentMetadata = ref({});

// Add methods to handle the modal
const openMetadataEditor = () => {
  if (!jsonData.value) return;

  try {
    showMetadataEditor.value = true;
  } catch (e) {
    console.error("Failed to parse JSON:", e);
    const toast = useToast();
    toast.addToast({
      type: "error",
      title: "Invalid JSON",
      description: "Failed to parse JSON data",
      time: 2.5,
      position: "bottom-right",
    });
  }
};

const loadingExisting = ref(false);

const loadExistingMetadata = async () => {
  if (!state.collection || !state.documentId || !state.path) return;

  loadingExisting.value = true;
  const toast = useToast();

  try {
    const existingData = await store.fetchExistingMetadata(state.collection, state.documentId, state.path);

    Object.assign(store.bulkImportState.formData, existingData);

    toast.addToast({
      type: "success",
      title: "Data Loaded",
      description: "Existing metadata loaded successfully",
      time: 2.5,
      position: "bottom-right",
    });
  } catch (error) {
    console.error("Failed to load existing metadata:", error);
    toast.addToast({
      type: "error",
      title: "Load Failed",
      description: error instanceof Error ? error.message : "Failed to load existing metadata",
      position: "bottom-right",
      hasAcceptButton: true,
    });
  } finally {
    loadingExisting.value = false;
  }
};

// Add these helper functions
const hasIncompleteLines = (lines) => {
  if (!lines) return false;
  return Object.values(lines).some((line) => !line.exists || !line.has_reasoning);
};

const prettyJson = computed(() => {
  if (!state.jsonData) return "";
  try {
    return JSON.stringify(JSON.parse(state.jsonData), null, 2);
  } catch (e) {
    return state.jsonData;
  }
});

const pasteFromClipboard = async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (!text.trim()) {
      jsonError.value = "Clipboard is empty";
      return;
    }
    jsonData.value = text;
    jsonError.value = "";
  } catch (e) {
    jsonError.value = "Invalid JSON format";
    const toast = useToast();
    toast.addToast({
      type: "error",
      title: "Invalid JSON",
      description: "The clipboard content is not valid JSON",
      time: 2.5,
      position: "bottom-right",
    });
  }
};

const getJsonSize = computed(() => {
  if (!jsonData.value.trim()) return "0 bytes";
  const bytes = new TextEncoder().encode(jsonData.value).length;
  if (bytes < 1024) return `${bytes} bytes`;
  return `${(bytes / 1024).toFixed(1)} KB`;
});

const copyToClipboard = async () => {
  if (!jsonData.value) return;

  try {
    await navigator.clipboard.writeText(jsonData.value);
    const toast = useToast();
    toast.addToast({
      type: "success",
      title: "Copied",
      description: "JSON copied to clipboard",
      time: 2,
      position: "bottom-right",
    });
  } catch (error) {
    const toast = useToast();
    toast.addToast({
      type: "error",
      title: "Copy Failed",
      description: "Failed to copy JSON to clipboard",
      time: 2.5,
      position: "bottom-right",
    });
  }
};

// Update isValidJson computed property
const isValidJson = computed(() => {
  if (!jsonData.value || !jsonData.value.trim()) return false;
  try {
    JSON.parse(jsonData.value);
    return true;
  } catch {
    return false;
  }
});

// Update the resetResponse function to use the store method
const resetResponse = () => {
  store.resetValidationState();
};

const formatElementId = (elementId) => {
  if (!elementId) return "";
  return elementId
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
};

// Add this computed property with the other computed properties
const getMetadataStatusTooltip = computed(() => {
  if (!selectedPathInfo.value) return "";

  if (!selectedPathInfo.value.exists) {
    return "No metadata exists for this path";
  }
  if (selectedPathInfo.value.is_default) {
    return "Using default metadata values";
  }
  return "Custom metadata exists";
});

// Update these computed properties to handle nested metadata properly
const getCompletedSections = computed(() => {
  if (!selectedDocument.value?.metadata_status) return {};

  // Convert the metadata_status object into a flat structure
  const sections = {};

  Object.entries(selectedDocument.value.metadata_status).forEach(([key, value]) => {
    // Handle nested structures (like lines)
    if (value && typeof value === "object" && !("exists" in value)) {
      // For nested objects, check if all children exist
      const allChildrenComplete = Object.values(value).every((child) => child && typeof child === "object" && "exists" in child && child.exists);
      const someChildrenComplete = Object.values(value).some((child) => child && typeof child === "object" && "exists" in child && child.exists);

      sections[key] = {
        exists: allChildrenComplete,
        partial: someChildrenComplete && !allChildrenComplete,
      };
    }
    // Handle direct metadata status objects
    else if (value && typeof value === "object" && "exists" in value) {
      sections[key] = { exists: value.exists };
    }
  });

  return sections;
});

const getCompletedSectionsCount = computed(() => {
  return Object.values(getCompletedSections.value).filter((section) => section.exists).length;
});

const getTotalSectionsCount = computed(() => {
  return Object.keys(getCompletedSections.value).length;
});

const getDocumentCompletionPercentage = computed(() => {
  if (!selectedDocument.value) return 0;
  const total = getTotalSectionsCount.value;
  if (total === 0) return 0;
  return Math.round((getCompletedSectionsCount.value / total) * 100);
});

// Update the getDocumentStatus function to handle nested metadata
const getDocumentStatus = (doc) => {
  if (!doc.metadata_status) return "incomplete";

  let hasComplete = false;
  let hasIncomplete = false;

  // Helper function to check nested status
  const checkStatus = (status) => {
    // If it's a lines object or other nested structure
    if (status && typeof status === "object" && !("exists" in status)) {
      // Check all nested items
      return Object.values(status).every((item) => item && typeof item === "object" && "exists" in item && item.exists);
    }
    // Regular metadata status
    return status && status.exists;
  };

  // Check all metadata sections
  Object.values(doc.metadata_status).forEach((status) => {
    if (checkStatus(status)) {
      hasComplete = true;
    } else {
      hasIncomplete = true;
    }
  });

  // Determine overall status
  if (hasComplete && !hasIncomplete) return "complete";
  if (hasComplete && hasIncomplete) return "partial";
  return "incomplete";
};

// Update the jsonData computed property to handle _custom wrappers
const jsonData = computed({
  get: () => {
    if (!store.bulkImportState.formData || Object.keys(store.bulkImportState.formData).length === 0) {
      return "";
    }

    // Deep clone and unwrap _custom objects
    const unwrappedData = JSON.parse(
      JSON.stringify(store.bulkImportState.formData, (key, value) => {
        // If the value is an object with _custom property, return its value
        if (value && typeof value === "object" && "_custom" in value) {
          return value._custom.value;
        }
        return value;
      })
    );

    return JSON.stringify(unwrappedData, null, 2);
  },
  set: (val) => {
    try {
      if (val.trim() === "") {
        store.bulkImportState.formData = {};
      } else {
        const parsed = JSON.parse(val);
        store.bulkImportState.formData = parsed;
      }
    } catch (e) {
      console.error("Invalid JSON:", e);
    }
  },
});

// Add these helper functions
const areAllLinesComplete = (status) => {
  if (!status) return false;
  return Object.values(status).every((line) => line.exists);
};

const areSomeLinesComplete = (status) => {
  if (!status) return false;
  return Object.values(status).some((line) => line.exists);
};

// Add these watchers near the top of the script setup
watch(
  () => state.loadingCollections,
  (newVal) => {
    console.log("loadingCollections changed:", newVal);
  }
);

watch(
  () => state.loadingDocuments,
  (newVal) => {
    console.log("loadingDocuments changed:", newVal);
  }
);

watch(
  () => state.loadingPaths,
  (newVal) => {
    console.log("loadingPaths changed:", newVal);
  }
);
</script>

<style>
/* Fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* List transitions */
.list-enter-active,
.list-leave-active {
  transition: all 0.3s ease;
}

.list-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.list-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Ensure items animate independently */
.list-move {
  transition: transform 0.3s ease;
}

/* Keep loading spinner visible */
.loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(var(--b2) / 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

/* Remove Monaco-related styles */
.textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  resize: none;
}

/* Remove the transition class from fixed elements */
.fixed {
  transition: none;
}

/* Add styles for the fullscreen container */
.fixed.bg-base-300 {
  padding: 1rem;
}
</style>
