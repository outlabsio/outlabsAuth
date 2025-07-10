import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
import {
  Shield,
  Eye,
  Edit,
  Users,
  Crown,
  Briefcase,
  Rocket,
  BookOpen,
  Copy,
  AlertCircle,
  Building2,
  Key,
  Settings,
  FileText,
  Sparkles,
  CheckCircle
} from "lucide-react";
import { cn } from "@/lib/utils";

interface RoleTemplate {
  id: string;
  name: string;
  display_name: string;
  description: string;
  icon: any;
  color: string;
  permissions: string[];
  suitable_for: string[];
  is_premium?: boolean;
}

// Predefined role templates
const ROLE_TEMPLATES: RoleTemplate[] = [
  {
    id: "viewer",
    name: "viewer",
    display_name: "Viewer",
    description: "Read-only access to view information across the system",
    icon: Eye,
    color: "text-blue-600 dark:text-blue-400",
    permissions: ["entity:read", "user:read", "role:read", "member:read"],
    suitable_for: ["organization", "division", "team"],
  },
  {
    id: "editor",
    name: "editor",
    display_name: "Editor",
    description: "Create and edit content, manage basic operations",
    icon: Edit,
    color: "text-green-600 dark:text-green-400",
    permissions: [
      "entity:read", "entity:create", "entity:manage",
      "user:read", "user:create", "user:manage",
      "role:read", "member:read", "member:manage"
    ],
    suitable_for: ["organization", "division", "team"],
  },
  {
    id: "admin",
    name: "admin",
    display_name: "Administrator",
    description: "Full administrative access within the assigned scope",
    icon: Crown,
    color: "text-purple-600 dark:text-purple-400",
    permissions: [
      "entity:read", "entity:create", "entity:manage", "entity:delete",
      "user:read", "user:create", "user:manage", "user:delete",
      "role:read", "role:create", "role:manage",
      "member:read", "member:manage"
    ],
    suitable_for: ["organization", "division"],
  },
  {
    id: "member_manager",
    name: "member_manager",
    display_name: "Member Manager",
    description: "Manage team members and their access",
    icon: Users,
    color: "text-orange-600 dark:text-orange-400",
    permissions: [
      "entity:read", "user:read", "user:create", "user:manage",
      "role:read", "member:read", "member:manage"
    ],
    suitable_for: ["organization", "division", "team"],
  },
  {
    id: "project_lead",
    name: "project_lead",
    display_name: "Project Lead",
    description: "Lead projects with entity and member management",
    icon: Briefcase,
    color: "text-indigo-600 dark:text-indigo-400",
    permissions: [
      "entity:read", "entity:create", "entity:manage",
      "user:read", "role:read", "member:read", "member:manage"
    ],
    suitable_for: ["division", "team"],
  },
  {
    id: "developer",
    name: "developer",
    display_name: "Developer",
    description: "Technical role with system configuration access",
    icon: Rocket,
    color: "text-cyan-600 dark:text-cyan-400",
    permissions: [
      "entity:read", "entity:manage",
      "user:read", "role:read", "member:read",
      "system:read"
    ],
    suitable_for: ["team"],
    is_premium: true,
  },
  {
    id: "auditor",
    name: "auditor",
    display_name: "Auditor",
    description: "Read-only access for compliance and auditing",
    icon: FileText,
    color: "text-gray-600 dark:text-gray-400",
    permissions: [
      "entity:read", "user:read", "role:read", "member:read", "system:read"
    ],
    suitable_for: ["platform", "organization"],
    is_premium: true,
  },
  {
    id: "platform_admin",
    name: "platform_admin",
    display_name: "Platform Administrator",
    description: "Complete platform control and system management",
    icon: Shield,
    color: "text-red-600 dark:text-red-400",
    permissions: [
      "entity:read", "entity:create", "entity:manage", "entity:delete",
      "user:read", "user:create", "user:manage", "user:delete",
      "role:read", "role:create", "role:manage", "role:delete",
      "member:read", "member:manage",
      "system:read", "system:manage", "platform:manage"
    ],
    suitable_for: ["platform"],
    is_premium: true,
  },
];

// Permission category icons
const PERMISSION_ICONS: Record<string, any> = {
  entity: Building2,
  user: Users,
  role: Shield,
  member: Key,
  system: Settings,
  platform: Shield,
};

function PermissionBadge({ permission }: { permission: string }) {
  const [resource, action] = permission.split(":");
  const Icon = PERMISSION_ICONS[resource] || Shield;
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant="secondary" className="gap-1 text-xs">
            <Icon className="h-3 w-3" />
            {permission}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="font-medium capitalize">{resource} - {action}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function RoleTemplateCard({ 
  template, 
  onUseTemplate 
}: { 
  template: RoleTemplate;
  onUseTemplate: (template: RoleTemplate) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const Icon = template.icon;
  const visiblePermissions = showAll ? template.permissions : template.permissions.slice(0, 4);
  
  return (
    <Card className="group hover:shadow-lg transition-all duration-200 relative overflow-hidden">
      {template.is_premium && (
        <div className="absolute top-2 right-2">
          <Badge variant="default" className="gap-1 bg-gradient-to-r from-purple-600 to-pink-600">
            <Sparkles className="h-3 w-3" />
            Premium
          </Badge>
        </div>
      )}
      
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className={cn("p-3 rounded-lg bg-muted", template.color)}>
            <Icon className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <CardTitle className="text-lg">{template.display_name}</CardTitle>
            <CardDescription className="mt-1">
              {template.description}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        <div className="space-y-4">
          {/* Suitable For */}
          <div>
            <p className="text-sm font-medium mb-2">Best suited for:</p>
            <div className="flex flex-wrap gap-1">
              {template.suitable_for.map((type) => (
                <Badge key={type} variant="outline" className="text-xs capitalize">
                  {type}
                </Badge>
              ))}
            </div>
          </div>
          
          {/* Permissions */}
          <div>
            <p className="text-sm font-medium mb-2">Permissions included:</p>
            <div className="flex flex-wrap gap-1">
              {visiblePermissions.map((permission) => (
                <PermissionBadge key={permission} permission={permission} />
              ))}
              {template.permissions.length > 4 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => setShowAll(!showAll)}
                >
                  {showAll ? "Show less" : `+${template.permissions.length - 4} more`}
                </Button>
              )}
            </div>
          </div>
          
          {/* Actions */}
          <div className="pt-2">
            <Button 
              className="w-full" 
              variant="outline"
              onClick={() => onUseTemplate(template)}
            >
              <Copy className="mr-2 h-4 w-4" />
              Use This Template
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function RoleTemplates() {
  const [selectedTemplate, setSelectedTemplate] = useState<RoleTemplate | null>(null);
  const [roleName, setRoleName] = useState("");
  const [creating, setCreating] = useState(false);
  const queryClient = useQueryClient();
  
  const createRoleMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await authenticatedFetch("/v1/roles/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to create role");
      }
      
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast.success("Role created successfully from template");
      setSelectedTemplate(null);
      setRoleName("");
      setCreating(false);
    },
    onError: (error: Error) => {
      toast.error(error.message);
      setCreating(false);
    },
  });
  
  const handleUseTemplate = (template: RoleTemplate) => {
    setSelectedTemplate(template);
    setRoleName(template.display_name);
  };
  
  const handleCreateFromTemplate = () => {
    if (!selectedTemplate || !roleName.trim()) return;
    
    setCreating(true);
    
    const systemName = roleName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_|_$/g, '');
    
    createRoleMutation.mutate({
      name: systemName,
      display_name: roleName,
      description: `Created from ${selectedTemplate.display_name} template`,
      permissions: selectedTemplate.permissions,
      assignable_at_types: selectedTemplate.suitable_for,
      is_global: selectedTemplate.suitable_for.includes("platform"),
    });
  };
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <h3 className="text-lg font-semibold flex items-center justify-center gap-2">
          <BookOpen className="h-5 w-5" />
          Role Templates
        </h3>
        <p className="text-muted-foreground max-w-2xl mx-auto">
          Start with a pre-configured role template and customize it to fit your needs. 
          These templates follow security best practices and common organizational patterns.
        </p>
      </div>
      
      {/* Template Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {ROLE_TEMPLATES.map((template) => (
          <RoleTemplateCard
            key={template.id}
            template={template}
            onUseTemplate={handleUseTemplate}
          />
        ))}
      </div>
      
      {/* Create from Template Dialog */}
      <Dialog open={!!selectedTemplate} onOpenChange={() => setSelectedTemplate(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Role from Template</DialogTitle>
            <DialogDescription>
              Customize the role name before creating it from the {selectedTemplate?.display_name} template.
            </DialogDescription>
          </DialogHeader>
          
          {selectedTemplate && (
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-muted">
                <selectedTemplate.icon className={cn("h-5 w-5", selectedTemplate.color)} />
                <div>
                  <p className="font-medium">{selectedTemplate.display_name}</p>
                  <p className="text-sm text-muted-foreground">
                    {selectedTemplate.permissions.length} permissions
                  </p>
                </div>
              </div>
              
              <div className="space-y-2">
                <label htmlFor="role-name" className="text-sm font-medium">
                  Role Name
                </label>
                <Input
                  id="role-name"
                  value={roleName}
                  onChange={(e) => setRoleName(e.target.value)}
                  placeholder="Enter role name"
                />
                <p className="text-xs text-muted-foreground">
                  This will be the display name for your new role
                </p>
              </div>
              
              <div className="rounded-lg border p-3 bg-muted/50">
                <div className="flex items-center gap-2 text-sm">
                  <AlertCircle className="h-4 w-4 text-amber-600" />
                  <p>
                    You can customize permissions and settings after creating the role
                  </p>
                </div>
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setSelectedTemplate(null)}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button 
              onClick={handleCreateFromTemplate}
              disabled={!roleName.trim() || creating}
            >
              {creating ? "Creating..." : "Create Role"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}