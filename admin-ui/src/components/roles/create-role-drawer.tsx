import { useState } from "react";
import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Shield, Globe, Building2, Search, Info } from "lucide-react";
import { authenticatedFetch } from "@/lib/auth";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface CreateRoleDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface Permission {
  id: string;
  name: string;
  display_name: string;
  description: string;
  scope: string;
}

interface PermissionGroup {
  resource: string;
  permissions: Permission[];
}

interface AvailablePermissionsResponse {
  system_permissions: Permission[];
  platform_permissions: Permission[];
  client_permissions: Permission[];
}

// Permission hierarchy map
const PERMISSION_HIERARCHY: Record<string, string[]> = {
  "user:manage_all": ["user:manage_platform", "user:manage_client", "user:read_all", "user:read_platform", "user:read_client", "user:read_self"],
  "user:manage_platform": ["user:manage_client", "user:read_platform", "user:read_client", "user:read_self"],
  "user:manage_client": ["user:read_client", "user:read_self"],
  "user:read_all": ["user:read_platform", "user:read_client", "user:read_self"],
  "user:read_platform": ["user:read_client", "user:read_self"],
  "user:read_client": ["user:read_self"],
  
  "role:manage_all": ["role:manage_platform", "role:manage_client", "role:read_all", "role:read_platform", "role:read_client"],
  "role:manage_platform": ["role:manage_client", "role:read_platform", "role:read_client"],
  "role:manage_client": ["role:read_client"],
  "role:read_all": ["role:read_platform", "role:read_client"],
  "role:read_platform": ["role:read_client"],
  
  "group:manage_all": ["group:manage_platform", "group:manage_client", "group:read_all", "group:read_platform", "group:read_client"],
  "group:manage_platform": ["group:manage_client", "group:read_platform", "group:read_client"],
  "group:manage_client": ["group:read_client"],
  "group:read_all": ["group:read_platform", "group:read_client"],
  "group:read_platform": ["group:read_client"],
  
  "client:manage_all": ["client:manage_platform", "client:read_all", "client:read_platform", "client:read_own"],
  "client:manage_platform": ["client:read_platform", "client:read_own"],
  "client:read_all": ["client:read_platform", "client:read_own"],
  "client:read_platform": ["client:read_own"],
  
  "permission:manage_all": ["permission:manage_platform", "permission:manage_client", "permission:read_all", "permission:read_platform", "permission:read_client"],
  "permission:manage_platform": ["permission:manage_client", "permission:read_platform", "permission:read_client"],
  "permission:manage_client": ["permission:read_client"],
  "permission:read_all": ["permission:read_platform", "permission:read_client"],
  "permission:read_platform": ["permission:read_client"],
};

async function fetchAvailablePermissions(): Promise<AvailablePermissionsResponse> {
  const response = await authenticatedFetch("/v1/permissions/available");
  return response.json();
}

async function createRole(data: {
  name: string;
  display_name: string;
  description: string;
  scope: string;
  permissions: string[];
  is_assignable_by_main_client: boolean;
}) {
  const response = await authenticatedFetch("/v1/roles/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  
  return response.json();
}

function groupPermissionsByResource(permissions: Permission[]): PermissionGroup[] {
  const groups: Record<string, Permission[]> = {};
  
  permissions.forEach((permission) => {
    const resource = permission.name.split(":")[0];
    if (!groups[resource]) {
      groups[resource] = [];
    }
    groups[resource].push(permission);
  });
  
  return Object.entries(groups).map(([resource, perms]) => ({
    resource,
    permissions: perms.sort((a, b) => {
      // Sort by hierarchy level (manage > read, all > platform > client > self)
      const order = ["manage_all", "manage_platform", "manage_client", "read_all", "read_platform", "read_client", "read_self", "read_own"];
      const aIndex = order.findIndex(o => a.name.includes(o));
      const bIndex = order.findIndex(o => b.name.includes(o));
      return aIndex - bIndex;
    }),
  }));
}

function getInheritedPermissions(selectedPermissions: string[]): Set<string> {
  const inherited = new Set<string>();
  
  selectedPermissions.forEach((perm) => {
    const includes = PERMISSION_HIERARCHY[perm] || [];
    includes.forEach((included) => inherited.add(included));
  });
  
  return inherited;
}

export function CreateRoleDrawer({ open, onOpenChange }: CreateRoleDrawerProps) {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const inheritedPermissions = getInheritedPermissions(selectedPermissions);
  
  const { data: availablePermissions, isLoading: permissionsLoading } = useQuery({
    queryKey: ["permissions", "available"],
    queryFn: fetchAvailablePermissions,
    enabled: open,
  });
  
  const createMutation = useMutation({
    mutationFn: createRole,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast.success("Role created successfully!");
      onOpenChange(false);
      form.reset();
      setSelectedPermissions([]);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  const form = useForm({
    defaultValues: {
      name: "",
      display_name: "",
      description: "",
      scope: "client",
      is_assignable_by_main_client: false,
    },
    onSubmit: async ({ value }) => {
      await createMutation.mutateAsync({
        ...value,
        permissions: selectedPermissions,
      });
    },
  });
  
  // Get all permissions based on selected scope
  const getScopePermissions = () => {
    if (!availablePermissions) return [];
    
    const scope = form.state.values.scope;
    switch (scope) {
      case "system":
        return availablePermissions.system_permissions || [];
      case "platform":
        return availablePermissions.platform_permissions || [];
      case "client":
        return availablePermissions.client_permissions || [];
      default:
        return [];
    }
  };
  
  const scopePermissions = getScopePermissions();
  const permissionGroups = groupPermissionsByResource(scopePermissions);
  
  // Filter permissions based on search
  const filteredGroups = permissionGroups
    .map((group) => ({
      ...group,
      permissions: group.permissions.filter(
        (perm) =>
          perm.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          perm.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          perm.description?.toLowerCase().includes(searchQuery.toLowerCase())
      ),
    }))
    .filter((group) => group.permissions.length > 0);
  
  const togglePermission = (permissionName: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(permissionName)
        ? prev.filter((p) => p !== permissionName)
        : [...prev, permissionName]
    );
  };
  
  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full max-w-4xl h-full flex flex-col">
        <DrawerHeader className="px-6">
          <DrawerTitle>Create New Role</DrawerTitle>
          <DrawerDescription>
            Define a new role with specific permissions for your organization
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
          {/* Basic Information */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium">Basic Information</h3>
            
            <form.Field name="name">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="name">Role Name</Label>
                  <Input
                    id="name"
                    placeholder="e.g., admin, manager, viewer"
                    value={field.state.value}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => field.handleChange(e.target.value.toLowerCase().replace(/\s+/g, "_"))}
                    onBlur={field.handleBlur}
                  />
                  <p className="text-xs text-muted-foreground">
                    Internal identifier (lowercase, no spaces)
                  </p>
                  {field.state.meta.errors && (
                    <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                  )}
                </div>
              )}
            </form.Field>
            
            <form.Field name="display_name">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="display_name">Display Name</Label>
                  <Input
                    id="display_name"
                    placeholder="e.g., Administrator, Team Manager"
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
                    placeholder="Describe the purpose and capabilities of this role"
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
          
          <Separator />
          
          {/* Scope Selection */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium">Role Scope</h3>
            
            <form.Field name="scope">
              {(field) => (
                <RadioGroup
                  value={field.state.value}
                  onValueChange={(value) => {
                    field.handleChange(value);
                    setSelectedPermissions([]); // Reset permissions when scope changes
                  }}
                >
                  <div className="grid grid-cols-3 gap-3">
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
                        Cross-client operations
                      </span>
                    </label>
                    
                    <label
                      htmlFor="scope-client"
                      className={cn(
                        "relative flex flex-col items-center space-y-2 rounded-lg border-2 p-4 cursor-pointer hover:bg-accent transition-colors",
                        field.state.value === "client" ? "border-primary bg-primary/5" : "border-muted"
                      )}
                    >
                      <RadioGroupItem value="client" id="scope-client" className="sr-only" />
                      <Building2 className={cn(
                        "h-6 w-6",
                        field.state.value === "client" ? "text-primary" : "text-muted-foreground"
                      )} />
                      <span className="text-sm font-medium">Client</span>
                      <span className="text-xs text-center text-muted-foreground">
                        Organization-specific
                      </span>
                    </label>
                  </div>
                </RadioGroup>
              )}
            </form.Field>
            
            {form.state.values.scope === "system" && (
              <form.Field name="is_assignable_by_main_client">
                {(field) => (
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="assignable"
                      checked={field.state.value}
                      onCheckedChange={(checked) => field.handleChange(!!checked)}
                    />
                    <Label htmlFor="assignable" className="text-sm font-normal cursor-pointer">
                      Allow client administrators to assign this role
                    </Label>
                  </div>
                )}
              </form.Field>
            )}
          </div>
          
          <Separator />
          
          {/* Permission Selection */}
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium">Permissions</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Select permissions for this role. Higher-level permissions automatically include lower ones.
              </p>
            </div>
            
            {selectedPermissions.length > 0 && (
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  <strong>{selectedPermissions.length}</strong> permissions selected
                  {inheritedPermissions.size > 0 && (
                    <span className="text-muted-foreground">
                      {" "}(+{inheritedPermissions.size} inherited)
                    </span>
                  )}
                </AlertDescription>
              </Alert>
            )}
            
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
              <Input
                placeholder="Search permissions..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            
            <ScrollArea className="h-[300px] border rounded-md p-4">
              {permissionsLoading ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : filteredGroups.length === 0 ? (
                <div className="text-center text-muted-foreground py-8">
                  {searchQuery ? "No permissions found matching your search" : "No permissions available for this scope"}
                </div>
              ) : (
                <div className="space-y-6">
                  {filteredGroups.map((group) => (
                    <div key={group.resource} className="space-y-3">
                      <h4 className="text-sm font-medium capitalize">{group.resource} Management</h4>
                      <div className="space-y-2">
                        {group.permissions.map((permission) => {
                          const isSelected = selectedPermissions.includes(permission.name);
                          const isInherited = inheritedPermissions.has(permission.name);
                          const isDisabled = isInherited && !isSelected;
                          
                          return (
                            <div
                              key={permission.id}
                              className={cn(
                                "flex items-start space-x-3 p-3 rounded-lg border transition-colors",
                                isSelected && "bg-primary/5 border-primary",
                                isInherited && !isSelected && "bg-muted/50 opacity-75",
                                !isSelected && !isInherited && "hover:bg-muted/50"
                              )}
                            >
                              <Checkbox
                                id={permission.id}
                                checked={isSelected || isInherited}
                                disabled={isDisabled}
                                onCheckedChange={() => togglePermission(permission.name)}
                              />
                              <div className="flex-1 space-y-1">
                                <Label
                                  htmlFor={permission.id}
                                  className={cn(
                                    "text-sm font-medium cursor-pointer",
                                    isDisabled && "cursor-not-allowed"
                                  )}
                                >
                                  {permission.display_name}
                                  {isInherited && !isSelected && (
                                    <Badge variant="secondary" className="ml-2 text-xs">
                                      Inherited
                                    </Badge>
                                  )}
                                </Label>
                                <p className="text-xs text-muted-foreground">
                                  {permission.description}
                                </p>
                                <code className="text-xs bg-muted px-1 py-0.5 rounded">
                                  {permission.name}
                                </code>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </div>
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
                disabled={!canSubmit || createMutation.isPending}
                onClick={form.handleSubmit}
              >
                {createMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create Role"
                )}
              </Button>
            )}
          </form.Subscribe>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}