import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "@tanstack/react-router";
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
import { Loader2, Trash2, AlertTriangle, Check, ChevronsUpDown, Search } from "lucide-react";
import { authenticatedFetch } from "@/lib/auth";
import { cn } from "@/lib/utils";
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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Entity,
  EntityClass,
  EntityType,
  getEntityTypeLabel,
} from "@/types/entity";
import { getEntityTypeIcon, getEntityClassIcon } from "@/lib/entity-icons";

interface EntityDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  entity?: Entity | null;
  defaultParentId?: string | null;
}

// Entity type options based on class
const structuralTypes = [
  EntityType.PLATFORM,
  EntityType.ORGANIZATION,
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
  return response.json();
}

export function EntityDrawer({ open, onOpenChange, mode, entity, defaultParentId }: EntityDrawerProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isEditMode = mode === "edit";
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [hasChildren, setHasChildren] = useState(false);
  const [enableCascade, setEnableCascade] = useState(false);
  const [selectedClass, setSelectedClass] = useState<EntityClass>(EntityClass.STRUCTURAL);
  const [parentEntityOpen, setParentEntityOpen] = useState(false);

  // Fetch all entities for parent selection
  const { data: allEntities } = useQuery({
    queryKey: ["entities"],
    queryFn: fetchEntities,
    enabled: open,
  });

  // Filter potential parent entities based on context
  const potentialParents = useMemo(() => {
    if (!allEntities) return [];
    
    let filtered = allEntities.filter(
      e => e.entity_class === EntityClass.STRUCTURAL && 
           e.status === "active" && 
           (!isEditMode || e.id !== entity?.id)
    );
    
    // If we have a default parent (creating within a context), 
    // only show that parent and its ancestors
    if (defaultParentId && !isEditMode) {
      const contextEntity = allEntities.find(e => e.id === defaultParentId);
      if (contextEntity) {
        // Get the context entity and all its ancestors
        const allowedIds = new Set<string>([defaultParentId]);
        
        // Find all ancestors of the context entity
        let current = contextEntity;
        while (current.parent_entity_id) {
          const parent = allEntities.find(e => e.id === current.parent_entity_id);
          if (parent) {
            allowedIds.add(parent.id);
            current = parent;
          } else {
            break;
          }
        }
        
        filtered = filtered.filter(e => allowedIds.has(e.id));
      }
    }
    
    return filtered;
  }, [allEntities, defaultParentId, isEditMode, entity?.id]);

  const mutation = useMutation({
    mutationFn: (data: Partial<Entity>) =>
      isEditMode && entity ? updateEntity(entity.id, data) : createEntity(data),
    onSuccess: () => {
      // Invalidate all entity-related queries
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      if (isEditMode && entity) {
        // Invalidate specific entity query
        queryClient.invalidateQueries({ queryKey: ["entity", entity.id] });
        queryClient.invalidateQueries({ queryKey: ["entity-path", entity.id] });
        queryClient.invalidateQueries({ queryKey: ["entity-children", entity.id] });
        queryClient.invalidateQueries({ queryKey: ["entity-members", entity.id] });
      }
      queryClient.invalidateQueries({ queryKey: ["all-entities"] });
      
      toast.success(isEditMode ? "Entity updated successfully!" : "Entity created successfully!");
      if (!isEditMode) {
        // Reset form values for create mode
        form.setFieldValue("name", "");
        form.setFieldValue("description", "");
        form.setFieldValue("entity_class", EntityClass.STRUCTURAL);
        form.setFieldValue("entity_type", "");
        form.setFieldValue("parent_entity", "none");
        form.setFieldValue("status", "active");
        form.setFieldValue("max_members", "");
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

      const url = `/v1/entities/${entity.id}${enableCascade ? '?cascade=true' : ''}`;
      await authenticatedFetch(url, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      // Invalidate all entity-related queries
      queryClient.invalidateQueries({ queryKey: ["entities"] });
      queryClient.invalidateQueries({ queryKey: ["all-entities"] });
      queryClient.invalidateQueries({ queryKey: ["entity"] });
      queryClient.invalidateQueries({ queryKey: ["entity-path"] });
      queryClient.invalidateQueries({ queryKey: ["entity-children"] });
      toast.success("Entity archived successfully!");
      onOpenChange(false);
      setShowDeleteDialog(false);
      
      // Navigate back to entities list or parent entity
      if (entity?.parent_entity_id) {
        navigate({ to: '/entities/$entityId', params: { entityId: entity.parent_entity_id } });
      } else {
        navigate({ to: '/entities' });
      }
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
      // Generate a system name from the display name
      const systemName = value.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_|_$/g, '');
      
      const data: any = {
        name: systemName,
        display_name: value.name,
        description: value.description,
        entity_class: value.entity_class, // Already uppercase from enum
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
      // Set form values individually
      form.setFieldValue("name", entity.name || "");
      form.setFieldValue("description", entity.description || "");
      form.setFieldValue("entity_class", entity.entity_class);
      form.setFieldValue("entity_type", entity.entity_type);
      form.setFieldValue("parent_entity", entity.parent_entity_id || "none");
      form.setFieldValue("status", entity.status || "active");
      form.setFieldValue("max_members", entity.max_members?.toString() || "");
      
      setSelectedClass(entity.entity_class);
    }
  }, [entity, isEditMode, open, form]);

  // Reset form when switching to create mode
  useEffect(() => {
    if (!isEditMode && open) {
      // If there's only one parent option and we have a defaultParentId, use it
      const parentValue = defaultParentId && potentialParents.length === 1 
        ? defaultParentId 
        : defaultParentId || "none";
      
      // Set form values individually
      form.setFieldValue("name", "");
      form.setFieldValue("description", "");
      form.setFieldValue("entity_class", EntityClass.STRUCTURAL);
      form.setFieldValue("entity_type", ""); // No default, force user to select
      form.setFieldValue("parent_entity", parentValue);
      form.setFieldValue("status", "active");
      form.setFieldValue("max_members", "");
      
      setSelectedClass(EntityClass.STRUCTURAL);
    }
  }, [isEditMode, open, defaultParentId, potentialParents, form]);

  // Get available entity types based on selected class and parent
  const availableTypes = useMemo(() => {
    if (selectedClass === EntityClass.ACCESS_GROUP) {
      return accessGroupTypes;
    }
    
    // For structural entities, filter based on parent's allowed children
    if (!isEditMode && form.state.values.parent_entity && form.state.values.parent_entity !== "none") {
      const parentEntity = potentialParents.find(p => p.id === form.state.values.parent_entity);
      if (parentEntity) {
        // Define hierarchy rules matching backend
        const hierarchyRules: Record<string, EntityType[]> = {
          [EntityType.PLATFORM]: [EntityType.ORGANIZATION, EntityType.BRANCH, EntityType.TEAM],
          [EntityType.ORGANIZATION]: [EntityType.BRANCH, EntityType.TEAM],
          [EntityType.BRANCH]: [EntityType.TEAM],
          [EntityType.TEAM]: [], // Teams can't have structural children
        };
        
        return hierarchyRules[parentEntity.entity_type] || [];
      }
    }
    
    // If no parent selected, allow platforms and organizations at root level
    if (!form.state.values.parent_entity || form.state.values.parent_entity === "none") {
      return [EntityType.PLATFORM, EntityType.ORGANIZATION];
    }
    
    return structuralTypes;
  }, [selectedClass, isEditMode, form.state.values.parent_entity, potentialParents, allEntities]);

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
                    A display name for this entity (system name will be generated automatically)
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
                      // Reset entity type when class changes to force selection
                      form.setFieldValue("entity_type", "");
                    }}
                    disabled={isEditMode}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={EntityClass.STRUCTURAL}>
                        <div className="flex items-center gap-2">
                          {(() => {
                            const Icon = getEntityClassIcon(EntityClass.STRUCTURAL);
                            return <Icon className="h-4 w-4" />;
                          })()}
                          <span>Structural Entity</span>
                        </div>
                      </SelectItem>
                      <SelectItem value={EntityClass.ACCESS_GROUP}>
                        <div className="flex items-center gap-2">
                          {(() => {
                            const Icon = getEntityClassIcon(EntityClass.ACCESS_GROUP);
                            return <Icon className="h-4 w-4" />;
                          })()}
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

            <form.Field 
              name="entity_type"
              validators={{
                onChange: ({ value }) => (!value ? "Entity type is required" : undefined),
              }}
            >
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="entity_type">Entity Type *</Label>
                  {availableTypes.length === 0 && selectedClass === EntityClass.STRUCTURAL ? (
                    <div className="rounded-lg border border-muted bg-muted/50 p-3">
                      <p className="text-sm text-muted-foreground">
                        The selected parent entity cannot have structural children.
                        Consider creating an access group instead.
                      </p>
                    </div>
                  ) : (
                    <Select
                      value={field.state.value}
                      onValueChange={(value: EntityType) => field.handleChange(value)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select an entity type" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableTypes.map(type => (
                          <SelectItem key={type} value={type}>
                            <div className="flex items-center gap-2">
                              {(() => {
                                const Icon = getEntityTypeIcon(type);
                                return <Icon className="h-4 w-4" />;
                              })()}
                              <span>{getEntityTypeLabel(type)}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  {field.state.meta.errors && (
                    <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                  )}
                </div>
              )}
            </form.Field>

            <form.Field name="parent_entity">
                {(field) => {
                  const selectedParent = field.state.value && field.state.value !== "none" 
                    ? potentialParents.find(p => p.id === field.state.value)
                    : null;
                  
                  return (
                    <div className="space-y-2">
                      <Label htmlFor="parent_entity">
                        {selectedClass === EntityClass.ACCESS_GROUP 
                          ? "Assign to Entity" 
                          : "Parent Entity"}
                      </Label>
                      <Popover open={parentEntityOpen} onOpenChange={setParentEntityOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            variant="outline"
                            role="combobox"
                            aria-expanded={parentEntityOpen}
                            className="w-full justify-between font-normal"
                          >
                            {selectedParent ? (
                              <div className="flex items-center gap-2">
                                {(() => {
                                  const Icon = getEntityTypeIcon(selectedParent.entity_type);
                                  return <Icon className="h-4 w-4" />;
                                })()}
                                <span>{selectedParent.name}</span>
                              </div>
                            ) : (
                              <span className="text-muted-foreground">Select parent entity (optional)</span>
                            )}
                            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-full p-0" align="start">
                          <Command>
                            <CommandInput 
                              placeholder={potentialParents.length > 0 ? "Search parent entities..." : "No other options available"} 
                              className="h-9"
                            />
                            <CommandList>
                              <CommandEmpty>No entities found.</CommandEmpty>
                              <CommandGroup>
                                {(!defaultParentId || isEditMode) && (
                                  <CommandItem
                                    value="none"
                                    onSelect={() => {
                                      field.handleChange("none");
                                      setParentEntityOpen(false);
                                      // Clear entity type to force selection
                                      form.setFieldValue("entity_type", "");
                                    }}
                                  >
                                    <Check
                                      className={cn(
                                        "mr-2 h-4 w-4",
                                        field.state.value === "none" ? "opacity-100" : "opacity-0"
                                      )}
                                    />
                                    No parent (root entity)
                                  </CommandItem>
                                )}
                                {potentialParents.map(parent => (
                                  <CommandItem
                                    key={parent.id}
                                    value={`${parent.name.toLowerCase()} ${parent.slug}`}
                                    onSelect={() => {
                                      field.handleChange(parent.id);
                                      setParentEntityOpen(false);
                                      // Clear entity type to force selection when parent changes
                                      form.setFieldValue("entity_type", "");
                                    }}
                                  >
                                    <Check
                                      className={cn(
                                        "mr-2 h-4 w-4",
                                        field.state.value === parent.id ? "opacity-100" : "opacity-0"
                                      )}
                                    />
                                    <div className="flex items-center gap-2">
                                      {(() => {
                                        const Icon = getEntityTypeIcon(parent.entity_type);
                                        return <Icon className="h-4 w-4" />;
                                      })()}
                                      <div className="flex flex-col">
                                        <span>{parent.name}</span>
                                        {parent.description && (
                                          <span className="text-xs text-muted-foreground">{parent.description}</span>
                                        )}
                                      </div>
                                    </div>
                                  </CommandItem>
                                ))}
                              </CommandGroup>
                            </CommandList>
                          </Command>
                        </PopoverContent>
                      </Popover>
                      <p className="text-xs text-muted-foreground">
                        {selectedClass === EntityClass.ACCESS_GROUP ? (
                          defaultParentId && !isEditMode 
                            ? "Access groups will be assigned to the current context"
                            : "Access groups are assigned to structural entities for organization"
                        ) : (
                          defaultParentId && !isEditMode 
                            ? "Parent selection is limited to the current context and its ancestors"
                            : "Create a hierarchy by selecting a parent entity"
                        )}
                      </p>
                    </div>
                  );
                }}
              </form.Field>

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

            {/* Danger Zone - Only show in edit mode and not for root platform */}
            {isEditMode && entity && 
             !(entity.metadata?.is_root || entity.slug === "root_platform") && (
              <div className="mt-8 space-y-4 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                  <h3 className="font-semibold text-destructive">Archive Zone</h3>
                </div>

                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium">Archive this entity</h4>
                    <p className="text-sm text-muted-foreground mt-1">
                      Archiving an entity will soft-delete it, removing it from active lists
                      and revoking all memberships. Archived entities are not permanently deleted.
                    </p>
                  </div>

                  <Button
                    variant="destructive"
                    onClick={async () => {
                      // Check if entity has children
                      if (entity) {
                        try {
                          const response = await authenticatedFetch(`/v1/entities/?parent_entity_id=${entity.id}&status=active`);
                          const data = await response.json();
                          setHasChildren(data.total > 0);
                        } catch (error) {
                          // If error checking children, assume no children
                          setHasChildren(false);
                        }
                      }
                      setShowDeleteDialog(true);
                    }}
                    className="w-full"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Archive Entity
                  </Button>
                </div>
              </div>
            )}
          </form>
        </div>

        <DrawerFooter className="px-6">
          <div className="flex gap-3 w-full">
            <Button variant="outline" onClick={() => onOpenChange(false)} className="flex-1">
              Cancel
            </Button>
            <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
              {([canSubmit]) => (
                <Button
                  type="submit"
                  disabled={!canSubmit || mutation.isPending}
                  onClick={form.handleSubmit}
                  className="flex-1"
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
          </div>
        </DrawerFooter>
      </DrawerContent>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={(open) => {
        setShowDeleteDialog(open);
        if (!open) {
          setEnableCascade(false); // Reset cascade state when dialog closes
        }
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <p>
                  This will archive the entity
                  <span className="font-semibold"> {entity?.name}</span> and:
                </p>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  <li>Remove it from all active lists</li>
                  <li>Revoke all user memberships in this entity</li>
                  <li>Disable all permissions assigned to this entity</li>
                  {hasChildren && <li className="text-destructive font-semibold">Archive all child entities and their data</li>}
                </ul>
                
                {hasChildren && (
                  <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 space-y-3">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-5 w-5 text-destructive mt-0.5" />
                      <div className="space-y-1">
                        <p className="font-semibold text-destructive">
                          Warning: This entity has child entities!
                        </p>
                        <p className="text-sm">
                          Deleting this entity will require cascading deletion of all its children.
                          This operation cannot be undone.
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <Checkbox 
                        id="cascade-delete" 
                        checked={enableCascade}
                        onCheckedChange={(checked) => setEnableCascade(checked as boolean)}
                      />
                      <label
                        htmlFor="cascade-delete"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                      >
                        I understand and want to archive all child entities
                      </label>
                    </div>
                  </div>
                )}
                
                {!hasChildren && (
                  <p className="text-sm text-muted-foreground">
                    The entity will be archived and removed from active views.
                  </p>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending || (hasChildren && !enableCascade)}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Archive Entity"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Drawer>
  );
}