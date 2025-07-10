import { useState, useEffect, useMemo, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useContextStore } from "@/stores/context-store";
import { authenticatedFetch } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ChevronRight,
  ChevronDown,
  Search,
  Building2,
  Users,
  Shield,
  Briefcase,
  GitBranch,
  FolderTree,
  Loader2,
  X,
  Home,
  Building,
  Globe,
  Layers,
  Network,
  UserCheck,
  Lock,
  FolderOpen,
  Key,
  UserCog,
} from "lucide-react";
import { 
  Entity, 
  EntityType,
  getEntityTypeIcon,
  isStructuralEntity 
} from "@/types/entity";

interface EntityTreeNodeData extends Entity {
  children?: EntityTreeNodeData[];
  isLoading?: boolean;
  isExpanded?: boolean;
  childCount?: number;
}

interface EntityTreeSidebarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentEntityId: string | null;
  onSelectEntity: (entityId: string | null) => void;
}

// Enhanced icon mapping for better visual hierarchy
const entityTypeIcons: Record<EntityType, React.ReactNode> = {
  [EntityType.PLATFORM]: <Globe className="h-4 w-4" />,
  [EntityType.ORGANIZATION]: <Building2 className="h-4 w-4" />,
  [EntityType.DIVISION]: <Building className="h-4 w-4" />,
  [EntityType.BRANCH]: <GitBranch className="h-4 w-4" />,
  [EntityType.TEAM]: <Users className="h-4 w-4" />,
  [EntityType.FUNCTIONAL_GROUP]: <Briefcase className="h-4 w-4" />,
  [EntityType.PERMISSION_GROUP]: <Lock className="h-4 w-4" />,
  [EntityType.PROJECT_GROUP]: <FolderOpen className="h-4 w-4" />,
  [EntityType.ROLE_GROUP]: <Key className="h-4 w-4" />,
  [EntityType.ACCESS_GROUP]: <UserCog className="h-4 w-4" />,
};

async function fetchEntityChildren(entityId: string | null): Promise<Entity[]> {
  const params = new URLSearchParams({ status: "active" });
  if (entityId) {
    params.append("parent_entity_id", entityId);
  }
  
  const response = await authenticatedFetch(`/v1/entities/?${params}`);
  const data = await response.json();
  return data.items || [];
}

function highlightText(text: string, searchTerm: string) {
  if (!searchTerm) return text;
  
  const regex = new RegExp(`(${searchTerm})`, 'gi');
  const parts = text.split(regex);
  
  return parts.map((part, i) => 
    regex.test(part) ? (
      <span key={i} className="bg-yellow-200 dark:bg-yellow-900 font-semibold">
        {part}
      </span>
    ) : (
      part
    )
  );
}

function EntityTreeNode({ 
  node, 
  level = 0, 
  searchTerm,
  currentEntityId,
  onSelectEntity,
  expandedNodes,
  onToggleExpand,
  matchedNodes,
}: {
  node: EntityTreeNodeData;
  level?: number;
  searchTerm: string;
  currentEntityId: string | null;
  onSelectEntity: (entityId: string) => void;
  expandedNodes: Set<string>;
  onToggleExpand: (nodeId: string) => void;
  matchedNodes: Set<string>;
}) {
  const queryClient = useQueryClient();
  const isExpanded = expandedNodes.has(node.id);
  const hasChildren = node.entity_class === "STRUCTURAL"; // Only structural entities can have children
  const isSelected = currentEntityId === node.id;
  const isMatched = matchedNodes.has(node.id);
  
  // Fetch children when expanded
  const { data: children, isLoading } = useQuery({
    queryKey: ["entity-children", node.id],
    queryFn: () => fetchEntityChildren(node.id),
    enabled: isExpanded && hasChildren,
    staleTime: 30000, // Cache for 30 seconds
  });
  
  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren) {
      onToggleExpand(node.id);
    }
  };
  
  const handleSelect = () => {
    onSelectEntity(node.id);
  };
  
  // Visual depth indicator
  const depthIndicator = level > 0 && (
    <div 
      className="absolute left-0 top-0 bottom-0 flex items-center"
      style={{ paddingLeft: `${(level - 1) * 20 + 10}px` }}
    >
      <div className="w-px h-full bg-border opacity-50" />
    </div>
  );
  
  // Node expansion indicator
  const expansionIndicator = hasChildren && (
    <Button
      variant="ghost"
      size="icon"
      className="h-5 w-5 p-0"
      onClick={handleToggle}
    >
      {isLoading ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : isExpanded ? (
        <ChevronDown className="h-3 w-3" />
      ) : (
        <ChevronRight className="h-3 w-3" />
      )}
    </Button>
  );
  
  // Count indicator for structural entities
  const childCountIndicator = hasChildren && children && (
    <span className="text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity ml-auto">
      {children.length}
    </span>
  );
  
  return (
    <div className="relative group/node">
      {depthIndicator}
      
      <div
        className={cn(
          "group relative flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-all duration-200",
          "hover:bg-accent hover:text-accent-foreground",
          isSelected && "bg-accent text-accent-foreground font-medium shadow-sm",
          isMatched && !searchTerm && "ring-1 ring-primary/20",
          !isMatched && searchTerm && "opacity-40"
        )}
        style={{ paddingLeft: `${level * 20 + 8}px` }}
        onClick={handleSelect}
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {expansionIndicator || <div className="w-5" />}
          
          <div className={cn(
            "flex items-center justify-center",
            isStructuralEntity(node) ? "text-blue-600 dark:text-blue-400" : "text-purple-600 dark:text-purple-400"
          )}>
            {entityTypeIcons[node.entity_type]}
          </div>
          
          <span className="truncate flex-1">
            {highlightText(node.name, searchTerm)}
          </span>
          
          
          {/* Child count for collapsed nodes */}
          {!isExpanded && hasChildren && !isLoading && children === undefined && (
            <span className="text-xs text-muted-foreground opacity-60">
              ...
            </span>
          )}
        </div>
        
        {childCountIndicator}
        
        {/* Entity slug on hover */}
        {node.slug && (
          <span className="text-xs text-muted-foreground truncate max-w-[80px] opacity-0 group-hover:opacity-100 transition-opacity">
            {node.slug}
          </span>
        )}
      </div>
      
      {/* Connection line for expanded nodes */}
      {isExpanded && children && children.length > 0 && level > 0 && (
        <div 
          className="absolute w-px bg-border opacity-50"
          style={{ 
            left: `${(level - 1) * 20 + 10}px`,
            top: '28px',
            bottom: '4px'
          }}
        />
      )}
      
      {/* Render children with animation */}
      <div
        className={cn(
          "overflow-hidden transition-all duration-200",
          isExpanded && children && children.length > 0 ? "max-h-[5000px] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        {isExpanded && children && children.length > 0 && (
          <div className="relative">
            {children.map((child, index) => (
              <EntityTreeNode
                key={child.id}
                node={child}
                level={level + 1}
                searchTerm={searchTerm}
                currentEntityId={currentEntityId}
                onSelectEntity={onSelectEntity}
                expandedNodes={expandedNodes}
                onToggleExpand={onToggleExpand}
                matchedNodes={matchedNodes}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function EntityTreeSidebar({
  open,
  onOpenChange,
  currentEntityId,
  onSelectEntity,
}: EntityTreeSidebarProps) {
  const { selectedOrganization, isSystemContext } = useContextStore();
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();
  
  // Determine the root based on context
  const contextRootId = isSystemContext() ? null : selectedOrganization?.id || null;
  
  // Fetch root entities
  const { data: rootEntities, isLoading: isLoadingRoots } = useQuery({
    queryKey: ["entity-roots", contextRootId],
    queryFn: () => fetchEntityChildren(contextRootId),
    staleTime: 30000,
  });
  
  // Search through all cached entities
  const matchedNodes = useMemo(() => {
    const matches = new Set<string>();
    if (!searchTerm) return matches;
    
    const searchLower = searchTerm.toLowerCase();
    
    // Search through all cached entity queries
    const cache = queryClient.getQueryCache();
    cache.getAll().forEach(query => {
      if (query.queryKey[0] === "entity-children") {
        const entities = query.state.data as Entity[] | undefined;
        entities?.forEach(entity => {
          if (
            entity.name.toLowerCase().includes(searchLower) ||
            entity.slug?.toLowerCase().includes(searchLower) ||
            entity.description?.toLowerCase().includes(searchLower)
          ) {
            matches.add(entity.id);
          }
        });
      }
    });
    
    // Also search root entities
    rootEntities?.forEach(entity => {
      if (
        entity.name.toLowerCase().includes(searchLower) ||
        entity.slug?.toLowerCase().includes(searchLower) ||
        entity.description?.toLowerCase().includes(searchLower)
      ) {
        matches.add(entity.id);
      }
    });
    
    return matches;
  }, [searchTerm, rootEntities, queryClient]);
  
  // Auto-expand to show current entity path
  useEffect(() => {
    if (currentEntityId && open) {
      // Fetch the path to the current entity
      const fetchAndExpandPath = async () => {
        try {
          const response = await authenticatedFetch(`/v1/entities/${currentEntityId}/path`);
          const path = await response.json();
          
          // Expand all nodes in the path
          const pathIds = new Set<string>();
          path.forEach((entity: Entity) => {
            if (entity.id !== currentEntityId) {
              pathIds.add(entity.id);
            }
          });
          
          setExpandedNodes(prev => {
            const next = new Set(prev);
            pathIds.forEach(id => next.add(id));
            return next;
          });
        } catch (error) {
          console.error('Failed to fetch entity path:', error);
        }
      };
      
      fetchAndExpandPath();
    }
  }, [currentEntityId, open]);
  
  const handleToggleExpand = useCallback((nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);
  
  const handleSelectRoot = () => {
    onSelectEntity(contextRootId);
  };
  
  // Expand all nodes when searching
  useEffect(() => {
    if (searchTerm) {
      // Expand all nodes to show search results
      const allNodeIds = new Set<string>();
      rootEntities?.forEach(entity => allNodeIds.add(entity.id));
      
      // Get all cached children
      const cache = queryClient.getQueryCache();
      cache.getAll().forEach(query => {
        if (query.queryKey[0] === "entity-children") {
          const entities = query.state.data as Entity[] | undefined;
          entities?.forEach(entity => allNodeIds.add(entity.id));
        }
      });
      
      setExpandedNodes(allNodeIds);
    } else {
      // Collapse all when search is cleared
      setExpandedNodes(new Set());
    }
  }, [searchTerm, rootEntities, queryClient]);
  
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-[350px] sm:w-[400px] p-0">
        <SheetHeader className="px-6 py-4 border-b">
          <SheetTitle className="flex items-center gap-2">
            <FolderTree className="h-5 w-5" />
            Entity Navigator
          </SheetTitle>
          <SheetDescription>
            {isSystemContext() 
              ? "Browse all entities in the system" 
              : `Browse entities within ${selectedOrganization?.name}`
            }
          </SheetDescription>
        </SheetHeader>
        
        {/* Search */}
        <div className="px-4 py-3 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search entities..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-9"
            />
            {searchTerm && (
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                onClick={() => setSearchTerm("")}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
          {searchTerm && matchedNodes.size > 0 && (
            <p className="text-xs text-muted-foreground mt-2">
              Found {matchedNodes.size} matching {matchedNodes.size === 1 ? 'entity' : 'entities'}
            </p>
          )}
        </div>
        
        {/* Tree Content */}
        <ScrollArea className="flex-1 px-4 py-2" onKeyDown={(e) => {
          // Add keyboard navigation
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            // TODO: Implement keyboard navigation
          }
        }}>
          {/* Root/Home button */}
          <div
            className={cn(
              "flex items-center gap-2 px-2 py-1.5 mb-2 rounded-md cursor-pointer transition-all duration-200",
              "hover:bg-accent hover:text-accent-foreground",
              currentEntityId === contextRootId && "bg-accent text-accent-foreground font-medium shadow-sm"
            )}
            onClick={handleSelectRoot}
          >
            <Home className="h-4 w-4" />
            <span>
              {contextRootId 
                ? `${selectedOrganization?.name} Home`
                : "All Entities"
              }
            </span>
            {rootEntities && (
              <span className="ml-auto text-xs text-muted-foreground">
                {rootEntities.length}
              </span>
            )}
          </div>
          
          {/* Loading state */}
          {isLoadingRoots ? (
            <div className="space-y-2">
              {[1, 2, 3].map(i => (
                <div key={i} className="flex items-center gap-2 px-2 py-1.5">
                  <Skeleton className="h-4 w-4" />
                  <Skeleton className="h-4 flex-1" />
                </div>
              ))}
            </div>
          ) : rootEntities && rootEntities.length > 0 ? (
            <div className="space-y-0.5">
              {rootEntities.map(entity => (
                <EntityTreeNode
                  key={entity.id}
                  node={entity}
                  searchTerm={searchTerm}
                  currentEntityId={currentEntityId}
                  onSelectEntity={onSelectEntity}
                  expandedNodes={expandedNodes}
                  onToggleExpand={handleToggleExpand}
                  matchedNodes={matchedNodes}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Building2 className="h-12 w-12 mx-auto mb-2 opacity-20" />
              <p className="text-sm">No entities found</p>
            </div>
          )}
        </ScrollArea>
        
        {/* Footer with stats */}
        <div className="px-6 py-3 border-t bg-muted/50">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{rootEntities?.length || 0} root entities</span>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-6 text-xs">
                    <Network className="h-3 w-3 mr-1" />
                    View Graph
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Coming soon: Interactive entity relationship graph</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}