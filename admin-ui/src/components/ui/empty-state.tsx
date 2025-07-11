import { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: LucideIcon;
  };
  className?: string;
  compact?: boolean;
}

export function EmptyState({ 
  icon: Icon, 
  title, 
  description, 
  action, 
  className,
  compact = false 
}: EmptyStateProps) {
  const content = (
    <div className={cn("text-center", compact ? "py-6" : "py-8")}>
      {Icon && (
        <Icon className={cn(
          "text-muted-foreground mx-auto mb-4",
          compact ? "h-8 w-8" : "h-12 w-12"
        )} />
      )}
      <h3 className={cn(
        "font-semibold mb-2",
        compact ? "text-base" : "text-lg"
      )}>
        {title}
      </h3>
      {description && (
        <p className="text-muted-foreground mb-4">{description}</p>
      )}
      {action && (
        <Button onClick={action.onClick} size={compact ? "sm" : "default"}>
          {action.icon && <action.icon className="mr-2 h-4 w-4" />}
          {action.label}
        </Button>
      )}
    </div>
  );

  if (compact) {
    return content;
  }

  return (
    <Card className={className}>
      <CardContent className="pt-6">
        {content}
      </CardContent>
    </Card>
  );
}