import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AppSidebar } from "@/components/app-sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  BreadcrumbLink,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Plus, Shield, Globe, Building2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { CreateRoleDrawer } from "@/components/roles/create-role-drawer";
import { requireAuth } from "@/lib/route-guards";

export const Route = createFileRoute("/roles/")({
  beforeLoad: requireAuth,
  component: Roles,
});

interface Permission {
  id: string;
  name: string;
  display_name: string;
  description: string;
}

interface Role {
  _id: string;
  name: string;
  display_name: string;
  description: string;
  permissions: Permission[];
  scope: "system" | "platform" | "client";
  scope_id: string | null;
  is_assignable_by_main_client: boolean;
  created_at: string;
  updated_at: string;
}

interface RolesResponse {
  system_roles: Role[];
  platform_roles: Role[];
  client_roles: Role[];
}

async function fetchRoles(): Promise<RolesResponse> {
  const response = await authenticatedFetch("/v1/roles/available");
  return response.json();
}

function RoleCard({ role }: { role: Role }) {
  const getScopeIcon = (scope: string) => {
    switch (scope) {
      case "system":
        return <Shield className="h-4 w-4" />;
      case "platform":
        return <Globe className="h-4 w-4" />;
      case "client":
        return <Building2 className="h-4 w-4" />;
      default:
        return <Shield className="h-4 w-4" />;
    }
  };

  const getScopeBadgeVariant = (scope: string) => {
    switch (scope) {
      case "system":
        return "destructive";
      case "platform":
        return "secondary";
      case "client":
        return "default";
      default:
        return "default";
    }
  };

  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getScopeIcon(role.scope)}
            <CardTitle className="text-lg">{role.display_name}</CardTitle>
          </div>
          <Badge variant={getScopeBadgeVariant(role.scope)}>
            {role.scope}
          </Badge>
        </div>
        <CardDescription className="mt-2">
          {role.description || "No description available"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div>
            <p className="text-sm font-medium mb-1">Role Name</p>
            <code className="text-xs bg-muted px-2 py-1 rounded">
              {role.name}
            </code>
          </div>
          <div>
            <p className="text-sm font-medium mb-1">Permissions ({role.permissions.length})</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {role.permissions.slice(0, 3).map((permission) => (
                <Badge key={permission.id} variant="outline" className="text-xs">
                  {permission.name}
                </Badge>
              ))}
              {role.permissions.length > 3 && (
                <Badge variant="outline" className="text-xs">
                  +{role.permissions.length - 3} more
                </Badge>
              )}
            </div>
          </div>
          {role.is_assignable_by_main_client && (
            <Badge variant="secondary" className="text-xs">
              Assignable by client admins
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function RolesList({ roles, title, description }: { roles: Role[]; title: string; description: string }) {
  if (roles.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <p>No {title.toLowerCase()} found</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {roles.map((role) => (
          <RoleCard key={role._id} role={role} />
        ))}
      </div>
    </div>
  );
}

function RolesContent() {
  const { data: roles, isLoading, error } = useQuery({
    queryKey: ["roles"],
    queryFn: fetchRoles,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-3 w-full mt-2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">Error loading roles: {error.message}</p>
        </CardContent>
      </Card>
    );
  }

  const hasSystemRoles = roles?.system_roles && roles.system_roles.length > 0;
  const hasPlatformRoles = roles?.platform_roles && roles.platform_roles.length > 0;
  const hasClientRoles = roles?.client_roles && roles.client_roles.length > 0;

  // If user only has access to one scope, don't show tabs
  const scopeCount = [hasSystemRoles, hasPlatformRoles, hasClientRoles].filter(Boolean).length;

  if (scopeCount === 1) {
    if (hasSystemRoles) {
      return <RolesList roles={roles.system_roles} title="System Roles" description="Global roles that apply across the entire system" />;
    }
    if (hasPlatformRoles) {
      return <RolesList roles={roles.platform_roles} title="Platform Roles" description="Roles for managing platform-level operations" />;
    }
    if (hasClientRoles) {
      return <RolesList roles={roles.client_roles} title="Client Roles" description="Roles specific to your organization" />;
    }
  }

  return (
    <Tabs defaultValue={hasSystemRoles ? "system" : hasPlatformRoles ? "platform" : "client"} className="space-y-6">
      <TabsList>
        {hasSystemRoles && <TabsTrigger value="system">System Roles</TabsTrigger>}
        {hasPlatformRoles && <TabsTrigger value="platform">Platform Roles</TabsTrigger>}
        {hasClientRoles && <TabsTrigger value="client">Client Roles</TabsTrigger>}
      </TabsList>

      {hasSystemRoles && (
        <TabsContent value="system" className="space-y-6">
          <RolesList 
            roles={roles.system_roles} 
            title="System Roles" 
            description="Global roles that apply across the entire system"
          />
        </TabsContent>
      )}

      {hasPlatformRoles && (
        <TabsContent value="platform" className="space-y-6">
          <RolesList 
            roles={roles.platform_roles} 
            title="Platform Roles" 
            description="Roles for managing platform-level operations"
          />
        </TabsContent>
      )}

      {hasClientRoles && (
        <TabsContent value="client" className="space-y-6">
          <RolesList 
            roles={roles.client_roles} 
            title="Client Roles" 
            description="Roles specific to your organization"
          />
        </TabsContent>
      )}
    </Tabs>
  );
}

function Roles() {
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbLink href="/dashboard">Dashboard</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>Roles</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="mx-auto w-full max-w-7xl">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Roles Management</h1>
                <p className="text-muted-foreground">
                  Manage roles and their permissions across different scopes
                </p>
              </div>
              <Button onClick={() => setCreateDrawerOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Role
              </Button>
            </div>
            
            <RolesContent />
          </div>
        </div>
      </SidebarInset>
      
      <CreateRoleDrawer 
        open={createDrawerOpen} 
        onOpenChange={setCreateDrawerOpen} 
      />
    </SidebarProvider>
  );
}