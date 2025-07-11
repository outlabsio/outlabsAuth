import { useState, useMemo, useEffect } from "react";
import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { AppSidebar } from "@/components/app-sidebar";
import { useContextStore } from "@/stores/context-store";
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
import { Plus, Search, Building2, ChevronRight, FolderTree, Users, Calendar, MoreVertical, ArrowRight } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { useQuery } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EntityDrawer } from "@/components/entities/entity-drawer";
import { EntityTreeSidebar } from "@/components/entities/entity-tree-sidebar";
import { requireAuth } from "@/lib/route-guards";
import { cn } from "@/lib/utils";
import { 
  Entity, 
  EntityClass, 
  EntityType, 
  getEntityTypeLabel, 
  isStructuralEntity 
} from "@/types/entity";
import { getEntityTypeIcon, getEntityClassIcon } from "@/lib/entity-icons";

export const Route = createFileRoute("/entities/")({
  beforeLoad: requireAuth,
  component: Entities,
});

async function fetchEntities(parentId?: string, includeArchived: boolean = false): Promise<Entity[]> {
  let url = "/v1/entities/";
  const params = new URLSearchParams();
  if (parentId) {
    params.append("parent_entity_id", parentId);
  }
  if (!includeArchived) {
    params.append("status", "active");
  }
  if (params.toString()) {
    url += `?${params.toString()}`;
  }
  
  const response = await authenticatedFetch(url);
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
  return response.json();
}


function EntityCard({ 
  entity, 
  onNavigate, 
  onEdit,
  hasChildren,
  childCount = 0
}: { 
  entity: Entity; 
  onNavigate: () => void; 
  onEdit: () => void;
  hasChildren: boolean;
  childCount?: number;
}) {
  const navigate = useNavigate();
  
  const handleCardClick = () => {
    navigate({ to: '/entities/$entityId', params: { entityId: entity.id } });
  };
  
  // Get the appropriate icon
  const Icon = getEntityTypeIcon(entity.entity_type);
  
  // Determine card style based on entity type
  const isStructural = isStructuralEntity(entity);
  
  return (
    <Card className={cn(
      "group relative overflow-hidden transition-all duration-200",
      "hover:shadow-md hover:-translate-y-0.5",
      "bg-card hover:bg-accent/50",
      isStructural 
        ? "border-border dark:border-border" 
        : "border-muted dark:border-muted"
    )}>
      <div 
        className="px-3 py-1.5 cursor-pointer"
        onClick={handleCardClick}
      >
        {/* Ultra-compact single row */}
        <div className="flex items-center gap-2">
          {/* Icon with grayscale styling */}
          <Icon className={cn(
            "h-3.5 w-3.5 flex-shrink-0",
            isStructural ? "text-foreground" : "text-muted-foreground"
          )} />
          
          {/* Title */}
          <h3 className="font-medium text-sm leading-none truncate flex-1">
            {entity.display_name || entity.name}
          </h3>
          
          {/* Child count if has children */}
          {hasChildren && (
            <div className="flex items-center gap-0.5 text-muted-foreground">
              <Users className="h-3 w-3" />
              <span className="text-xs">{childCount}</span>
            </div>
          )}
          
          {/* Status badge if not active */}
          {entity.status !== "active" && (
            <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">
              {entity.status}
            </Badge>
          )}
          
          {/* Action button */}
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 -mr-1 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
          >
            <MoreVertical className="h-3 w-3" />
          </Button>
        </div>
        
        {/* Description on second line if present */}
        {entity.description && (
          <p className="text-xs text-muted-foreground truncate mt-0.5 pl-5 leading-none">
            {entity.description}
          </p>
        )}
      </div>
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
  childCounts,
  contextRootId
}: { 
  onEditEntity: (entity: Entity) => void;
  onNavigateToEntity: (entityId: string | null) => void;
  searchQuery: string;
  classFilter: string;
  typeFilter: string;
  currentEntityId: string | null;
  childCounts: Map<string, number>;
  contextRootId: string | null;
}) {
  // Determine what parent to query for
  const queryParentId = currentEntityId || contextRootId || undefined;
  
  const { data: entities, isLoading, error } = useQuery({
    queryKey: ["entities", queryParentId],
    queryFn: () => fetchEntities(queryParentId),
  });

  // Fetch current entity details if we're not at root
  const { data: currentEntity } = useQuery({
    queryKey: ["entity", currentEntityId],
    queryFn: async () => {
      if (!currentEntityId) return null;
      const response = await authenticatedFetch(`/v1/entities/${currentEntityId}`);
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

  // No additional filtering needed - the API already filters by parent

  return (
    <div className="space-y-4">
      {/* Breadcrumb Navigation */}
      {breadcrumbPath && breadcrumbPath.length > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigateToEntity(contextRootId)}
            className="h-8 px-2"
          >
            <Building2 className="h-4 w-4 mr-1" />
            {contextRootId ? "Context Root" : "All Entities"}
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
                {(() => {
                  const Icon = getEntityTypeIcon(entity.entity_type);
                  return (
                    <>
                      <Icon className="h-3 w-3 mr-1" />
                      {entity.name}
                    </>
                  );
                })()}
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
                {(() => {
                  const Icon = getEntityTypeIcon(currentEntity.entity_type);
                  return <Icon className="h-8 w-8" />;
                })()}
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
                {(() => {
                  const Icon = getEntityClassIcon(EntityClass.STRUCTURAL);
                  return <Icon className="h-5 w-5" />;
                })()}
                Structural Entities
              </h3>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredEntities.filter(isStructuralEntity).map((entity) => (
                  <EntityCard 
                    key={entity.id} 
                    entity={entity} 
                    onNavigate={() => onNavigateToEntity(entity.id)}
                    onEdit={() => onEditEntity(entity)}
                    hasChildren={(childCounts.get(entity.id) || 0) > 0}
                    childCount={childCounts.get(entity.id) || 0}
                  />
                ))}
              </div>
            </div>
          )}
          
          {filteredEntities.filter(e => !isStructuralEntity(e)).length > 0 && (
            <div>
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                {(() => {
                  const Icon = getEntityClassIcon(EntityClass.ACCESS_GROUP);
                  return <Icon className="h-5 w-5" />;
                })()}
                Access Groups
              </h3>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredEntities.filter(e => !isStructuralEntity(e)).map((entity) => (
                  <EntityCard 
                    key={entity.id} 
                    entity={entity} 
                    onNavigate={() => onNavigateToEntity(entity.id)}
                    onEdit={() => onEditEntity(entity)}
                    hasChildren={(childCounts.get(entity.id) || 0) > 0}
                    childCount={childCounts.get(entity.id) || 0}
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
  const { selectedOrganization, isSystemContext } = useContextStore();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"create" | "edit">("create");
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [treeOpen, setTreeOpen] = useState(false);
  
  // Start at the selected organization context, or null for system context
  const contextRootId = isSystemContext() ? null : selectedOrganization?.id || null;
  const [currentEntityId, setCurrentEntityId] = useState<string | null>(contextRootId);
  const [childCounts] = useState(new Map<string, number>());
  
  // Keyboard shortcut for tree view (Cmd/Ctrl + K)
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setTreeOpen(prev => !prev);
      }
    };
    
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);
  
  // Reset current entity when context changes
  useEffect(() => {
    setCurrentEntityId(contextRootId);
  }, [contextRootId]);
  
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
      const parentId = entity.parent_entity_id || 
        (entity.parent_entity && typeof entity.parent_entity === 'string' ? entity.parent_entity : 
         entity.parent_entity && typeof entity.parent_entity === 'object' ? entity.parent_entity.id : null);
      
      if (parentId) {
        const count = childCounts.get(parentId) || 0;
        childCounts.set(parentId, count + 1);
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
          <div className="flex items-center justify-between gap-2 px-4 w-full">
            <div className="flex items-center gap-2">
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
            <ThemeToggle />
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
                  {!isSystemContext() && selectedOrganization ? (
                    currentEntityId && currentEntityId !== contextRootId ? (
                      "Navigate through your organizational hierarchy"
                    ) : (
                      <>
                        Showing entities within <span className="font-medium">{selectedOrganization.name}</span>
                      </>
                    )
                  ) : currentEntityId ? (
                    "Navigate through your organizational hierarchy"
                  ) : (
                    "Manage all organizational structures and access groups"
                  )}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  onClick={() => setTreeOpen(true)}
                  className="relative"
                >
                  <FolderTree className="mr-2 h-4 w-4" />
                  Tree View
                  <kbd className="ml-2 pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100">
                    <span className="text-xs">⌘</span>K
                  </kbd>
                </Button>
                <Button onClick={handleCreateEntity}>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Entity
                </Button>
              </div>
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
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityClassIcon(EntityClass.STRUCTURAL);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Structural</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityClass.ACCESS_GROUP}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityClassIcon(EntityClass.ACCESS_GROUP);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Access Groups</span>
                    </div>
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
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.PLATFORM);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Platform</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityType.ORGANIZATION}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.ORGANIZATION);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Organization</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityType.DIVISION}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.DIVISION);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Division</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityType.BRANCH}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.BRANCH);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Branch</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityType.TEAM}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.TEAM);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Team</span>
                    </div>
                  </SelectItem>
                  <Separator className="my-1" />
                  <SelectItem value={EntityType.FUNCTIONAL_GROUP}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.FUNCTIONAL_GROUP);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Functional Group</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityType.PERMISSION_GROUP}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.PERMISSION_GROUP);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Permission Group</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityType.PROJECT_GROUP}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.PROJECT_GROUP);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Project Group</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityType.ROLE_GROUP}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.ROLE_GROUP);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Role Group</span>
                    </div>
                  </SelectItem>
                  <SelectItem value={EntityType.ACCESS_GROUP}>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = getEntityTypeIcon(EntityType.ACCESS_GROUP);
                        return <Icon className="h-4 w-4" />;
                      })()}
                      <span>Access Group</span>
                    </div>
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
              contextRootId={contextRootId}
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
      
      <EntityTreeSidebar
        open={treeOpen}
        onOpenChange={setTreeOpen}
        currentEntityId={currentEntityId}
        onSelectEntity={handleNavigateToEntity}
      />
    </SidebarProvider>
  );
}