import { ReactNode } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { PageHeader, BreadcrumbItem } from "@/components/layout/page-header";
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

interface PageLayoutProps {
  children: ReactNode;
  breadcrumbs: BreadcrumbItem[];
  actions?: ReactNode;
  showThemeToggle?: boolean;
  className?: string;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl" | "6xl" | "7xl" | "full";
}

const maxWidthClasses = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
  "2xl": "max-w-2xl",
  "6xl": "max-w-6xl",
  "7xl": "max-w-7xl",
  full: "max-w-full",
};

export function PageLayout({ 
  children, 
  breadcrumbs, 
  actions,
  showThemeToggle = true,
  className,
  maxWidth = "7xl" 
}: PageLayoutProps) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <PageHeader 
          breadcrumbs={breadcrumbs}
          actions={actions}
          showThemeToggle={showThemeToggle}
        />
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className={cn("mx-auto w-full", maxWidthClasses[maxWidth], className)}>
            {children}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}