import { useState, useEffect } from "react";
import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerFooter,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Loader2, Shield, Globe, AlertTriangle, Trash2, Info } from "lucide-react";
import { authenticatedFetch } from "@/lib/auth";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface PermissionDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  permissionData?: Permission | null;
}

interface Permission {
  id: string;
  name: string;
  display_name: string;
  description: string;
  scope: "system" | "platform";
  resource: string;
  action: string;
  created_at: string;
  updated_at: string;
}

async function createPermission(data: {
  name: string;
  display_name: string;
  description: string;
  scope: string;
}) {
  const response = await authenticatedFetch("/v1/permissions/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  
  return response.json();
}

async function updatePermission(id: string, data: {
  display_name: string;
  description: string;
}) {
  const response = await authenticatedFetch(`/v1/permissions/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  
  return response.json();
}

async function deletePermission(id: string) {
  const response = await authenticatedFetch(`/v1/permissions/${id}`, {
    method: "DELETE",
  });
}

// Common permission actions
const PERMISSION_ACTIONS = [
  { value: "manage_all", label: "Manage All", description: "Full control over all resources" },
  { value: "manage_platform", label: "Manage Platform", description: "Manage resources within a platform" },
  { value: "manage_client", label: "Manage Client", description: "Manage resources within a client" },
  { value: "read_all", label: "Read All", description: "View all resources" },
  { value: "read_platform", label: "Read Platform", description: "View platform resources" },
  { value: "read_client", label: "Read Client", description: "View client resources" },
  { value: "create", label: "Create", description: "Create new resources" },
  { value: "update", label: "Update", description: "Update existing resources" },
  { value: "delete", label: "Delete", description: "Delete resources" },
];

// Common resources
const RESOURCES = [
  "user",
  "role",
  "permission",
  "group",
  "platform",
  "client",
  "audit_log",
  "api_key",
  "webhook",
  "billing",
];

async function fetchPlatforms(): Promise<Platform[]> {
  const response = await authenticatedFetch("/v1/platforms/");
  return response.json();
}

export function PermissionDrawer({ open, onOpenChange, mode, permissionData }: PermissionDrawerProps) {
  const queryClient = useQueryClient();
  const isEditMode = mode === "edit";
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [selectedResource, setSelectedResource] = useState("");
  const [selectedAction, setSelectedAction] = useState("");
  
  const { data: platforms = [] } = useQuery({
    queryKey: ["platforms"],
    queryFn: fetchPlatforms,
    enabled: open,
  });
  
  const createMutation = useMutation({
    mutationFn: createPermission,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
      toast.success("Permission created successfully!");
      onOpenChange(false);
      form.reset();
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updatePermission(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
      toast.success("Permission updated successfully!");
      onOpenChange(false);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  const deleteMutation = useMutation({
    mutationFn: deletePermission,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
      toast.success("Permission deleted successfully!");
      onOpenChange(false);
      setShowDeleteDialog(false);
    },
    onError: (error: Error) => {
      toast.error(error.message);
      setShowDeleteDialog(false);
    },
  });
  
  const form = useForm({
    defaultValues: {
      display_name: "",
      description: "",
      scope: "platform",
      resource: "",
      action: "",
    },
    onSubmit: async ({ value }) => {
      if (isEditMode && permissionData) {
        await updateMutation.mutateAsync({
          id: permissionData.id,
          data: {
            display_name: value.display_name,
            description: value.description,
          },
        });
      } else {
        // Generate permission name from resource and action
        const name = `${value.resource}:${value.action}`;
        await createMutation.mutateAsync({
          name,
          display_name: value.display_name,
          description: value.description,
          scope: value.scope,
        });
      }
    },
  });
  
  // Initialize form with permission data when in edit mode
  useEffect(() => {
    if (isEditMode && permissionData) {
      form.setFieldValue("display_name", permissionData.display_name);
      form.setFieldValue("description", permissionData.description || "");
      form.setFieldValue("scope", permissionData.scope);
      
      // Extract resource and action from permission name
      const [resource, action] = permissionData.name.split(":");
      setSelectedResource(resource);
      setSelectedAction(action);
      form.setFieldValue("resource", resource);
      form.setFieldValue("action", action);
    } else {
      form.reset();
      setSelectedResource("");
      setSelectedAction("");
    }
  }, [isEditMode, permissionData, form]);
  
  // Update display name when resource/action changes
  useEffect(() => {
    if (!isEditMode && selectedResource && selectedAction) {
      const action = PERMISSION_ACTIONS.find(a => a.value === selectedAction);
      const displayName = `${action?.label || selectedAction} ${selectedResource.charAt(0).toUpperCase() + selectedResource.slice(1)}s`;
      form.setFieldValue("display_name", displayName);
    }
  }, [selectedResource, selectedAction, isEditMode, form]);
  
  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full max-w-2xl h-full flex flex-col">
        <DrawerHeader className="px-6">
          <DrawerTitle>{isEditMode ? "Edit Permission" : "Create New Permission"}</DrawerTitle>
          <DrawerDescription>
            {isEditMode
              ? "Update permission details"
              : "Define a new granular permission for your system"}
          </DrawerDescription>
        </DrawerHeader>
        
        <div className="overflow-y-auto px-6 py-4 flex-1">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              e.stopPropagation();
              form.handleSubmit();
            }}
            className="space-y-6"
          >
            {/* Resource Selection - Only in create mode */}
            {!isEditMode && (
              <>
                <div className="space-y-4">
                  <h3 className="text-sm font-medium">Resource</h3>
                  <form.Field name="resource">
                    {(field) => (
                      <div className="grid grid-cols-3 gap-2">
                        {RESOURCES.map((resource) => (
                          <Button
                            key={resource}
                            type="button"
                            variant={selectedResource === resource ? "default" : "outline"}
                            size="sm"
                            onClick={() => {
                              setSelectedResource(resource);
                              field.handleChange(resource);
                            }}
                            className="justify-start"
                          >
                            {resource}
                          </Button>
                        ))}
                      </div>
                    )}
                  </form.Field>
                </div>
                
                <Separator />
                
                {/* Action Selection - Only in create mode */}
                <div className="space-y-4">
                  <h3 className="text-sm font-medium">Action</h3>
                  <form.Field name="action">
                    {(field) => (
                      <div className="space-y-2">
                        {PERMISSION_ACTIONS.map((action) => (
                          <label
                            key={action.value}
                            className={cn(
                              "flex items-start space-x-3 rounded-lg border p-3 cursor-pointer hover:bg-accent transition-colors",
                              selectedAction === action.value && "border-primary bg-primary/5"
                            )}
                          >
                            <RadioGroup
                              value={selectedAction}
                              onValueChange={(value) => {
                                setSelectedAction(value);
                                field.handleChange(value);
                              }}
                            >
                              <RadioGroupItem value={action.value} />
                            </RadioGroup>
                            <div className="flex-1">
                              <div className="font-medium text-sm">{action.label}</div>
                              <div className="text-xs text-muted-foreground">{action.description}</div>
                            </div>
                          </label>
                        ))}
                      </div>
                    )}
                  </form.Field>
                </div>
                
                <Separator />
              </>
            )}
            
            {/* Display Name and Description */}
            <div className="space-y-4">
              <h3 className="text-sm font-medium">Details</h3>
              
              {isEditMode && (
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    Permission name: <code className="ml-1">{permissionData?.name}</code>
                  </AlertDescription>
                </Alert>
              )}
              
              <form.Field name="display_name">
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="display_name">Display Name</Label>
                    <Input
                      id="display_name"
                      placeholder="e.g., Manage Users"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    <p className="text-xs text-muted-foreground">
                      Human-readable name shown in the UI
                    </p>
                    {field.state.meta.errors && (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    )}
                  </div>
                )}
              </form.Field>
              
              <form.Field name="description">
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      placeholder="Describe what this permission allows"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                      rows={3}
                    />
                    {field.state.meta.errors && (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    )}
                  </div>
                )}
              </form.Field>
            </div>
            
            {/* Scope Selection */}
            <div className="space-y-4">
              <h3 className="text-sm font-medium">Permission Scope</h3>
              
              {isEditMode ? (
                <div className="flex items-center gap-2 p-4 bg-muted rounded-lg">
                  {form.state.values.scope === "system" ? (
                    <>
                      <Shield className="h-5 w-5 text-primary" />
                      <span className="font-medium">System Scope</span>
                    </>
                  ) : (
                    <>
                      <Globe className="h-5 w-5 text-primary" />
                      <span className="font-medium">Platform Scope</span>
                    </>
                  )}
                  <span className="text-sm text-muted-foreground ml-2">
                    (scope cannot be changed)
                  </span>
                </div>
              ) : (
                <form.Field name="scope">
                  {(field) => (
                    <RadioGroup
                      value={field.state.value}
                      onValueChange={(value) => field.handleChange(value)}
                    >
                      <div className="grid grid-cols-2 gap-3">
                        <label
                          htmlFor="scope-system"
                          className={cn(
                            "relative flex flex-col items-center space-y-2 rounded-lg border-2 p-4 cursor-pointer hover:bg-accent transition-colors",
                            field.state.value === "system" ? "border-primary bg-primary/5" : "border-muted"
                          )}
                        >
                          <RadioGroupItem value="system" id="scope-system" className="sr-only" />
                          <Shield className={cn(
                            "h-6 w-6",
                            field.state.value === "system" ? "text-primary" : "text-muted-foreground"
                          )} />
                          <span className="text-sm font-medium">System</span>
                          <span className="text-xs text-center text-muted-foreground">
                            Global across all platforms
                          </span>
                        </label>
                        
                        <label
                          htmlFor="scope-platform"
                          className={cn(
                            "relative flex flex-col items-center space-y-2 rounded-lg border-2 p-4 cursor-pointer hover:bg-accent transition-colors",
                            field.state.value === "platform" ? "border-primary bg-primary/5" : "border-muted"
                          )}
                        >
                          <RadioGroupItem value="platform" id="scope-platform" className="sr-only" />
                          <Globe className={cn(
                            "h-6 w-6",
                            field.state.value === "platform" ? "text-primary" : "text-muted-foreground"
                          )} />
                          <span className="text-sm font-medium">Platform</span>
                          <span className="text-xs text-center text-muted-foreground">
                            Platform-specific operations
                          </span>
                        </label>
                      </div>
                    </RadioGroup>
                  )}
                </form.Field>
              )}
              
              {/* Platform selection for platform-scoped permissions */}
              {form.state.values.scope === "platform" && (
                <form.Field 
                  name="platform_id"
                  validators={{
                    onChange: ({ value }) => (!value ? "Platform is required for platform-scoped permissions" : undefined),
                  }}
                >
                  {(field) => (
                    <div className="space-y-2">
                      <Label htmlFor="platform_id">Target Platform *</Label>
                      <Select
                        value={field.state.value}
                        onValueChange={(value) => field.handleChange(value)}
                        disabled={isEditMode}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select a platform" />
                        </SelectTrigger>
                        <SelectContent>
                          {platforms.map((platform) => (
                            <SelectItem key={platform._id} value={platform._id}>
                              {platform.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        {isEditMode 
                          ? "Platform assignment cannot be changed" 
                          : "Select which platform this permission belongs to"}
                      </p>
                      {field.state.meta.errors && (
                        <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                      )}
                    </div>
                  )}
                </form.Field>
              )}
            </div>
          </form>
          
          {/* Danger Zone - Only show in edit mode */}
          {isEditMode && (
            <div className="mt-8 space-y-4 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-destructive" />
                <h3 className="font-semibold text-destructive">Danger Zone</h3>
              </div>
              
              <div className="space-y-4">
                <div>
                  <h4 className="font-medium">Delete this permission</h4>
                  <p className="text-sm text-muted-foreground mt-1">
                    Once you delete a permission, there is no going back. This will permanently delete the permission
                    and remove it from all roles that currently have it assigned.
                  </p>
                </div>
                
                <Button
                  variant="destructive"
                  onClick={() => setShowDeleteDialog(true)}
                  className="w-full"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Permission
                </Button>
              </div>
            </div>
          )}
        </div>
        
        <DrawerFooter className="px-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
            {([canSubmit]) => (
              <Button
                type="submit"
                disabled={!canSubmit || createMutation.isPending || updateMutation.isPending || (!isEditMode && (!selectedResource || !selectedAction)) || (form.state.values.scope === "platform" && !form.state.values.platform_id && !isEditMode)}
                onClick={form.handleSubmit}
              >
                {(createMutation.isPending || updateMutation.isPending) ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {isEditMode ? "Updating..." : "Creating..."}
                  </>
                ) : (
                  isEditMode ? "Update Permission" : "Create Permission"
                )}
              </Button>
            )}
          </form.Subscribe>
        </DrawerFooter>
      </DrawerContent>
      
      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the permission
              "{permissionData?.display_name}" and remove it from all roles that currently have it assigned.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => permissionData && deleteMutation.mutate(permissionData.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete Permission"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Drawer>
  );
}