import { useState, useMemo, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useContextStore } from "@/stores/context-store";
import { PageLayout } from "@/components/layout/page-layout";
import { PageTitle } from "@/components/ui/page-title";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingGrid } from "@/components/ui/loading-grid";
import { SearchFilterBar } from "@/components/ui/search-filter-bar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Building2, ChevronRight, FolderTree } from "lucide-react";
import { EntityDrawer } from "@/components/entities/entity-drawer";
import { EntityTreeSidebar } from "@/components/entities/entity-tree-sidebar";
import { EntityCard } from "@/components/entities/entity-card";
import { requireAuth } from "@/lib/route-guards";
import { useDrawerState } from "@/hooks/use-drawer-state";
import { useEntities, useEntity, useEntityPath } from "@/hooks/api/use-entities";
import { useNotificationStore } from "@/stores/notification-store";
import { 
  type Entity, 
  type EntityClass,
  isStructuralEntity 
} from "@/lib/api/types";
import { getEntityTypeIcon, getEntityClassIcon } from "@/lib/entity-icons";

export const Route = createFileRoute("/entities/")({
  beforeLoad: requireAuth,
  component: Entities,
});




function EntitiesContent({ 
  entities,
  isLoading,
  error,
  currentEntity,
  breadcrumbPath,
  onEditEntity,
  onNavigateToEntity,
  childCounts,
  contextRootId
}: { 
  entities: Entity[];
  isLoading: boolean;
  error: unknown;
  currentEntity?: Entity | null;
  breadcrumbPath: Entity[];
  onEditEntity: (entity: Entity) => void;
  onNavigateToEntity: (entityId: string | null) => void;
  childCounts: Map<string, number>;
  contextRootId: string | null;
}) {
  if (isLoading) {
    return <LoadingGrid />;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading entities: {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Breadcrumb Navigation */}
      {breadcrumbPath.length > 0 && (
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
      {entities.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No Child Entities"
          description={
            currentEntity 
              ? `No entities found under ${currentEntity.name}`
              : "Create your first entity to start building your organizational structure"
          }
          action={{
            label: "Create Entity",
            onClick: () => onEditEntity({} as Entity),
            icon: Plus,
          }}
        />
      ) : (
        <div className="space-y-6">
          {/* Group by class */}
          {entities.filter(isStructuralEntity).length > 0 && (
            <div>
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                {(() => {
                  const Icon = getEntityClassIcon("STRUCTURAL");
                  return <Icon className="h-5 w-5" />;
                })()}
                Structural Entities
              </h3>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {entities.filter(isStructuralEntity).map((entity) => (
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
          
          {entities.filter(e => !isStructuralEntity(e)).length > 0 && (
            <div>
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                {(() => {
                  const Icon = getEntityClassIcon("ACCESS_GROUP");
                  return <Icon className="h-5 w-5" />;
                })()}
                Access Groups
              </h3>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {entities.filter(e => !isStructuralEntity(e)).map((entity) => (
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
  const drawer = useDrawerState<Entity>();
  const { success, error } = useNotificationStore();
  
  const [searchQuery, setSearchQuery] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [treeOpen, setTreeOpen] = useState(false);
  
  // Start at the selected organization context, or null for system context
  const contextRootId = isSystemContext() ? null : selectedOrganization?.id || null;
  const [currentEntityId, setCurrentEntityId] = useState<string | null>(contextRootId);
  
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
  
  // Use our custom hooks
  const { data: entitiesData, isLoading, error: entitiesError } = useEntities({
    parentId: currentEntityId || contextRootId || undefined,
    status: "active",
  });
  
  const { data: currentEntity } = useEntity(currentEntityId);
  const { data: breadcrumbPath } = useEntityPath(currentEntityId);
  
  // Calculate child counts
  const childCounts = useMemo(() => {
    const counts = new Map<string, number>();
    if (!entitiesData?.items) return counts;
    
    entitiesData.items.forEach(entity => {
      const parentId = entity.parent_entity_id;
      if (parentId) {
        counts.set(parentId, (counts.get(parentId) || 0) + 1);
      }
    });
    
    return counts;
  }, [entitiesData]);
  
  // Filter entities
  const filteredEntities = useMemo(() => {
    let items = entitiesData?.items || [];
    
    if (searchQuery) {
      items = items.filter(entity => 
        entity.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entity.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entity.slug.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    if (classFilter !== "all") {
      items = items.filter(entity => entity.entity_class === classFilter);
    }
    
    if (typeFilter !== "all") {
      items = items.filter(entity => entity.entity_type === typeFilter);
    }
    
    return items;
  }, [entitiesData, searchQuery, classFilter, typeFilter]);
  
  const handleNavigateToEntity = (entityId: string | null) => {
    setCurrentEntityId(entityId);
    // Reset filters when navigating
    setSearchQuery("");
    setClassFilter("all");
    setTypeFilter("all");
  };
  
  const handleSaveSuccess = () => {
    success(
      drawer.mode === "create" ? "Entity created" : "Entity updated",
      drawer.mode === "create" 
        ? "The entity has been created successfully" 
        : "The entity has been updated successfully"
    );
    drawer.close();
  };
  
  return (
    <PageLayout
      breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: "Entities" }
      ]}
    >
      <PageTitle
        title={currentEntityId ? "Entity Details" : "Entity Management"}
        description={
          !isSystemContext() && selectedOrganization ? (
            currentEntityId && currentEntityId !== contextRootId ? (
              "Navigate through your organizational hierarchy"
            ) : (
              <>Showing entities within <span className="font-medium">{selectedOrganization.name}</span></>
            )
          ) : currentEntityId ? (
            "Navigate through your organizational hierarchy"
          ) : (
            "Manage all organizational structures and access groups"
          )
        }
        action={
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
            <Button onClick={drawer.openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Create Entity
            </Button>
          </div>
        }
      />
      
      {/* Filters */}
      <SearchFilterBar
        searchValue={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search entities..."
        filters={
          <>
            <Select value={classFilter} onValueChange={setClassFilter}>
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Entity Class" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Classes</SelectItem>
                <SelectItem value="STRUCTURAL">
                  <div className="flex items-center gap-2">
                    {(() => {
                      const Icon = getEntityClassIcon("STRUCTURAL");
                      return <Icon className="h-4 w-4" />;
                    })()}
                    <span>Structural</span>
                  </div>
                </SelectItem>
                <SelectItem value="ACCESS_GROUP">
                  <div className="flex items-center gap-2">
                    {(() => {
                      const Icon = getEntityClassIcon("ACCESS_GROUP");
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
                {/* Add entity types here */}
              </SelectContent>
            </Select>
          </>
        }
        className="mb-6"
      />
      
      <EntitiesContent 
        entities={filteredEntities}
        isLoading={isLoading}
        error={entitiesError}
        currentEntity={currentEntity}
        breadcrumbPath={breadcrumbPath || []}
        onEditEntity={drawer.openEdit}
        onNavigateToEntity={handleNavigateToEntity}
        childCounts={childCounts}
        contextRootId={contextRootId}
      />
      
      <EntityDrawer 
        open={drawer.isOpen} 
        onOpenChange={(open) => !open && drawer.close()}
        mode={drawer.mode}
        entity={drawer.selectedItem}
        defaultParentId={currentEntityId}
        onSuccess={handleSaveSuccess}
      />
      
      <EntityTreeSidebar
        open={treeOpen}
        onOpenChange={setTreeOpen}
        currentEntityId={currentEntityId}
        onSelectEntity={handleNavigateToEntity}
      />
    </PageLayout>
  );
}