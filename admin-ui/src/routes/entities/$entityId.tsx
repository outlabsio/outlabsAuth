import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AppSidebar } from "@/components/app-sidebar";
import { authenticatedFetch } from "@/lib/auth";
import { requireAuth } from "@/lib/route-guards";
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
import { Skeleton } from "@/components/ui/skeleton";
import { EntityMembers } from "@/components/entities/entity-members";
import { EntityDrawer } from "@/components/entities/entity-drawer";
import { 
  Entity, 
  getEntityTypeLabel,
  isStructuralEntity 
} from "@/types/entity";
import { getEntityTypeIcon } from "@/lib/entity-icons";
import { 
  Building2, 
  Edit, 
  Users, 
  Shield, 
  Settings,
  Calendar,
  ChevronRight,
  FolderTree,
  Hash,
  FileText,
  Activity
} from "lucide-react";
import { format } from "date-fns";

export const Route = createFileRoute("/entities/$entityId")({
  beforeLoad: requireAuth,
  component: EntityDetailsPage,
});

async function fetchEntity(entityId: string): Promise<Entity> {
  const response = await authenticatedFetch(`/v1/entities/${entityId}`);
  return response.json();
}

async function fetchEntityPath(entityId: string): Promise<Entity[]> {
  const response = await authenticatedFetch(`/v1/entities/${entityId}/path`);
  return response.json();
}

async function fetchChildEntities(entityId: string): Promise<Entity[]> {
  const response = await authenticatedFetch(`/v1/entities/?parent_entity_id=${entityId}&status=active`);
  const data = await response.json();
  return data.items || [];
}

function EntityDetailsPage() {
  const { entityId } = Route.useParams();
  const [drawerOpen, setDrawerOpen] = useState(false);
  
  // Fetch entity details
  const { data: entity, isLoading, error } = useQuery({
    queryKey: ["entity", entityId],
    queryFn: () => fetchEntity(entityId),
  });
  
  // Fetch entity path for breadcrumbs
  const { data: entityPath } = useQuery({
    queryKey: ["entity-path", entityId],
    queryFn: () => fetchEntityPath(entityId),
    enabled: !!entity,
  });
  
  // Fetch child entities
  const { data: childEntities } = useQuery({
    queryKey: ["entity-children", entityId],
    queryFn: () => fetchChildEntities(entityId),
    enabled: !!entity && isStructuralEntity(entity),
  });
  
  if (isLoading) {
    return (
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <div className="flex flex-1 flex-col gap-4 p-4">
            <div className="mx-auto w-full max-w-7xl">
              <Skeleton className="h-12 w-64 mb-4" />
              <div className="grid gap-4">
                <Skeleton className="h-32 w-full" />
                <Skeleton className="h-96 w-full" />
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    );
  }
  
  if (error || !entity) {
    return (
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <div className="flex flex-1 flex-col gap-4 p-4">
            <div className="mx-auto w-full max-w-7xl">
              <Card>
                <CardContent className="pt-6">
                  <p className="text-destructive">
                    {error ? "Failed to load entity details" : "Entity not found"}
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    );
  }
  
  const canManageMembers = true; // TODO: Check actual permissions
  
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
                  <BreadcrumbLink href="/entities">Entities</BreadcrumbLink>
                </BreadcrumbItem>
                {entityPath && entityPath.length > 1 && (
                  <>
                    {entityPath.slice(0, -1).map((pathEntity) => (
                      <div key={pathEntity.id} className="flex items-center gap-2">
                        <BreadcrumbSeparator />
                        <BreadcrumbItem>
                          <BreadcrumbLink href={`/entities/${pathEntity.id}`}>
                            {pathEntity.name}
                          </BreadcrumbLink>
                        </BreadcrumbItem>
                      </div>
                    ))}
                  </>
                )}
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>{entity.name}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="mx-auto w-full max-w-7xl">
            {/* Compact Entity Header */}
            <div className="mb-6 border-b pb-6">
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className="text-3xl lg:text-4xl flex-shrink-0 mt-1">
                    {(() => {
                      const Icon = getEntityTypeIcon(entity.entity_type);
                      return <Icon className="h-10 w-10 lg:h-12 lg:w-12" />;
                    })()}
                  </div>
                  <div className="space-y-2 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h1 className="text-2xl lg:text-3xl font-bold tracking-tight">
                        {entity.name}
                      </h1>
                      <Badge variant={entity.status === "active" ? "default" : "secondary"}>
                        {entity.status}
                      </Badge>
                      <Badge variant="outline" className="font-mono">
                        {getEntityTypeLabel(entity.entity_type)}
                      </Badge>
                      <Badge variant="outline">
                        {entity.entity_class === "STRUCTURAL" ? "Structural" : "Access Group"}
                      </Badge>
                    </div>
                    {entity.description && (
                      <p className="text-muted-foreground">{entity.description}</p>
                    )}
                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      {entity.slug && (
                        <div className="flex items-center gap-1">
                          <Hash className="h-3 w-3" />
                          <span className="font-mono">{entity.slug}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        <span>Created {format(new Date(entity.created_at), 'PP')}</span>
                      </div>
                      {entity.valid_until && (
                        <div className="flex items-center gap-1 text-destructive">
                          <Calendar className="h-3 w-3" />
                          <span>Expires {format(new Date(entity.valid_until), 'PP')}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <Button onClick={() => setDrawerOpen(true)} className="flex-shrink-0">
                  <Edit className="mr-2 h-4 w-4" />
                  Edit Entity
                </Button>
              </div>
              
              {/* Direct Permissions - Compact Display */}
              {entity.direct_permissions && entity.direct_permissions.length > 0 && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="text-sm text-muted-foreground flex items-center gap-1">
                    <Shield className="h-3 w-3" />
                    Permissions:
                  </span>
                  {entity.direct_permissions.map((permission) => (
                    <Badge key={permission} variant="secondary" className="text-xs">
                      {permission}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            
            {/* Tabs for different sections */}
            <Tabs defaultValue="members" className="space-y-4">
              <TabsList>
                <TabsTrigger value="members">
                  <Users className="mr-2 h-4 w-4" />
                  Users
                </TabsTrigger>
                {isStructuralEntity(entity) && (
                  <TabsTrigger value="children">
                    <FolderTree className="mr-2 h-4 w-4" />
                    Child Entities ({childEntities?.length || 0})
                  </TabsTrigger>
                )}
                <TabsTrigger value="activity">
                  <Activity className="mr-2 h-4 w-4" />
                  Activity
                </TabsTrigger>
                <TabsTrigger value="settings">
                  <Settings className="mr-2 h-4 w-4" />
                  Settings
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="members" className="space-y-4">
                <EntityMembers 
                  entityId={entity.id}
                  entityName={entity.name}
                  canManageMembers={canManageMembers}
                />
              </TabsContent>
              
              {isStructuralEntity(entity) && (
                <TabsContent value="children" className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle>Child Entities</CardTitle>
                      <CardDescription>
                        Entities that belong to {entity.name}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      {childEntities && childEntities.length > 0 ? (
                        <div className="space-y-2">
                          {childEntities.map((child) => (
                            <Link
                              key={child.id}
                              to="/entities/$entityId"
                              params={{ entityId: child.id }}
                              className="flex items-center justify-between p-3 rounded-lg border hover:bg-accent transition-colors"
                            >
                              <div className="flex items-center gap-3">
                                {(() => {
                                  const Icon = getEntityTypeIcon(child.entity_type);
                                  return <Icon className="h-5 w-5" />;
                                })()}
                                <div>
                                  <p className="font-medium">{child.name}</p>
                                  {child.description && (
                                    <p className="text-sm text-muted-foreground">
                                      {child.description}
                                    </p>
                                  )}
                                </div>
                              </div>
                              <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            </Link>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-8">
                          <FolderTree className="h-12 w-12 text-muted-foreground mx-auto mb-2" />
                          <p className="text-muted-foreground">No child entities</p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>
              )}
              
              <TabsContent value="activity" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Activity Log</CardTitle>
                    <CardDescription>
                      Recent activities for this entity
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center py-8">
                      <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-2" />
                      <p className="text-muted-foreground">Activity tracking coming soon</p>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
              
              <TabsContent value="settings" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Entity Settings</CardTitle>
                    <CardDescription>
                      Configure advanced settings for this entity
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center py-8">
                      <Settings className="h-12 w-12 text-muted-foreground mx-auto mb-2" />
                      <p className="text-muted-foreground">Advanced settings coming soon</p>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </SidebarInset>
      
      <EntityDrawer 
        open={drawerOpen} 
        onOpenChange={setDrawerOpen}
        mode="edit"
        entity={entity}
      />
    </SidebarProvider>
  );
}