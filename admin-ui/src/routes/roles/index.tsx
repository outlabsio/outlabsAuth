import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppSidebar } from "@/components/app-sidebar";
import { PageHeader } from "@/components/layout/page-header";
import { useContextStore } from "@/stores/context-store";
import { authenticatedFetch } from "@/lib/auth";
import { requireAuth } from "@/lib/route-guards";
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RoleDrawer } from "@/components/roles/role-drawer";
import { RoleTemplates } from "@/components/roles/role-templates";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Shield,
  Plus,
  Search,
  Building2,
  Globe,
  Users,
  Key,
  Sparkles,
  Lock,
  Unlock,
  BookOpen,
  Award,
  Settings,
  Edit,
  Copy,
  Trash2,
  AlertCircle,
  CheckCircle,
  Info,
  TrendingUp,
  MoreVertical
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/roles/")({
  beforeLoad: requireAuth,
  component: RolesPage,
});

interface Role {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  permissions: string[];
  entity_id?: string;
  entity_name?: string;
  assignable_at_types: string[];
  is_system_role: boolean;
  is_global: boolean;
  created_at: string;
  updated_at?: string;
}

interface RoleUsageStats {
  role_id: string;
  role_name: string;
  active_assignments: number;
  total_assignments: number;
  entities_used_in: number;
  last_assigned?: string;
}

async function fetchRoles(entityId?: string, isGlobal?: boolean) {
  const params = new URLSearchParams();
  if (entityId) params.append("entity_id", entityId);
  if (isGlobal !== undefined) params.append("is_global", String(isGlobal));
  
  const response = await authenticatedFetch(`/v1/roles/?${params}`);
  const data = await response.json();
  return data.items || [];
}

async function fetchRoleUsage(roleId: string): Promise<RoleUsageStats> {
  const response = await authenticatedFetch(`/v1/roles/${roleId}/usage`);
  const data = await response.json();
  return data.stats[0];
}

// Permission categories for better organization
const PERMISSION_CATEGORIES = {
  entity: {
    label: "Entity Management",
    icon: Building2,
    permissions: ["entity:read", "entity:create", "entity:manage", "entity:delete"],
    color: "text-blue-600 dark:text-blue-400"
  },
  user: {
    label: "User Management",
    icon: Users,
    permissions: ["user:read", "user:create", "user:manage", "user:delete"],
    color: "text-green-600 dark:text-green-400"
  },
  role: {
    label: "Role Management",
    icon: Shield,
    permissions: ["role:read", "role:create", "role:manage", "role:delete"],
    color: "text-purple-600 dark:text-purple-400"
  },
  member: {
    label: "Membership",
    icon: Key,
    permissions: ["member:read", "member:manage"],
    color: "text-orange-600 dark:text-orange-400"
  },
  system: {
    label: "System",
    icon: Settings,
    permissions: ["system:read", "system:manage", "platform:manage"],
    color: "text-red-600 dark:text-red-400"
  }
};

function getPermissionCategory(permission: string) {
  const [resource] = permission.split(":");
  return PERMISSION_CATEGORIES[resource as keyof typeof PERMISSION_CATEGORIES] || null;
}

function RoleCard({ 
  role, 
  onEdit, 
  onClone,
  onDelete,
  showUsage = true 
}: { 
  role: Role;
  onEdit: () => void;
  onClone: () => void;
  onDelete: () => void;
  showUsage?: boolean;
}) {
  const [showAllPermissions, setShowAllPermissions] = useState(false);
  const queryClient = useQueryClient();
  
  // Fetch usage stats
  const { data: usage } = useQuery({
    queryKey: ["role-usage", role.id],
    queryFn: () => fetchRoleUsage(role.id),
    enabled: showUsage && !role.is_system_role,
    staleTime: 60000, // Cache for 1 minute
  });
  
  // Group permissions by category
  const permissionsByCategory = role.permissions.reduce((acc, permission) => {
    const category = getPermissionCategory(permission);
    if (category) {
      const key = permission.split(":")[0];
      if (!acc[key]) acc[key] = [];
      acc[key].push(permission);
    }
    return acc;
  }, {} as Record<string, string[]>);
  
  const visiblePermissions = showAllPermissions ? role.permissions : role.permissions.slice(0, 3);
  
  return (
    <Card className="group hover:shadow-lg transition-all duration-200">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-1 flex-1">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-lg">{role.display_name}</CardTitle>
              {role.is_system_role && (
                <Badge variant="secondary" className="gap-1">
                  <Lock className="h-3 w-3" />
                  System
                </Badge>
              )}
              {role.is_global && (
                <Badge variant="outline" className="gap-1">
                  <Globe className="h-3 w-3" />
                  Global
                </Badge>
              )}
            </div>
            {role.description && (
              <CardDescription className="mt-1">
                {role.description}
              </CardDescription>
            )}
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                size="icon" 
                className="opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={onEdit} disabled={role.is_system_role}>
                <Edit className="mr-2 h-4 w-4" />
                Edit Role
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onClone}>
                <Copy className="mr-2 h-4 w-4" />
                Clone Role
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem 
                onClick={onDelete} 
                disabled={role.is_system_role || (usage && usage.active_assignments > 0)}
                className="text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Role
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        {/* Scope Information */}
        <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">
          {role.entity_name && (
            <div className="flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" />
              <span>{role.entity_name}</span>
            </div>
          )}
          <div className="flex items-center gap-1">
            <Award className="h-3.5 w-3.5" />
            <span>Assignable at: {role.assignable_at_types.join(", ")}</span>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        {/* Permissions Display */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium">Permissions</h4>
            <Badge variant="outline" className="text-xs">
              {role.permissions.length} total
            </Badge>
          </div>
          
          {/* Visual Permission Categories */}
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(permissionsByCategory).map(([key, perms]) => {
              const category = PERMISSION_CATEGORIES[key as keyof typeof PERMISSION_CATEGORIES];
              if (!category) return null;
              const Icon = category.icon;
              
              return (
                <TooltipProvider key={key}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className={cn(
                        "flex items-center gap-2 p-2 rounded-lg bg-muted/50",
                        "hover:bg-muted transition-colors cursor-default"
                      )}>
                        <Icon className={cn("h-4 w-4", category.color)} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate">
                            {category.label}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {perms.length} permissions
                          </p>
                        </div>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-xs">
                      <p className="font-medium mb-1">{category.label}</p>
                      <div className="space-y-0.5">
                        {perms.map(perm => (
                          <div key={perm} className="text-xs">
                            • {perm}
                          </div>
                        ))}
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              );
            })}
          </div>
          
          {/* Permission List */}
          <div className="flex flex-wrap gap-1">
            {visiblePermissions.map((permission) => (
              <Badge key={permission} variant="secondary" className="text-xs">
                {permission}
              </Badge>
            ))}
            {role.permissions.length > 3 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-5 px-2 text-xs"
                onClick={() => setShowAllPermissions(!showAllPermissions)}
              >
                {showAllPermissions ? "Show less" : `+${role.permissions.length - 3} more`}
              </Button>
            )}
          </div>
        </div>
        
        {/* Usage Stats */}
        {showUsage && usage && (
          <div className="mt-4 pt-4 border-t">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-semibold text-primary">
                  {usage.active_assignments}
                </p>
                <p className="text-xs text-muted-foreground">Active Users</p>
              </div>
              <div>
                <p className="text-2xl font-semibold">
                  {usage.entities_used_in}
                </p>
                <p className="text-xs text-muted-foreground">Entities</p>
              </div>
              <div>
                <p className="text-2xl font-semibold">
                  {usage.total_assignments}
                </p>
                <p className="text-xs text-muted-foreground">Total Assigned</p>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RolesContent() {
  const { selectedOrganization, isSystemContext } = useContextStore();
  const [searchQuery, setSearchQuery] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"create" | "edit">("create");
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const queryClient = useQueryClient();
  
  // Determine context for fetching roles
  const contextEntityId = !isSystemContext() && selectedOrganization ? selectedOrganization.id : undefined;
  
  // Fetch roles
  const { data: roles, isLoading } = useQuery({
    queryKey: ["roles", contextEntityId],
    queryFn: () => fetchRoles(contextEntityId),
  });
  
  // Filter roles
  const filteredRoles = roles?.filter((role: Role) =>
    role.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    role.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    role.permissions.some(p => p.toLowerCase().includes(searchQuery.toLowerCase()))
  ) || [];
  
  // Separate roles by type
  const systemRoles = filteredRoles.filter((r: Role) => r.is_system_role);
  const globalRoles = filteredRoles.filter((r: Role) => r.is_global && !r.is_system_role);
  const customRoles = filteredRoles.filter((r: Role) => !r.is_global && !r.is_system_role);
  
  const handleCreateRole = () => {
    setDrawerMode("create");
    setSelectedRole(null);
    setDrawerOpen(true);
  };
  
  const handleEditRole = (role: Role) => {
    setDrawerMode("edit");
    setSelectedRole(role);
    setDrawerOpen(true);
  };
  
  const handleCloneRole = (role: Role) => {
    setDrawerMode("create");
    setSelectedRole({
      ...role,
      id: "",
      name: `${role.name}_copy`,
      display_name: `${role.display_name} (Copy)`,
      is_system_role: false,
    });
    setDrawerOpen(true);
  };
  
  const handleDeleteRole = async (role: Role) => {
    // TODO: Implement delete confirmation dialog
    console.log("Delete role:", role);
  };
  
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-48 mt-2" />
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <Skeleton className="h-20 w-full" />
                  <Skeleton className="h-16 w-full" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      {/* Search and Actions */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search roles by name, description, or permissions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button onClick={handleCreateRole}>
          <Plus className="mr-2 h-4 w-4" />
          Create Role
        </Button>
      </div>
      
      {/* Roles by Category */}
      {systemRoles.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">System Roles</h3>
            <Badge variant="secondary">{systemRoles.length}</Badge>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {systemRoles.map((role: Role) => (
              <RoleCard
                key={role.id}
                role={role}
                onEdit={() => handleEditRole(role)}
                onClone={() => handleCloneRole(role)}
                onDelete={() => handleDeleteRole(role)}
              />
            ))}
          </div>
        </div>
      )}
      
      {globalRoles.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">Global Roles</h3>
            <Badge variant="secondary">{globalRoles.length}</Badge>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {globalRoles.map((role: Role) => (
              <RoleCard
                key={role.id}
                role={role}
                onEdit={() => handleEditRole(role)}
                onClone={() => handleCloneRole(role)}
                onDelete={() => handleDeleteRole(role)}
              />
            ))}
          </div>
        </div>
      )}
      
      {customRoles.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">Custom Roles</h3>
            <Badge variant="secondary">{customRoles.length}</Badge>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {customRoles.map((role: Role) => (
              <RoleCard
                key={role.id}
                role={role}
                onEdit={() => handleEditRole(role)}
                onClone={() => handleCloneRole(role)}
                onDelete={() => handleDeleteRole(role)}
              />
            ))}
          </div>
        </div>
      )}
      
      {filteredRoles.length === 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-8">
              <Shield className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Roles Found</h3>
              <p className="text-muted-foreground mb-4">
                {searchQuery 
                  ? "No roles match your search criteria"
                  : "Create your first role to start managing permissions"}
              </p>
              {!searchQuery && (
                <Button onClick={handleCreateRole}>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Your First Role
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
      
      <RoleDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        mode={drawerMode}
        role={selectedRole}
        entityId={contextEntityId}
      />
    </div>
  );
}

function RolesPage() {
  const { selectedOrganization, isSystemContext } = useContextStore();
  const [activeTab, setActiveTab] = useState("roles");
  
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <PageHeader 
          breadcrumbs={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Roles" }
          ]}
        />
        
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="mx-auto w-full max-w-7xl">
            <div className="mb-6">
              <h1 className="text-2xl font-bold tracking-tight">Role Management</h1>
              <p className="text-muted-foreground">
                {!isSystemContext() && selectedOrganization ? (
                  <>
                    Managing roles for <span className="font-medium">{selectedOrganization.name}</span>
                  </>
                ) : (
                  "Create and manage roles with granular permissions"
                )}
              </p>
            </div>
            
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
              <TabsList>
                <TabsTrigger value="roles">
                  <Shield className="mr-2 h-4 w-4" />
                  All Roles
                </TabsTrigger>
                <TabsTrigger value="templates">
                  <BookOpen className="mr-2 h-4 w-4" />
                  Templates
                </TabsTrigger>
                <TabsTrigger value="insights">
                  <TrendingUp className="mr-2 h-4 w-4" />
                  Insights
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="roles" className="space-y-4">
                <RolesContent />
              </TabsContent>
              
              <TabsContent value="templates" className="space-y-4">
                <RoleTemplates />
              </TabsContent>
              
              <TabsContent value="insights" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Role Insights</CardTitle>
                    <CardDescription>
                      Analytics and usage patterns for your roles
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center py-8">
                      <TrendingUp className="h-12 w-12 text-muted-foreground mx-auto mb-2" />
                      <p className="text-muted-foreground">Role analytics coming soon</p>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}