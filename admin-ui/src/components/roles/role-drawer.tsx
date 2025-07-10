import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Shield,
  Building2,
  Users,
  Key,
  Settings,
  Globe,
  Lock,
  AlertCircle,
  Info,
  Check,
  X,
  ChevronRight,
  Sparkles
} from "lucide-react";

interface RoleDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  role?: any;
  entityId?: string;
}

// Available permissions grouped by category
const PERMISSION_GROUPS = {
  "Entity Management": {
    icon: Building2,
    color: "text-blue-600 dark:text-blue-400",
    permissions: [
      { value: "entity:read", label: "View Entities", description: "View entity details and hierarchy" },
      { value: "entity:create", label: "Create Entities", description: "Create new entities" },
      { value: "entity:manage", label: "Manage Entities", description: "Edit and configure entities" },
      { value: "entity:delete", label: "Delete Entities", description: "Remove entities from the system" },
    ]
  },
  "User Management": {
    icon: Users,
    color: "text-green-600 dark:text-green-400",
    permissions: [
      { value: "user:read", label: "View Users", description: "View user profiles and details" },
      { value: "user:create", label: "Create Users", description: "Create new user accounts" },
      { value: "user:manage", label: "Manage Users", description: "Edit user profiles and settings" },
      { value: "user:delete", label: "Delete Users", description: "Remove users from the system" },
    ]
  },
  "Role & Permissions": {
    icon: Shield,
    color: "text-purple-600 dark:text-purple-400",
    permissions: [
      { value: "role:read", label: "View Roles", description: "View role configurations" },
      { value: "role:create", label: "Create Roles", description: "Create new roles" },
      { value: "role:manage", label: "Manage Roles", description: "Edit role permissions" },
      { value: "role:delete", label: "Delete Roles", description: "Remove roles from the system" },
    ]
  },
  "Membership": {
    icon: Key,
    color: "text-orange-600 dark:text-orange-400",
    permissions: [
      { value: "member:read", label: "View Members", description: "View entity memberships" },
      { value: "member:manage", label: "Manage Members", description: "Add/remove entity members" },
    ]
  },
  "System Administration": {
    icon: Settings,
    color: "text-red-600 dark:text-red-400",
    permissions: [
      { value: "system:read", label: "View System Settings", description: "View system configuration" },
      { value: "system:manage", label: "Manage System", description: "Configure system settings" },
      { value: "platform:manage", label: "Platform Admin", description: "Full platform administration" },
    ]
  }
};

// Entity types where roles can be assigned
const ASSIGNABLE_ENTITY_TYPES = [
  { value: "platform", label: "Platform", icon: Globe },
  { value: "organization", label: "Organization", icon: Building2 },
  { value: "division", label: "Division", icon: Building2 },
  { value: "branch", label: "Branch", icon: Building2 },
  { value: "team", label: "Team", icon: Users },
];

export function RoleDrawer({
  open,
  onOpenChange,
  mode,
  role,
  entityId
}: RoleDrawerProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    display_name: "",
    description: "",
    permissions: [] as string[],
    assignable_at_types: [] as string[],
    is_global: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  
  // Initialize form data when role changes
  useEffect(() => {
    if (role) {
      setFormData({
        name: role.name || "",
        display_name: role.display_name || "",
        description: role.description || "",
        permissions: role.permissions || [],
        assignable_at_types: role.assignable_at_types || [],
        is_global: role.is_global || false,
      });
    } else {
      // Reset for new role
      setFormData({
        name: "",
        display_name: "",
        description: "",
        permissions: [],
        assignable_at_types: ["organization", "team"], // Default assignable types
        is_global: false,
      });
    }
    setErrors({});
  }, [role, open]);
  
  // Create/Update mutation
  const mutation = useMutation({
    mutationFn: async (data: any) => {
      const url = mode === "create" ? "/v1/roles/" : `/v1/roles/${role?.id}`;
      const method = mode === "create" ? "POST" : "PUT";
      
      const body = {
        ...data,
        entity_id: entityId, // Associate with current entity context
      };
      
      const response = await authenticatedFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `Failed to ${mode} role`);
      }
      
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast.success(`Role ${mode === "create" ? "created" : "updated"} successfully`);
      onOpenChange(false);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  const handleSubmit = () => {
    // Validate
    const newErrors: Record<string, string> = {};
    
    if (!formData.display_name.trim()) {
      newErrors.display_name = "Display name is required";
    }
    
    if (mode === "create" && !formData.name.trim()) {
      newErrors.name = "System name is required";
    }
    
    if (formData.permissions.length === 0) {
      newErrors.permissions = "At least one permission is required";
    }
    
    if (formData.assignable_at_types.length === 0) {
      newErrors.assignable_at_types = "Select at least one entity type";
    }
    
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    
    // Submit
    mutation.mutate(formData);
  };
  
  const togglePermission = (permission: string) => {
    setFormData(prev => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter(p => p !== permission)
        : [...prev.permissions, permission]
    }));
    if (errors.permissions) {
      setErrors(prev => ({ ...prev, permissions: "" }));
    }
  };
  
  const toggleAssignableType = (type: string) => {
    setFormData(prev => ({
      ...prev,
      assignable_at_types: prev.assignable_at_types.includes(type)
        ? prev.assignable_at_types.filter(t => t !== type)
        : [...prev.assignable_at_types, type]
    }));
    if (errors.assignable_at_types) {
      setErrors(prev => ({ ...prev, assignable_at_types: "" }));
    }
  };
  
  // Quick templates
  const applyTemplate = (template: string) => {
    switch (template) {
      case "viewer":
        setFormData(prev => ({
          ...prev,
          permissions: ["entity:read", "user:read", "role:read", "member:read"]
        }));
        break;
      case "editor":
        setFormData(prev => ({
          ...prev,
          permissions: [
            "entity:read", "entity:create", "entity:manage",
            "user:read", "user:create", "user:manage",
            "role:read", "member:read", "member:manage"
          ]
        }));
        break;
      case "admin":
        setFormData(prev => ({
          ...prev,
          permissions: Object.values(PERMISSION_GROUPS)
            .flatMap(group => group.permissions.map(p => p.value))
            .filter(p => !p.includes("delete") && !p.includes("platform"))
        }));
        break;
    }
  };
  
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            {mode === "create" ? "Create New Role" : "Edit Role"}
          </SheetTitle>
          <SheetDescription>
            {mode === "create" 
              ? "Define a new role with specific permissions and access levels"
              : "Update role configuration and permissions"
            }
          </SheetDescription>
        </SheetHeader>
        
        <ScrollArea className="h-[calc(100vh-200px)] mt-6 pr-4">
          <div className="space-y-6">
            {/* Basic Information */}
            <div className="space-y-4">
              <h3 className="text-sm font-medium flex items-center gap-2">
                <Info className="h-4 w-4" />
                Basic Information
              </h3>
              
              <div className="space-y-2">
                <Label htmlFor="display_name">
                  Display Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="display_name"
                  value={formData.display_name}
                  onChange={(e) => {
                    setFormData(prev => ({ ...prev, display_name: e.target.value }));
                    if (errors.display_name) setErrors(prev => ({ ...prev, display_name: "" }));
                  }}
                  placeholder="e.g., Project Manager"
                  className={errors.display_name ? "border-destructive" : ""}
                />
                {errors.display_name && (
                  <p className="text-sm text-destructive">{errors.display_name}</p>
                )}
              </div>
              
              {mode === "create" && (
                <div className="space-y-2">
                  <Label htmlFor="name">
                    System Name <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => {
                      const value = e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_');
                      setFormData(prev => ({ ...prev, name: value }));
                      if (errors.name) setErrors(prev => ({ ...prev, name: "" }));
                    }}
                    placeholder="e.g., project_manager"
                    className={cn("font-mono", errors.name ? "border-destructive" : "")}
                  />
                  <p className="text-xs text-muted-foreground">
                    Lowercase letters, numbers, and underscores only
                  </p>
                  {errors.name && (
                    <p className="text-sm text-destructive">{errors.name}</p>
                  )}
                </div>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Describe the purpose and responsibilities of this role"
                  rows={3}
                />
              </div>
              
              <div className="flex items-center justify-between rounded-lg border p-3">
                <div className="space-y-0.5">
                  <Label htmlFor="is_global" className="text-base cursor-pointer">
                    Global Role
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Make this role available across all entities
                  </p>
                </div>
                <Switch
                  id="is_global"
                  checked={formData.is_global}
                  onCheckedChange={(checked) => 
                    setFormData(prev => ({ ...prev, is_global: checked }))
                  }
                />
              </div>
            </div>
            
            <Separator />
            
            {/* Quick Templates */}
            <div className="space-y-4">
              <h3 className="text-sm font-medium flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Quick Templates
              </h3>
              <div className="grid grid-cols-3 gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => applyTemplate("viewer")}
                  className="justify-start"
                >
                  <Shield className="mr-2 h-4 w-4" />
                  Viewer
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => applyTemplate("editor")}
                  className="justify-start"
                >
                  <Shield className="mr-2 h-4 w-4" />
                  Editor
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => applyTemplate("admin")}
                  className="justify-start"
                >
                  <Shield className="mr-2 h-4 w-4" />
                  Admin
                </Button>
              </div>
            </div>
            
            <Separator />
            
            {/* Permissions */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium flex items-center gap-2">
                  <Key className="h-4 w-4" />
                  Permissions <span className="text-destructive">*</span>
                </h3>
                <Badge variant="outline">
                  {formData.permissions.length} selected
                </Badge>
              </div>
              
              {errors.permissions && (
                <p className="text-sm text-destructive flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" />
                  {errors.permissions}
                </p>
              )}
              
              <Accordion type="single" collapsible className="w-full">
                {Object.entries(PERMISSION_GROUPS).map(([groupName, group]) => {
                  const Icon = group.icon;
                  const selectedCount = group.permissions.filter(p => 
                    formData.permissions.includes(p.value)
                  ).length;
                  
                  return (
                    <AccordionItem key={groupName} value={groupName}>
                      <AccordionTrigger className="hover:no-underline">
                        <div className="flex items-center justify-between w-full mr-2">
                          <div className="flex items-center gap-2">
                            <Icon className={cn("h-4 w-4", group.color)} />
                            <span>{groupName}</span>
                          </div>
                          {selectedCount > 0 && (
                            <Badge variant="secondary" className="text-xs">
                              {selectedCount}/{group.permissions.length}
                            </Badge>
                          )}
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="space-y-2 pt-2">
                          {group.permissions.map((permission) => (
                            <div
                              key={permission.value}
                              className={cn(
                                "flex items-start space-x-3 p-3 rounded-lg transition-colors",
                                formData.permissions.includes(permission.value)
                                  ? "bg-primary/5 border border-primary/20"
                                  : "hover:bg-muted/50"
                              )}
                            >
                              <Checkbox
                                id={permission.value}
                                checked={formData.permissions.includes(permission.value)}
                                onCheckedChange={() => togglePermission(permission.value)}
                                className="mt-0.5"
                              />
                              <div className="flex-1 space-y-1">
                                <Label
                                  htmlFor={permission.value}
                                  className="text-sm font-medium cursor-pointer"
                                >
                                  {permission.label}
                                </Label>
                                <p className="text-xs text-muted-foreground">
                                  {permission.description}
                                </p>
                                <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                                  {permission.value}
                                </code>
                              </div>
                            </div>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  );
                })}
              </Accordion>
            </div>
            
            <Separator />
            
            {/* Assignable Entity Types */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  Can be assigned at <span className="text-destructive">*</span>
                </h3>
                <Badge variant="outline">
                  {formData.assignable_at_types.length} selected
                </Badge>
              </div>
              
              <p className="text-sm text-muted-foreground">
                Select the entity types where this role can be assigned to users
              </p>
              
              {errors.assignable_at_types && (
                <p className="text-sm text-destructive flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" />
                  {errors.assignable_at_types}
                </p>
              )}
              
              <div className="grid grid-cols-2 gap-3">
                {ASSIGNABLE_ENTITY_TYPES.map((type) => {
                  const Icon = type.icon;
                  const isSelected = formData.assignable_at_types.includes(type.value);
                  
                  return (
                    <div
                      key={type.value}
                      onClick={() => toggleAssignableType(type.value)}
                      className={cn(
                        "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                        isSelected 
                          ? "bg-primary/5 border-primary/50" 
                          : "hover:bg-muted/50"
                      )}
                    >
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => toggleAssignableType(type.value)}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">{type.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </ScrollArea>
        
        <SheetFooter className="mt-6">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={mutation.isPending}
          >
            {mutation.isPending 
              ? "Saving..." 
              : mode === "create" ? "Create Role" : "Update Role"
            }
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}