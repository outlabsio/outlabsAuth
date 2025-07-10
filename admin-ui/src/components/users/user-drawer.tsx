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
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Loader2, X, Building2, Shield, Check, ChevronsUpDown } from "lucide-react";
import { authenticatedFetch } from "@/lib/auth";
import { toast } from "sonner";
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
import { cn } from "@/lib/utils";

interface UserDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  user?: any;
  defaultEntityId?: string;
}

interface Entity {
  id: string;
  name: string;
  slug: string;
  entity_type: string;
  entity_class: string;
  description?: string;
  parent_entity_id?: string;
}

interface Role {
  id: string;
  name: string;
  description?: string;
  entity_id?: string;
  entity_name?: string;
}

async function fetchEntities(): Promise<Entity[]> {
  const response = await authenticatedFetch("/v1/entities/?status=active");
  const data = await response.json();
  return data.items || [];
}

async function fetchRoles(): Promise<Role[]> {
  const response = await authenticatedFetch("/v1/roles/");
  const data = await response.json();
  return data.items || [];
}

async function createUser(data: any) {
  const response = await authenticatedFetch("/v1/users/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  return response.json();
}

async function updateUser(userId: string, data: any) {
  const response = await authenticatedFetch(`/v1/users/${userId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  return response.json();
}

export function UserDrawer({ open, onOpenChange, mode, user, defaultEntityId }: UserDrawerProps) {
  const queryClient = useQueryClient();
  const isEditMode = mode === "edit";
  const [selectedEntities, setSelectedEntities] = useState<string[]>([]);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [entitySearchOpen, setEntitySearchOpen] = useState(false);
  const [roleSearchOpen, setRoleSearchOpen] = useState(false);

  // Fetch entities and roles
  const { data: entities = [] } = useQuery({
    queryKey: ["entities-all"],
    queryFn: fetchEntities,
    enabled: open,
  });

  const { data: roles = [] } = useQuery({
    queryKey: ["roles-all"],
    queryFn: fetchRoles,
    enabled: open,
  });

  // Group roles by entity
  const rolesByEntity = roles.reduce((acc, role) => {
    const key = role.entity_id || "global";
    if (!acc[key]) acc[key] = [];
    acc[key].push(role);
    return acc;
  }, {} as Record<string, Role[]>);

  const mutation = useMutation({
    mutationFn: (data: any) =>
      isEditMode && user ? updateUser(user.id, data) : createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success(isEditMode ? "User updated successfully!" : "User created successfully!");
      setTimeout(() => {
        onOpenChange(false);
      }, 500);
    },
    onError: (error: any) => {
      const message = error.detail || error.message || "An error occurred";
      toast.error(message);
    },
  });

  const form = useForm({
    defaultValues: {
      email: "",
      first_name: "",
      last_name: "",
      password: "",
      is_active: true,
      send_invite: !isEditMode,
    },
    onSubmit: async ({ value }) => {
      const data: any = {
        email: value.email,
        first_name: value.first_name,
        last_name: value.last_name,
        is_active: value.is_active,
      };

      // Only include password for new users or if changed
      if (!isEditMode || value.password) {
        data.password = value.password;
      }

      // Transform to entity_assignments format expected by backend
      if (selectedEntities.length > 0) {
        // Group roles by their parent entity
        const entityAssignments = selectedEntities.map(entityId => {
          // Find roles that belong to this entity
          const entityRoles = selectedRoles.filter(roleId => {
            const role = roles.find(r => r.id === roleId);
            return role && role.entity_id === entityId;
          });
          
          return {
            entity_id: entityId,
            role_ids: entityRoles, // Can be empty array if no roles selected
            status: "active"
          };
        });
        
        data.entity_assignments = entityAssignments;
      }

      // Add send_invite flag for new users
      if (!isEditMode) {
        data.send_invite = value.send_invite;
      }

      await mutation.mutateAsync(data);
    },
  });

  // Update form when user data is loaded (edit mode)
  useEffect(() => {
    if (isEditMode && user && open) {
      console.log("UserDrawer: Editing user", user);
      form.reset({
        email: user.email || "",
        first_name: user.profile?.first_name || "",
        last_name: user.profile?.last_name || "",
        password: "", // Don't populate password
        is_active: user.is_active ?? true,
        is_platform_admin: false,
        send_invite: false,
      });
      setSelectedEntities(user.entities?.map((e: any) => e.id) || []);
      // Extract all roles from all entities
      const allRoles = user.entities?.flatMap((e: any) => e.roles?.map((r: any) => r.id) || []) || [];
      setSelectedRoles(allRoles);
    }
  }, [user, isEditMode, open]);

  // Reset form when switching to create mode
  useEffect(() => {
    if (!isEditMode && open) {
      form.reset({
        email: "",
        first_name: "",
        last_name: "",
        password: "",
        is_active: true,
        send_invite: true,
      });
      // If we have a default entity (organization context), pre-select it
      setSelectedEntities(defaultEntityId ? [defaultEntityId] : []);
      setSelectedRoles([]);
    }
  }, [isEditMode, open, form, defaultEntityId]);

  const getSelectedEntitiesDisplay = () => {
    if (selectedEntities.length === 0) return "Select entities...";
    const selected = entities.filter(e => selectedEntities.includes(e.id));
    if (selected.length <= 2) {
      return selected.map(e => e.name).join(", ");
    }
    return `${selected.length} entities selected`;
  };

  const getSelectedRolesDisplay = () => {
    if (selectedRoles.length === 0) return "Select roles...";
    const selected = roles.filter(r => selectedRoles.includes(r.id));
    if (selected.length <= 2) {
      return selected.map(r => r.name).join(", ");
    }
    return `${selected.length} roles selected`;
  };

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full max-w-xl h-full flex flex-col">
        <DrawerHeader className="px-6">
          <DrawerTitle>{isEditMode ? "Edit User" : "Create New User"}</DrawerTitle>
          <DrawerDescription>
            {isEditMode
              ? "Update user details and access permissions"
              : "Add a new user to the system with entity and role assignments"}
          </DrawerDescription>
        </DrawerHeader>

        <div className="overflow-y-auto flex-1 px-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              e.stopPropagation();
              form.handleSubmit();
            }}
            className="space-y-6 py-4"
          >
            {/* Basic Information */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">Basic Information</h3>
              
              <form.Field
                name="email"
                validators={{
                  onChange: ({ value }) => {
                    if (!value) return "Email is required";
                    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                      return "Invalid email format";
                    }
                    return undefined;
                  },
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="user@example.com"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                      disabled={isEditMode} // Email cannot be changed
                    />
                    {field.state.meta.errors && (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    )}
                  </div>
                )}
              </form.Field>

              <div className="grid grid-cols-2 gap-4">
                <form.Field
                  name="first_name"
                  validators={{
                    onChange: ({ value }) => (!value ? "First name is required" : undefined),
                  }}
                >
                  {(field) => (
                    <div className="space-y-2">
                      <Label htmlFor="first_name">First Name</Label>
                      <Input
                        id="first_name"
                        placeholder="John"
                        value={field.state.value}
                        onChange={(e) => field.handleChange(e.target.value)}
                        onBlur={field.handleBlur}
                      />
                      {field.state.meta.errors && (
                        <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                      )}
                    </div>
                  )}
                </form.Field>

                <form.Field
                  name="last_name"
                  validators={{
                    onChange: ({ value }) => (!value ? "Last name is required" : undefined),
                  }}
                >
                  {(field) => (
                    <div className="space-y-2">
                      <Label htmlFor="last_name">Last Name</Label>
                      <Input
                        id="last_name"
                        placeholder="Doe"
                        value={field.state.value}
                        onChange={(e) => field.handleChange(e.target.value)}
                        onBlur={field.handleBlur}
                      />
                      {field.state.meta.errors && (
                        <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                      )}
                    </div>
                  )}
                </form.Field>
              </div>

              <form.Field
                name="password"
                validators={{
                  onChange: ({ value }) => {
                    if (!isEditMode && !value) return "Password is required";
                    if (value && value.length < 8) return "Password must be at least 8 characters";
                    return undefined;
                  },
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="password">
                      Password {isEditMode && "(leave blank to keep current)"}
                    </Label>
                    <Input
                      id="password"
                      type="password"
                      placeholder={isEditMode ? "••••••••" : "Enter password"}
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    {field.state.meta.errors && (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    )}
                  </div>
                )}
              </form.Field>
            </div>

            {/* Entity Assignments */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">Entity Access</h3>
              {defaultEntityId && entities.find(e => e.id === defaultEntityId) && (
                <div className="text-sm text-muted-foreground bg-muted/50 rounded-lg p-3">
                  <p>Creating user within <span className="font-medium">{entities.find(e => e.id === defaultEntityId)?.name}</span> context</p>
                </div>
              )}
              <div className="space-y-2">
                <Label>Assigned Entities</Label>
                <Popover open={entitySearchOpen} onOpenChange={setEntitySearchOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      role="combobox"
                      aria-expanded={entitySearchOpen}
                      className="w-full justify-between font-normal"
                    >
                      <span className="truncate">{getSelectedEntitiesDisplay()}</span>
                      <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-full p-0" align="start">
                    <Command>
                      <CommandInput placeholder="Search entities..." />
                      <CommandList>
                        <CommandEmpty>No entities found.</CommandEmpty>
                        <CommandGroup>
                          {entities.map((entity) => (
                            <CommandItem
                              key={entity.id}
                              value={`${entity.name} ${entity.slug}`}
                              onSelect={() => {
                                setSelectedEntities(prev =>
                                  prev.includes(entity.id)
                                    ? prev.filter(id => id !== entity.id)
                                    : [...prev, entity.id]
                                );
                              }}
                            >
                              <Check
                                className={cn(
                                  "mr-2 h-4 w-4",
                                  selectedEntities.includes(entity.id) ? "opacity-100" : "opacity-0"
                                )}
                              />
                              <Building2 className="mr-2 h-4 w-4" />
                              <div className="flex flex-col">
                                <span>{entity.name}</span>
                                {entity.description && (
                                  <span className="text-xs text-muted-foreground">{entity.description}</span>
                                )}
                              </div>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
                <p className="text-xs text-muted-foreground">
                  Select entities this user should have access to
                </p>
              </div>

              {/* Show selected entities */}
              {selectedEntities.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {selectedEntities.map(id => {
                    const entity = entities.find(e => e.id === id);
                    return entity ? (
                      <Badge key={id} variant="secondary">
                        {entity.name}
                        <button
                          type="button"
                          onClick={() => setSelectedEntities(prev => prev.filter(eid => eid !== id))}
                          className="ml-1"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ) : null;
                  })}
                </div>
              )}
            </div>

            {/* Role Assignments */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">Role Assignments</h3>
              <div className="space-y-2">
                <Label>Assigned Roles</Label>
                <Popover open={roleSearchOpen} onOpenChange={setRoleSearchOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      role="combobox"
                      aria-expanded={roleSearchOpen}
                      className="w-full justify-between font-normal"
                    >
                      <span className="truncate">{getSelectedRolesDisplay()}</span>
                      <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-full p-0" align="start">
                    <Command>
                      <CommandInput placeholder="Search roles..." />
                      <CommandList>
                        <CommandEmpty>No roles found.</CommandEmpty>
                        {Object.entries(rolesByEntity).map(([entityId, entityRoles]) => {
                          const entity = entities.find(e => e.id === entityId);
                          const entityName = entity?.name || "Global Roles";
                          
                          return (
                            <CommandGroup key={entityId} heading={entityName}>
                              {entityRoles.map((role) => (
                                <CommandItem
                                  key={role.id}
                                  value={`${role.name} ${entityName}`}
                                  onSelect={() => {
                                    setSelectedRoles(prev =>
                                      prev.includes(role.id)
                                        ? prev.filter(id => id !== role.id)
                                        : [...prev, role.id]
                                    );
                                  }}
                                >
                                  <Check
                                    className={cn(
                                      "mr-2 h-4 w-4",
                                      selectedRoles.includes(role.id) ? "opacity-100" : "opacity-0"
                                    )}
                                  />
                                  <Shield className="mr-2 h-4 w-4" />
                                  <div className="flex flex-col">
                                    <span>{role.name}</span>
                                    {role.description && (
                                      <span className="text-xs text-muted-foreground">{role.description}</span>
                                    )}
                                  </div>
                                </CommandItem>
                              ))}
                            </CommandGroup>
                          );
                        })}
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
                <p className="text-xs text-muted-foreground">
                  Roles determine what actions users can perform
                </p>
              </div>

              {/* Show selected roles */}
              {selectedRoles.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {selectedRoles.map(id => {
                    const role = roles.find(r => r.id === id);
                    return role ? (
                      <Badge key={id} variant="default">
                        {role.name}
                        {role.entity_name && (
                          <span className="ml-1 opacity-70">@ {role.entity_name}</span>
                        )}
                        <button
                          type="button"
                          onClick={() => setSelectedRoles(prev => prev.filter(rid => rid !== id))}
                          className="ml-1"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ) : null;
                  })}
                </div>
              )}
            </div>

            {/* Settings */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">Settings</h3>
              
              <form.Field name="is_active">
                {(field) => (
                  <div className="flex items-center justify-between rounded-lg border p-4">
                    <div className="space-y-0.5">
                      <Label htmlFor="is_active">Active Status</Label>
                      <p className="text-sm text-muted-foreground">
                        {field.state.value
                          ? "User can sign in and access the system"
                          : "User is deactivated and cannot sign in"}
                      </p>
                    </div>
                    <Switch
                      id="is_active"
                      checked={field.state.value}
                      onCheckedChange={field.handleChange}
                    />
                  </div>
                )}
              </form.Field>


              {!isEditMode && (
                <form.Field name="send_invite">
                  {(field) => (
                    <div className="flex items-center justify-between rounded-lg border p-4">
                      <div className="space-y-0.5">
                        <Label htmlFor="send_invite">Send Invitation Email</Label>
                        <p className="text-sm text-muted-foreground">
                          {field.state.value
                            ? "User will receive an email invitation to set their password"
                            : "User will need to be given their password manually"}
                        </p>
                      </div>
                      <Switch
                        id="send_invite"
                        checked={field.state.value}
                        onCheckedChange={field.handleChange}
                      />
                    </div>
                  )}
                </form.Field>
              )}
            </div>
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
                    isEditMode ? "Update User" : "Create User"
                  )}
                </Button>
              )}
            </form.Subscribe>
          </div>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}