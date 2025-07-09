import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Plus, Search, Shield, Globe, MoreHorizontal, Pencil, Trash2, Building2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { requireAuth } from "@/lib/route-guards";
import { PermissionDrawer } from "@/components/permissions/permission-drawer";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const Route = createFileRoute("/permissions/")({
  beforeLoad: requireAuth,
  component: Permissions,
});

interface Permission {
  id: string;
  name: string;
  display_name: string;
  description: string;
  scope: "system" | "platform";
  scope_id?: string | null;
  resource: string;
  action: string;
  created_at: string;
  updated_at: string;
}

interface Platform {
  _id: string;
  name: string;
  status: string;
}

interface PermissionsResponse {
  system_permissions: Permission[];
  platform_permissions: Permission[];
}

async function fetchPermissions(): Promise<PermissionsResponse> {
  const response = await authenticatedFetch("/v1/permissions/available");
  return response.json();
}

async function fetchPlatforms(): Promise<Platform[]> {
  const response = await authenticatedFetch("/v1/platforms/");
  return response.json();
}

function Permissions() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPlatform, setSelectedPlatform] = useState<string>("all");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"create" | "edit">("create");
  const [selectedPermission, setSelectedPermission] = useState<Permission | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["permissions"],
    queryFn: fetchPermissions,
  });

  const { data: platforms = [] } = useQuery({
    queryKey: ["platforms"],
    queryFn: fetchPlatforms,
  });

  // Combine and filter permissions
  const allPermissions = [
    ...(data?.system_permissions || []),
    ...(data?.platform_permissions || []),
  ];

  const filteredPermissions = allPermissions.filter((permission) => {
    const search = searchQuery.toLowerCase();
    const matchesSearch = (
      permission.name.toLowerCase().includes(search) ||
      permission.display_name.toLowerCase().includes(search) ||
      permission.description?.toLowerCase().includes(search) ||
      permission.resource.toLowerCase().includes(search) ||
      permission.action.toLowerCase().includes(search)
    );
    
    // Filter by platform
    if (selectedPlatform === "all") return matchesSearch;
    if (selectedPlatform === "system") return matchesSearch && permission.scope === "system";
    return matchesSearch && permission.scope === "platform" && permission.scope_id === selectedPlatform;
  });

  const handleCreatePermission = () => {
    setSelectedPermission(null);
    setDrawerMode("create");
    setDrawerOpen(true);
  };

  const handleEditPermission = (permission: Permission) => {
    setSelectedPermission(permission);
    setDrawerMode("edit");
    setDrawerOpen(true);
  };

  if (error) {
    return (
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-destructive">Error loading permissions</p>
              <p className="text-sm text-muted-foreground">{error.message}</p>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    );
  }

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
                  <BreadcrumbPage>Permissions</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="mx-auto w-full max-w-7xl">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Permissions Management</h1>
                <p className="text-muted-foreground">
                  Define granular permissions for your platforms and system
                </p>
              </div>
              <Button onClick={handleCreatePermission}>
                <Plus className="mr-2 h-4 w-4" />
                Create Permission
              </Button>
            </div>

            <div className="space-y-4">
              {/* Search and filters */}
              <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                  <Input
                    placeholder="Search permissions..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Select value={selectedPlatform} onValueChange={setSelectedPlatform}>
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Filter by scope" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">
                      <div className="flex items-center gap-2">
                        <Globe className="h-4 w-4" />
                        All Permissions
                      </div>
                    </SelectItem>
                    <SelectItem value="system">
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4" />
                        System Only
                      </div>
                    </SelectItem>
                    {platforms.map((platform) => (
                      <SelectItem key={platform._id} value={platform._id}>
                        <div className="flex items-center gap-2">
                          <Building2 className="h-4 w-4" />
                          {platform.name}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Table */}
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Permission</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Resource</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Scope</TableHead>
                      <TableHead className="w-[50px]"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {isLoading ? (
                      // Loading skeleton
                      Array.from({ length: 5 }).map((_, i) => (
                        <TableRow key={i}>
                          <TableCell>
                            <div className="space-y-1">
                              <Skeleton className="h-4 w-32" />
                              <Skeleton className="h-3 w-24" />
                            </div>
                          </TableCell>
                          <TableCell>
                            <Skeleton className="h-4 w-48" />
                          </TableCell>
                          <TableCell>
                            <Skeleton className="h-5 w-16" />
                          </TableCell>
                          <TableCell>
                            <Skeleton className="h-5 w-20" />
                          </TableCell>
                          <TableCell>
                            <Skeleton className="h-5 w-20" />
                          </TableCell>
                          <TableCell>
                            <Skeleton className="h-8 w-8" />
                          </TableCell>
                        </TableRow>
                      ))
                    ) : filteredPermissions.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="h-24 text-center">
                          {searchQuery ? "No permissions found matching your search." : "No permissions found."}
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredPermissions.map((permission) => (
                        <TableRow key={permission.id}>
                          <TableCell>
                            <div className="flex flex-col">
                              <span className="font-medium">{permission.display_name}</span>
                              <code className="text-xs text-muted-foreground">{permission.name}</code>
                            </div>
                          </TableCell>
                          <TableCell>
                            <p className="text-sm text-muted-foreground max-w-[300px] truncate">
                              {permission.description || "No description"}
                            </p>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{permission.resource}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary">{permission.action}</Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {permission.scope === "system" ? (
                                <>
                                  <Shield className="h-4 w-4 text-destructive" />
                                  <Badge variant="destructive">System</Badge>
                                </>
                              ) : (
                                <>
                                  <Globe className="h-4 w-4 text-primary" />
                                  <Badge variant="secondary">
                                    {platforms.find(p => p._id === permission.scope_id)?.name || "Platform"}
                                  </Badge>
                                </>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="h-8 w-8 p-0">
                                  <span className="sr-only">Open menu</span>
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                                <DropdownMenuItem onClick={() => handleEditPermission(permission)}>
                                  <Pencil className="mr-2 h-4 w-4" />
                                  Edit permission
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem className="text-destructive">
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  Delete permission
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>

              {/* Results count */}
              <div className="text-sm text-muted-foreground">
                Showing {filteredPermissions.length} of {allPermissions.length} permissions
              </div>
            </div>
          </div>
        </div>
      </SidebarInset>
      
      <PermissionDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        mode={drawerMode}
        permissionData={selectedPermission}
      />
    </SidebarProvider>
  );
}