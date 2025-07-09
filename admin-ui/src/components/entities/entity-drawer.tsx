import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Trash2, AlertTriangle } from "lucide-react";
import { authenticatedFetch } from "@/lib/auth";
import { toast } from "sonner";
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
import {
  Entity,
  EntityClass,
  EntityType,
  getEntityTypeLabel,
  getEntityTypeIcon,
  getEntityClassIcon,
} from "@/types/entity";

interface EntityDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  entity?: Entity | null;
}

// Entity type options based on class
const structuralTypes = [
  EntityType.PLATFORM,
  EntityType.ORGANIZATION,
  EntityType.DIVISION,
  EntityType.BRANCH,
  EntityType.TEAM,
];

const accessGroupTypes = [
  EntityType.FUNCTIONAL_GROUP,
  EntityType.PERMISSION_GROUP,
  EntityType.PROJECT_GROUP,
  EntityType.ROLE_GROUP,
  EntityType.ACCESS_GROUP,
];

async function fetchEntities(): Promise<Entity[]> {
  const response = await authenticatedFetch("/v1/entities/");
  if (!response.ok) {
    throw new Error("Failed to fetch entities");
  }
  const data = await response.json();
  // API returns paginated response, extract items array
  return data.items || [];
}

async function createEntity(data: Partial<Entity>) {
  const response = await authenticatedFetch("/v1/entities/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorData = await response.json();
    // Pass the full error data as JSON string for better error handling
    throw new Error(JSON.stringify(errorData));
  }

  return response.json();
}

async function updateEntity(id: string, data: Partial<Entity>) {
  const response = await authenticatedFetch(`/v1/entities/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorData = await response.json();
    // Pass the full error data as JSON string for better error handling
    throw new Error(JSON.stringify(errorData));
  }

  return response.json();
}

export function EntityDrawer({ open, onOpenChange, mode, entity }: EntityDrawerProps) {
  const queryClient = useQueryClient();
  const isEditMode = mode === "edit";
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [selectedClass, setSelectedClass] = useState<EntityClass>(EntityClass.STRUCTURAL);

  // Fetch all entities for parent selection
  const { data: allEntities } = useQuery({
    queryKey: ["entities"],
    queryFn: fetchEntities,
    enabled: open,
  });

  // Filter potential parent entities (only structural entities can be parents)
  const potentialParents = allEntities?.filter(
    e => e.entity_class === EntityClass.STRUCTURAL && (!isEditMode || e.id !== entity?.id)
  ) || [];

  const mutation = useMutation({
    mutationFn: (data: Partial<Entity>) =>
      isEditMode && entity ? updateEntity(entity.id, data) : createEntity(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      toast.success(isEditMode ? "Entity updated successfully!" : "Entity created successfully!");
      if (!isEditMode) {
        form.reset();
      }
      // Close drawer after a short delay to show success message
      setTimeout(() => {
        onOpenChange(false);
      }, 500);
    },
    onError: (error: any) => {
      // Handle validation errors from API
      if (error.message) {
        try {
          const errorData = JSON.parse(error.message);
          if (errorData.detail && Array.isArray(errorData.detail)) {
            // Format validation errors
            const messages = errorData.detail.map((err: any) => 
              `${err.loc.join('.')}: ${err.msg}`
            ).join(', ');
            toast.error(messages);
          } else if (errorData.detail) {
            toast.error(errorData.detail);
          } else {
            toast.error(error.message);
          }
        } catch {
          toast.error(error.message);
        }
      } else {
        toast.error("An error occurred");
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!entity) throw new Error("No entity to delete");

      const response = await authenticatedFetch(`/v1/entities/${entity.id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to delete entity");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      toast.success("Entity deleted successfully!");
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
      name: "",
      description: "",
      entity_class: EntityClass.STRUCTURAL,
      entity_type: EntityType.ORGANIZATION,
      parent_entity: "none",
      status: "active" as "active" | "inactive" | "archived",
      max_members: "",
    },
    onSubmit: async ({ value }) => {
      const data: any = {
        name: value.name,
        display_name: value.name, // API expects display_name
        description: value.description,
        entity_class: value.entity_class.toUpperCase(), // API expects uppercase
        entity_type: value.entity_type,
        status: value.status,
      };

      if (value.parent_entity && value.parent_entity !== "none") {
        data.parent_entity_id = value.parent_entity;
      }

      if (value.max_members) {
        data.max_members = parseInt(value.max_members);
      }

      await mutation.mutateAsync(data);
    },
  });

  // Update form when entity data is loaded (edit mode)
  useEffect(() => {
    if (isEditMode && entity && open) {
      form.reset({
        name: entity.name || "",
        description: entity.description || "",
        entity_class: entity.entity_class,
        entity_type: entity.entity_type,
        parent_entity: typeof entity.parent_entity === 'string' 
          ? entity.parent_entity 
          : entity.parent_entity?.id || "none",
        status: entity.status || "active",
        max_members: entity.max_members?.toString() || "",
      });
      setSelectedClass(entity.entity_class);
    }
  }, [entity, isEditMode, open, form]);

  // Reset form when switching to create mode
  useEffect(() => {
    if (!isEditMode && open) {
      form.reset();
      setSelectedClass(EntityClass.STRUCTURAL);
    }
  }, [isEditMode, open]);

  // Get available entity types based on selected class
  const availableTypes = selectedClass === EntityClass.STRUCTURAL 
    ? structuralTypes 
    : accessGroupTypes;

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full max-w-xl h-full flex flex-col">
        <DrawerHeader className="px-6">
          <DrawerTitle>{isEditMode ? "Edit Entity" : "Create New Entity"}</DrawerTitle>
          <DrawerDescription>
            {isEditMode
              ? "Update entity details and configuration"
              : "Set up a new entity in your organizational structure"}
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
            <form.Field
              name="name"
              validators={{
                onChange: ({ value }) => (!value ? "Entity name is required" : undefined),
              }}
            >
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="name">Entity Name</Label>
                  <Input
                    id="name"
                    placeholder="e.g., Acme Corporation, Engineering Team"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                  />
                  <p className="text-xs text-muted-foreground">
                    A unique name to identify this entity
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
                    placeholder="Describe the purpose and scope of this entity"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                    rows={3}
                  />
                </div>
              )}
            </form.Field>

            <form.Field name="entity_class">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="entity_class">Entity Class</Label>
                  <Select
                    value={field.state.value}
                    onValueChange={(value: EntityClass) => {
                      field.handleChange(value);
                      setSelectedClass(value);
                      // Reset entity type when class changes
                      form.setFieldValue("entity_type", 
                        value === EntityClass.STRUCTURAL 
                          ? EntityType.ORGANIZATION 
                          : EntityType.FUNCTIONAL_GROUP
                      );
                    }}
                    disabled={isEditMode}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={EntityClass.STRUCTURAL}>
                        <div className="flex items-center gap-2">
                          <span>{getEntityClassIcon(EntityClass.STRUCTURAL)}</span>
                          <span>Structural Entity</span>
                        </div>
                      </SelectItem>
                      <SelectItem value={EntityClass.ACCESS_GROUP}>
                        <div className="flex items-center gap-2">
                          <span>{getEntityClassIcon(EntityClass.ACCESS_GROUP)}</span>
                          <span>Access Group</span>
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {selectedClass === EntityClass.STRUCTURAL
                      ? "Organizational units in your hierarchy"
                      : "Groups for managing permissions and access"}
                  </p>
                </div>
              )}
            </form.Field>

            <form.Field name="entity_type">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="entity_type">Entity Type</Label>
                  <Select
                    value={field.state.value}
                    onValueChange={(value: EntityType) => field.handleChange(value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {availableTypes.map(type => (
                        <SelectItem key={type} value={type}>
                          <div className="flex items-center gap-2">
                            <span>{getEntityTypeIcon(type)}</span>
                            <span>{getEntityTypeLabel(type)}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </form.Field>

            {selectedClass === EntityClass.STRUCTURAL && (
              <form.Field name="parent_entity">
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="parent_entity">Parent Entity</Label>
                    <Select
                      value={field.state.value}
                      onValueChange={(value) => field.handleChange(value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select parent entity (optional)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No parent (root entity)</SelectItem>
                        {potentialParents.map(parent => (
                          <SelectItem key={parent.id} value={parent.id}>
                            <div className="flex items-center gap-2">
                              <span>{getEntityTypeIcon(parent.entity_type)}</span>
                              <span>{parent.name}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Create a hierarchy by selecting a parent entity
                    </p>
                  </div>
                )}
              </form.Field>
            )}

            <form.Field name="max_members">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="max_members">Maximum Members (Optional)</Label>
                  <Input
                    id="max_members"
                    type="number"
                    placeholder="No limit"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                    min="0"
                  />
                  <p className="text-xs text-muted-foreground">
                    Leave empty for unlimited members
                  </p>
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
                        ? "Entity is currently active"
                        : field.state.value === "inactive"
                        ? "Entity is inactive"
                        : "Entity is archived"}
                    </p>
                  </div>
                  <Select
                    value={field.state.value}
                    onValueChange={(value: "active" | "inactive" | "archived") => field.handleChange(value)}
                  >
                    <SelectTrigger className="w-[140px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                      <SelectItem value="archived">Archived</SelectItem>
                    </SelectContent>
                  </Select>
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
                    <h4 className="font-medium">Delete this entity</h4>
                    <p className="text-sm text-muted-foreground mt-1">
                      Once you delete an entity, there is no going back. This will permanently delete
                      the entity and all associated memberships and permissions.
                    </p>
                  </div>

                  <Button
                    variant="destructive"
                    onClick={() => setShowDeleteDialog(true)}
                    className="w-full"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Entity
                  </Button>
                </div>
              </div>
            )}
          </form>
        </div>

        <DrawerFooter className="px-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
            {([canSubmit]) => (
              <Button
                type="submit"
                disabled={!canSubmit || mutation.isPending}
                onClick={form.handleSubmit}
              >
                {mutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {isEditMode ? "Updating..." : "Creating..."}
                  </>
                ) : (
                  isEditMode ? "Update Entity" : "Create Entity"
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
                This action cannot be undone. This will permanently delete the entity
                <span className="font-semibold"> {entity?.name}</span> and remove all
                associated data:
              </p>
              <ul className="list-disc list-inside space-y-1 text-sm">
                <li>All user memberships in this entity</li>
                <li>All permissions assigned to this entity</li>
                <li>All child entities (if any)</li>
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
                "Delete Entity"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Drawer>
  );
}