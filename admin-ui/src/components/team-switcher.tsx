"use client"

import * as React from "react"
import { ChevronsUpDown, Plus, Building2, Shield, Building, Users } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { authenticatedFetch } from "@/lib/auth"
import { useContextStore, SYSTEM_CONTEXT } from "@/stores/context-store"
import { cn } from "@/lib/utils"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { Skeleton } from "@/components/ui/skeleton"

interface Organization {
  id: string;
  name: string;
  slug: string;
  entity_type: string;
  entity_class: string;
  description?: string;
}

async function fetchTopLevelOrganizations(): Promise<Organization[]> {
  const response = await authenticatedFetch("/v1/entities/top-level-organizations");
  return response.json();
}

const entityTypeIcons: Record<string, React.ElementType> = {
  'PLATFORM': Shield,
  'ORGANIZATION': Building2,
  'DIVISION': Building,
  'BRANCH': Building,
  'TEAM': Users,
  'SYSTEM': Shield,
};

export function TeamSwitcher() {
  const { isMobile } = useSidebar()
  const { 
    selectedOrganization, 
    setSelectedOrganization, 
    availableOrganizations,
    setAvailableOrganizations 
  } = useContextStore();
  
  // Fetch organizations
  const { data: organizations, isLoading } = useQuery({
    queryKey: ["top-level-organizations"],
    queryFn: fetchTopLevelOrganizations,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
  
  // Update available organizations when data is loaded
  React.useEffect(() => {
    if (organizations) {
      setAvailableOrganizations(organizations);
    }
  }, [organizations, setAvailableOrganizations]);
  
  // Handle organization switch
  const handleContextSwitch = (org: Organization | typeof SYSTEM_CONTEXT) => {
    setSelectedOrganization(org);
    // Force a page refresh to reload data with new context
    window.location.reload();
  };
  
  if (isLoading) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton size="lg" disabled>
            <Skeleton className="h-8 w-8 rounded-lg" />
            <div className="grid flex-1 gap-1">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-16" />
            </div>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }
  
  const currentOrg = selectedOrganization || SYSTEM_CONTEXT;
  const Icon = entityTypeIcons[currentOrg.entity_type] || Building2;
  
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <div className={cn(
                "flex aspect-square size-8 items-center justify-center rounded-lg",
                currentOrg.is_system 
                  ? "bg-purple-600 text-white" 
                  : "bg-sidebar-primary text-sidebar-primary-foreground"
              )}>
                <Icon className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{currentOrg.name}</span>
                <span className="truncate text-xs">
                  {currentOrg.is_system ? "Platform Admin" : currentOrg.entity_type}
                </span>
              </div>
              <ChevronsUpDown className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
            align="start"
            side={isMobile ? "bottom" : "right"}
            sideOffset={4}
          >
            <DropdownMenuLabel className="text-muted-foreground text-xs">
              Organization Context
            </DropdownMenuLabel>
            
            {availableOrganizations.map((org, index) => {
              const OrgIcon = entityTypeIcons[org.entity_type] || Building2;
              const isActive = currentOrg.id === org.id;
              
              return (
                <DropdownMenuItem
                  key={org.id}
                  onClick={() => handleContextSwitch(org)}
                  className={cn("gap-2 p-2", isActive && "bg-accent")}
                >
                  <div className={cn(
                    "flex size-6 items-center justify-center rounded-md",
                    org.is_system 
                      ? "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300" 
                      : "border"
                  )}>
                    <OrgIcon className="size-3.5 shrink-0" />
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{org.name}</div>
                    {org.description && (
                      <div className="text-xs text-muted-foreground">{org.description}</div>
                    )}
                  </div>
                  {index < 9 && (
                    <DropdownMenuShortcut>⌘{index + 1}</DropdownMenuShortcut>
                  )}
                </DropdownMenuItem>
              );
            })}
            
            {availableOrganizations.length === 1 && (
              <div className="p-2 text-sm text-muted-foreground text-center">
                No other organizations available
              </div>
            )}
            
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2 p-2" disabled>
              <div className="flex size-6 items-center justify-center rounded-md border bg-transparent">
                <Plus className="size-4" />
              </div>
              <div className="text-muted-foreground font-medium">Create Organization</div>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}