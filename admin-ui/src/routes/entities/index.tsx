import { useState, useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Search, Building2, ChevronRight, FolderOpen, Folder } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EntityDrawer } from "@/components/entities/entity-drawer";
import { requireAuth } from "@/lib/route-guards";
import { 
  Entity, 
  EntityClass, 
  EntityType, 
  getEntityTypeLabel, 
  getEntityTypeIcon,
  getEntityClassIcon,
  isStructuralEntity 
} from "@/types/entity";

export const Route = createFileRoute("/entities/")({
  beforeLoad: requireAuth,
  component: Entities,
});

async function fetchEntities(parentId?: string): Promise<Entity[]> {
  let url = "/v1/entities/";
  if (parentId) {
    url += `?parent_entity_id=${parentId}`;
  }
  const response = await authenticatedFetch(url);
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to fetch entities");
  }
  const data = await response.json();
  // API returns paginated response, extract items array
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  // Fallback for unexpected response format
  return Array.isArray(data) ? data : [];
}

async function fetchEntityPath(entityId: string): Promise<Entity[]> {
  const response = await authenticatedFetch(`/v1/entities/${entityId}/path`);
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to fetch entity path");
  }
  return response.json();
}

function EntityTypeBadge({ type }: { type: EntityType }) {
  const colors: Record<EntityType, string> = {
    [EntityType.PLATFORM]: "bg-purple-100 text-purple-800",
    [EntityType.ORGANIZATION]: "bg-blue-100 text-blue-800",
    [EntityType.DIVISION]: "bg-green-100 text-green-800",
    [EntityType.BRANCH]: "bg-yellow-100 text-yellow-800",
    [EntityType.TEAM]: "bg-orange-100 text-orange-800",
    [EntityType.FUNCTIONAL_GROUP]: "bg-pink-100 text-pink-800",
    [EntityType.PERMISSION_GROUP]: "bg-red-100 text-red-800",
    [EntityType.PROJECT_GROUP]: "bg-indigo-100 text-indigo-800",
    [EntityType.ROLE_GROUP]: "bg-teal-100 text-teal-800",
    [EntityType.ACCESS_GROUP]: "bg-gray-100 text-gray-800",
  };

  return (
    <Badge className={`${colors[type]} border-0`}>
      <span className="mr-1">{getEntityTypeIcon(type)}</span>
      {getEntityTypeLabel(type)}
    </Badge>
  );
}

function EntityCard({ 
  entity, 
  onNavigate, 
  onEdit,
  hasChildren 
}: { 
  entity: Entity; 
  onNavigate: () => void; 
  onEdit: () => void;
  hasChildren?: boolean;
}) {
  return (
    <Card className="group hover:shadow-md transition-shadow">
      <CardHeader 
        className="cursor-pointer" 
        onClick={hasChildren ? onNavigate : undefined}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-2xl">
              {hasChildren ? (
                <FolderOpen className="h-6 w-6 text-muted-foreground group-hover:text-foreground transition-colors" />
              ) : (
                getEntityTypeIcon(entity.entity_type)
              )}
            </div>
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                {entity.name}
                {hasChildren && (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
              </CardTitle>
              {entity.slug && (
                <p className="text-xs text-muted-foreground mt-0.5">{entity.slug}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <EntityTypeBadge type={entity.entity_type} />
            <Badge variant={entity.status === "active" ? "default" : "secondary"}>
              {entity.status}
            </Badge>
          </div>
        </div>
        {entity.description && (
          <CardDescription className="mt-2">
            {entity.description}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>Created {new Date(entity.created_at).toLocaleDateString()}</span>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
          >
            Edit
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function EntitiesContent({ 
  onEditEntity,
  onNavigateToEntity,
  searchQuery,
  classFilter,
  typeFilter,
  currentEntityId,
  childCounts
}: { 
  onEditEntity: (entity: Entity) => void;
  onNavigateToEntity: (entityId: string | null) => void;
  searchQuery: string;
  classFilter: string;
  typeFilter: string;
  currentEntityId: string | null;
  childCounts: Map<string, number>;
}) {
  const { data: entities, isLoading, error } = useQuery({
    queryKey: ["entities", currentEntityId],
    queryFn: () => fetchEntities(currentEntityId || undefined),
  });

  // Fetch current entity details if we're not at root
  const { data: currentEntity } = useQuery({
    queryKey: ["entity", currentEntityId],
    queryFn: async () => {
      if (!currentEntityId) return null;
      const response = await authenticatedFetch(`/v1/entities/${currentEntityId}`);
      if (!response.ok) throw new Error("Failed to fetch entity");
      return response.json();
    },
    enabled: !!currentEntityId,
  });

  // Fetch breadcrumb path
  const { data: breadcrumbPath } = useQuery({
    queryKey: ["entity-path", currentEntityId],
    queryFn: () => currentEntityId ? fetchEntityPath(currentEntityId) : Promise.resolve([]),
    enabled: !!currentEntityId,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
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
          <p className="text-destructive">Error loading entities: {error.message}</p>
        </CardContent>
      </Card>
    );
  }

  // Filter entities
  let filteredEntities = Array.isArray(entities) ? entities : [];
  
  if (searchQuery) {
    filteredEntities = filteredEntities.filter(entity => 
      entity.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      entity.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      entity.slug.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }
  
  if (classFilter && classFilter !== "all") {
    filteredEntities = filteredEntities.filter(entity => 
      entity.entity_class === classFilter
    );
  }
  
  if (typeFilter && typeFilter !== "all") {
    filteredEntities = filteredEntities.filter(entity => 
      entity.entity_type === typeFilter
    );
  }

  // Filter to only show root entities when no current entity
  if (!currentEntityId) {
    filteredEntities = filteredEntities.filter(entity => !entity.parent_entity_id);
  }

  return (
    <div className="space-y-4">
      {/* Breadcrumb Navigation */}
      {breadcrumbPath && breadcrumbPath.length > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigateToEntity(null)}
            className="h-8 px-2"
          >
            <Building2 className="h-4 w-4 mr-1" />
            All Entities
          </Button>
          {breadcrumbPath.map((entity, index) => (
            <div key={entity.id} className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onNavigateToEntity(entity.id)}
                className="h-8 px-2"
                disabled={index === breadcrumbPath.length - 1}
              >
                {getEntityTypeIcon(entity.entity_type)} {entity.name}
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Current Entity Info */}
      {currentEntity && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{getEntityTypeIcon(currentEntity.entity_type)}</span>
                <div>
                  <CardTitle>{currentEntity.name}</CardTitle>
                  <CardDescription>{currentEntity.description || "No description"}</CardDescription>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => onEditEntity(currentEntity)}>
                Edit
              </Button>
            </div>
          </CardHeader>
        </Card>
      )}

      {/* Entity List */}
      {filteredEntities.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-8">
              <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Child Entities</h3>
              <p className="text-muted-foreground mb-4">
                {currentEntity 
                  ? `No entities found under ${currentEntity.name}`
                  : "Create your first entity to start building your organizational structure"}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Group by class */}
          {filteredEntities.filter(isStructuralEntity).length > 0 && (
            <div>
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <span>{getEntityClassIcon(EntityClass.STRUCTURAL)}</span>
                Structural Entities
              </h3>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredEntities.filter(isStructuralEntity).map((entity) => (
                  <EntityCard 
                    key={entity.id} 
                    entity={entity} 
                    onNavigate={() => onNavigateToEntity(entity.id)}
                    onEdit={() => onEditEntity(entity)}
                    hasChildren={childCounts.get(entity.id) > 0}
                  />
                ))}
              </div>
            </div>
          )}
          
          {filteredEntities.filter(e => !isStructuralEntity(e)).length > 0 && (
            <div>
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <span>{getEntityClassIcon(EntityClass.ACCESS_GROUP)}</span>
                Access Groups
              </h3>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredEntities.filter(e => !isStructuralEntity(e)).map((entity) => (
                  <EntityCard 
                    key={entity.id} 
                    entity={entity} 
                    onNavigate={() => onNavigateToEntity(entity.id)}
                    onEdit={() => onEditEntity(entity)}
                    hasChildren={childCounts.get(entity.id) > 0}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Entities() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"create" | "edit">("create");
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [currentEntityId, setCurrentEntityId] = useState<string | null>(null);
  const [childCounts] = useState(new Map<string, number>());
  
  // Fetch all entities to calculate child counts
  const { data: allEntities } = useQuery({
    queryKey: ["all-entities"],
    queryFn: () => fetchEntities(),
  });
  
  // Calculate child counts
  useMemo(() => {
    if (!allEntities) return;
    childCounts.clear();
    allEntities.forEach(entity => {
      if (entity.parent_entity_id) {
        const count = childCounts.get(entity.parent_entity_id) || 0;
        childCounts.set(entity.parent_entity_id, count + 1);
      }
    });
  }, [allEntities, childCounts]);
  
  const handleCreateEntity = () => {
    setDrawerMode("create");
    setSelectedEntity(null);
    setDrawerOpen(true);
  };
  
  const handleEditEntity = (entity: Entity) => {
    setDrawerMode("edit");
    setSelectedEntity(entity);
    setDrawerOpen(true);
  };
  
  const handleNavigateToEntity = (entityId: string | null) => {
    setCurrentEntityId(entityId);
    // Reset filters when navigating
    setSearchQuery("");
    setClassFilter("all");
    setTypeFilter("all");
  };
  
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
                  <BreadcrumbPage>Entities</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="mx-auto w-full max-w-7xl">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">
                  {currentEntityId ? "Entity Details" : "Entity Management"}
                </h1>
                <p className="text-muted-foreground">
                  {currentEntityId 
                    ? "Navigate through your organizational hierarchy"
                    : "Manage your organizational structure and access groups"}
                </p>
              </div>
              <Button onClick={handleCreateEntity}>
                <Plus className="mr-2 h-4 w-4" />
                Create Entity
              </Button>
            </div>
            
            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-4 mb-6">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search entities..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Select value={classFilter} onValueChange={setClassFilter}>
                <SelectTrigger className="w-full sm:w-[180px]">
                  <SelectValue placeholder="Entity Class" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Classes</SelectItem>
                  <SelectItem value={EntityClass.STRUCTURAL}>
                    {getEntityClassIcon(EntityClass.STRUCTURAL)} Structural
                  </SelectItem>
                  <SelectItem value={EntityClass.ACCESS_GROUP}>
                    {getEntityClassIcon(EntityClass.ACCESS_GROUP)} Access Groups
                  </SelectItem>
                </SelectContent>
              </Select>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-full sm:w-[180px]">
                  <SelectValue placeholder="Entity Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value={EntityType.PLATFORM}>
                    {getEntityTypeIcon(EntityType.PLATFORM)} Platform
                  </SelectItem>
                  <SelectItem value={EntityType.ORGANIZATION}>
                    {getEntityTypeIcon(EntityType.ORGANIZATION)} Organization
                  </SelectItem>
                  <SelectItem value={EntityType.DIVISION}>
                    {getEntityTypeIcon(EntityType.DIVISION)} Division
                  </SelectItem>
                  <SelectItem value={EntityType.BRANCH}>
                    {getEntityTypeIcon(EntityType.BRANCH)} Branch
                  </SelectItem>
                  <SelectItem value={EntityType.TEAM}>
                    {getEntityTypeIcon(EntityType.TEAM)} Team
                  </SelectItem>
                  <Separator className="my-1" />
                  <SelectItem value={EntityType.FUNCTIONAL_GROUP}>
                    {getEntityTypeIcon(EntityType.FUNCTIONAL_GROUP)} Functional Group
                  </SelectItem>
                  <SelectItem value={EntityType.PERMISSION_GROUP}>
                    {getEntityTypeIcon(EntityType.PERMISSION_GROUP)} Permission Group
                  </SelectItem>
                  <SelectItem value={EntityType.PROJECT_GROUP}>
                    {getEntityTypeIcon(EntityType.PROJECT_GROUP)} Project Group
                  </SelectItem>
                  <SelectItem value={EntityType.ROLE_GROUP}>
                    {getEntityTypeIcon(EntityType.ROLE_GROUP)} Role Group
                  </SelectItem>
                  <SelectItem value={EntityType.ACCESS_GROUP}>
                    {getEntityTypeIcon(EntityType.ACCESS_GROUP)} Access Group
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <EntitiesContent 
              onEditEntity={handleEditEntity}
              onNavigateToEntity={handleNavigateToEntity}
              searchQuery={searchQuery}
              classFilter={classFilter}
              typeFilter={typeFilter}
              currentEntityId={currentEntityId}
              childCounts={childCounts}
            />
          </div>
        </div>
      </SidebarInset>
      
      <EntityDrawer 
        open={drawerOpen} 
        onOpenChange={setDrawerOpen}
        mode={drawerMode}
        entity={selectedEntity}
        defaultParentId={currentEntityId}
      />
    </SidebarProvider>
  );
}