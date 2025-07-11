import { ReactNode } from "react";

interface PageTitleProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function PageTitle({ title, description, action }: PageTitleProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && (
          <p className="text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}