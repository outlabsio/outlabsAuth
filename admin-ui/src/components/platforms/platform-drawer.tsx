import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import { Switch } from "@/components/ui/switch";
import { Loader2, Trash2, AlertTriangle } from "lucide-react";
import { authenticatedFetch } from "@/lib/auth";
import { toast } from "sonner";
import { useEffect, useState } from "react";
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
import { useRouter } from "@tanstack/react-router";

interface PlatformDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  platformId?: string | null;
  platformData?: Platform | null;
}

interface Platform {
  _id: string;
  name: string;
  description: string;
  status: "active" | "suspended";
  is_platform_root: boolean;
  platform_url?: string;
}

// Removed fetchPlatform as we're using passed data instead

async function createPlatform(data: {
  name: string;
  description: string;
  status: "active" | "suspended";
  platform_url: string;
}) {
  const response = await authenticatedFetch("/v1/platforms/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to create platform");
  }
  
  return response.json();
}

async function updatePlatform(id: string, data: {
  name: string;
  description: string;
  status: "active" | "suspended";
  platform_url: string;
}) {
  const response = await authenticatedFetch(`/v1/platforms/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to update platform");
  }
  
  return response.json();
}

export function PlatformDrawer({ open, onOpenChange, mode, platformId, platformData }: PlatformDrawerProps) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const isEditMode = mode === "edit";
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  
  // Use provided platform data instead of fetching
  const platform = isEditMode ? platformData : null;
  const isLoading = false;
  
  const mutation = useMutation({
    mutationFn: (data: { name: string; description: string; status: "active" | "suspended"; platform_url: string }) => 
      isEditMode && platformId 
        ? updatePlatform(platformId, data)
        : createPlatform(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platforms"] });
      if (isEditMode) {
        queryClient.invalidateQueries({ queryKey: ["platform", platformId] });
      }
      toast.success(isEditMode ? "Platform updated successfully!" : "Platform created successfully!");
      onOpenChange(false);
      if (!isEditMode) {
        form.reset();
      }
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!platformId) throw new Error("No platform ID");
      
      const response = await authenticatedFetch(`/v1/platforms/${platformId}`, {
        method: "DELETE",
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to delete platform");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platforms"] });
      toast.success("Platform deleted successfully!");
      onOpenChange(false);
      setShowDeleteDialog(false);
      // Navigate back to platforms list
      router.navigate({ to: "/platforms" });
    },
    onError: (error: Error) => {
      toast.error(error.message);
      setShowDeleteDialog(false);
    },
  });
  
  const form = useForm({
    defaultValues: {
      name: "",
      description: "",
      status: "active" as "active" | "suspended",
      platform_url: "",
    },
    onSubmit: async ({ value }) => {
      await mutation.mutateAsync(value);
    },
  });
  
  // Update form when platform data is loaded (edit mode)
  useEffect(() => {
    if (isEditMode && platform && open) {
      form.reset({
        name: platform.name || "",
        description: platform.description || "",
        status: platform.status || "active",
        platform_url: platform.platform_url || "",
      });
    }
  }, [platform, isEditMode, open, form]);
  
  // Reset form when switching to create mode
  useEffect(() => {
    if (!isEditMode && open) {
      form.reset();
    }
  }, [isEditMode, open]);
  
  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full max-w-xl h-full flex flex-col">
        <DrawerHeader className="px-6">
          <DrawerTitle>{isEditMode ? "Edit Platform" : "Create New Platform"}</DrawerTitle>
          <DrawerDescription>
            {isEditMode 
              ? "Update platform details and configuration"
              : "Set up a new multi-tenant platform for your organization"}
          </DrawerDescription>
        </DrawerHeader>
        
        <div className="overflow-y-auto px-6 py-4 flex-1">
          {isEditMode && isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                e.stopPropagation();
                form.handleSubmit();
              }}
              className="space-y-6"
            >
              <form.Field
                name="name"
                validators={{
                  onChange: ({ value }) => (!value ? "Platform name is required" : undefined),
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="name">Platform Name</Label>
                    <Input
                      id="name"
                      placeholder="e.g., Real Estate Platform, Healthcare Platform"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    <p className="text-xs text-muted-foreground">
                      A unique name to identify this platform
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
                      placeholder="Describe the purpose and scope of this platform"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                      rows={4}
                    />
                    <p className="text-xs text-muted-foreground">
                      Help others understand what this platform is for
                    </p>
                    {field.state.meta.errors && (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    )}
                  </div>
                )}
              </form.Field>
              
              <form.Field
                name="platform_url"
                validators={{
                  onChange: ({ value }) => {
                    if (value && !value.match(/^https?:\/\/.*/)) {
                      return "Platform URL must start with http:// or https://";
                    }
                    return undefined;
                  },
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="platform_url">Platform URL</Label>
                    <Input
                      id="platform_url"
                      placeholder="https://example.com"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    <p className="text-xs text-muted-foreground">
                      The main URL for this platform
                    </p>
                    {field.state.meta.errors && (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    )}
                  </div>
                )}
              </form.Field>
              
              <form.Field name="status">
                {(field) => (
                  <div className="flex items-center justify-between rounded-lg border p-4">
                    <div className="space-y-0.5">
                      <Label htmlFor="status">Active Status</Label>
                      <p className="text-sm text-muted-foreground">
                        {field.state.value === "active" 
                          ? "Platform is currently active" 
                          : "Platform is suspended"}
                      </p>
                    </div>
                    <Switch
                      id="status"
                      checked={field.state.value === "active"}
                      onCheckedChange={(checked) => field.handleChange(checked ? "active" : "suspended")}
                    />
                  </div>
                )}
              </form.Field>
              
              {/* Danger Zone - Only show in edit mode */}
              {isEditMode && (
                <div className="mt-8 space-y-4 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-destructive" />
                    <h3 className="font-semibold text-destructive">Danger Zone</h3>
                  </div>
                  
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-medium">Delete this platform</h4>
                      <p className="text-sm text-muted-foreground mt-1">
                        Once you delete a platform, there is no going back. This will permanently delete the platform
                        and all associated users, roles, permissions, and groups.
                      </p>
                    </div>
                    
                    <Button
                      variant="destructive"
                      onClick={() => setShowDeleteDialog(true)}
                      className="w-full"
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete Platform
                    </Button>
                  </div>
                </div>
              )}
            </form>
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
                disabled={!canSubmit || mutation.isPending || (isEditMode && isLoading)}
                onClick={form.handleSubmit}
              >
                {mutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {isEditMode ? "Updating..." : "Creating..."}
                  </>
                ) : (
                  isEditMode ? "Update Platform" : "Create Platform"
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
            <AlertDialogDescription className="space-y-2">
              <p>
                This action cannot be undone. This will permanently delete the platform
                <span className="font-semibold"> {platform?.name}</span> and remove all associated data:
              </p>
              <ul className="list-disc list-inside space-y-1 text-sm">
                <li>All users associated with this platform</li>
                <li>All roles and permissions</li>
                <li>All groups and their assignments</li>
                <li>All configuration and settings</li>
              </ul>
              <p className="font-semibold text-destructive">
                This is a destructive action that cannot be reversed.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete Platform"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Drawer>
  );
}