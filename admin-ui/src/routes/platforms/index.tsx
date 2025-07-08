import { useState } from "react";
import { createFileRoute, redirect } from "@tanstack/react-router";
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
import { Plus, Globe } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { useQuery } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { CreatePlatformDrawer } from "@/components/platforms/create-platform-drawer";

export const Route = createFileRoute("/platforms/")({
  beforeLoad: async () => {
    // Check if user is authenticated using the store
    const { isAuthenticated } = useAuthStore.getState();
    if (!isAuthenticated) {
      throw redirect({
        to: "/login",
      });
    }
  },
  component: Platforms,
});

interface Platform {
  _id: string;
  name: string;
  description: string;
  is_active: boolean;
  is_platform_root: boolean;
  created_by_client?: string;
  created_at: string;
  updated_at: string;
}

async function fetchPlatforms(): Promise<Platform[]> {
  const response = await authenticatedFetch("/v1/client_accounts/");
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to fetch platforms");
  }
  const allAccounts = await response.json();
  // Filter to only show platform root accounts
  return allAccounts.filter((account: Platform) => account.is_platform_root);
}

function PlatformCard({ platform }: { platform: Platform }) {
  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-lg">{platform.name}</CardTitle>
          </div>
          <Badge variant={platform.is_active ? "default" : "secondary"}>
            {platform.is_active ? "Active" : "Inactive"}
          </Badge>
        </div>
        <CardDescription className="mt-2">
          {platform.description || "No description available"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="text-sm text-muted-foreground">
          Created on {new Date(platform.created_at).toLocaleDateString()}
        </div>
      </CardContent>
    </Card>
  );
}

function PlatformsContent() {
  const { data: platforms, isLoading, error } = useQuery({
    queryKey: ["platforms"],
    queryFn: fetchPlatforms,
  });

  if (isLoading) {
    return (
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
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">Error loading platforms: {error.message}</p>
        </CardContent>
      </Card>
    );
  }

  if (!platforms || platforms.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-8">
            <Globe className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Platforms Yet</h3>
            <p className="text-muted-foreground mb-4">
              Create your first platform to start organizing your multi-tenant architecture.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {platforms.map((platform) => (
        <PlatformCard key={platform._id} platform={platform} />
      ))}
    </div>
  );
}

function Platforms() {
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  
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
                  <BreadcrumbPage>Platforms</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="mx-auto w-full max-w-7xl">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Platform Management</h1>
                <p className="text-muted-foreground">
                  Manage multi-tenant platforms and their client organizations
                </p>
              </div>
              <Button onClick={() => setCreateDrawerOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Platform
              </Button>
            </div>
            
            <PlatformsContent />
          </div>
        </div>
      </SidebarInset>
      
      <CreatePlatformDrawer 
        open={createDrawerOpen} 
        onOpenChange={setCreateDrawerOpen} 
      />
    </SidebarProvider>
  );
}