import { useNavigate } from "@tanstack/react-router";
import { MoreVertical, Users } from "lucide-react";
import { Entity, isStructuralEntity } from "@/types/entity";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getEntityTypeIcon } from "@/lib/entity-icons";

interface EntityCardProps {
  entity: Entity;
  onNavigate: () => void;
  onEdit: () => void;
  hasChildren: boolean;
  childCount?: number;
}

export function EntityCard({ 
  entity, 
  onNavigate, 
  onEdit,
  hasChildren,
  childCount = 0
}: EntityCardProps) {
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