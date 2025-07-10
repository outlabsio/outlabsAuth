import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { 
  Users, 
  Search, 
  Plus, 
  MoreHorizontal, 
  Building2,
  Shield,
  UserCheck,
  UserX,
  Mail
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { requireAuth } from "@/lib/route-guards";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { UserDrawer } from "@/components/users/user-drawer";

export const Route = createFileRoute("/users/")({
  beforeLoad: requireAuth,
  component: UsersPage,
});

interface User {
  id: string;
  email: string;
  profile: {
    first_name: string;
    last_name: string;
    phone?: string;
    avatar_url?: string;
    preferences?: Record<string, any>;
  };
  is_active: boolean;
  is_system_user: boolean;
  is_platform_admin?: boolean;
  email_verified: boolean;
  last_login?: string;
  last_password_change?: string;
  created_at: string;
  updated_at: string;
  entities: Array<{
    id: string;
    name: string;
    slug: string;
    entity_type: string;
    entity_class: string;
    parent_id?: string;
    roles: Array<{
      id: string;
      name: string;
    }>;
    status: string;
    joined_at: string;
  }>;
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

async function fetchUsers(
  page: number = 1,
  search?: string,
  entityId?: string
): Promise<PaginatedResponse<User>> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: "10",
  });
  
  if (search) {
    params.append("search", search);
  }
  
  if (entityId) {
    params.append("entity_id", entityId);
  }
  
  const response = await authenticatedFetch(`/v1/users/?${params}`);
  return response.json();
}

async function fetchEntities() {
  const response = await authenticatedFetch("/v1/entities/?entity_class=STRUCTURAL");
  const data = await response.json();
  return data.items || [];
}

function UserStatusBadge({ user }: { user: User }) {
  if (!user.is_active) {
    return (
      <Badge variant="secondary" className="gap-1">
        <UserX className="h-3 w-3" />
        Inactive
      </Badge>
    );
  }
  
  if (!user.email_verified) {
    return (
      <Badge variant="outline" className="gap-1">
        <Mail className="h-3 w-3" />
        Unverified
      </Badge>
    );
  }
  
  return (
    <Badge variant="default" className="gap-1">
      <UserCheck className="h-3 w-3" />
      Active
    </Badge>
  );
}

function UsersContent({ onEditUser }: { onEditUser: (user: User) => void }) {
  const { selectedOrganization, isSystemContext } = useContextStore();
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEntity, setSelectedEntity] = useState<string>("");
  
  // In organization context, default to showing users from that org
  const contextEntityId = !isSystemContext() && selectedOrganization ? selectedOrganization.id : undefined;
  
  const { data: users, isLoading } = useQuery({
    queryKey: ["users", currentPage, searchQuery, selectedEntity || contextEntityId],
    queryFn: () => fetchUsers(currentPage, searchQuery, selectedEntity || contextEntityId),
  });
  
  // Only fetch entities for filtering if in system context
  const { data: entities } = useQuery({
    queryKey: ["entities-structural", contextEntityId],
    queryFn: fetchEntities,
    enabled: isSystemContext(), // Only need entity filter in system context
  });
  
  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <div className="border rounded-lg">
          <div className="p-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center space-x-4 py-4">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name or email..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1); // Reset to first page on search
            }}
            className="pl-10"
          />
        </div>
        {isSystemContext() && entities && (
          <Select value={selectedEntity || "all"} onValueChange={(value) => {
            setSelectedEntity(value === "all" ? "" : value);
            setCurrentPage(1); // Reset to first page on filter change
          }}>
            <SelectTrigger className="w-full sm:w-[250px]">
              <SelectValue placeholder="Filter by entity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Entities</SelectItem>
              {entities?.map((entity: any) => (
                <SelectItem key={entity.id} value={entity.id}>
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4" />
                    {entity.name}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
      
      {/* Users Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Roles</TableHead>
              <TableHead>Entities</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users?.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8">
                  <div className="flex flex-col items-center gap-2">
                    <Users className="h-8 w-8 text-muted-foreground" />
                    <p className="text-muted-foreground">No users found</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              users?.items.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar>
                        <AvatarFallback>
                          {user.profile.first_name?.[0] || ''}{user.profile.last_name?.[0] || ''}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <div className="font-medium">
                          {user.profile.first_name} {user.profile.last_name}
                          {user.is_system_user && (
                            <Badge variant="outline" className="ml-2 gap-1">
                              <Shield className="h-3 w-3" />
                              System User
                            </Badge>
                          )}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {user.email}
                        </div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <UserStatusBadge user={user} />
                  </TableCell>
                  <TableCell>
                    {user.entities.length === 0 ? (
                      <span className="text-sm text-muted-foreground">No roles</span>
                    ) : (
                      <div className="space-y-1">
                        {/* Show roles grouped by entity */}
                        {user.entities.slice(0, 2).map((entity) => (
                          <div key={entity.id} className="flex items-center gap-1">
                            <Building2 className="h-3 w-3 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">{entity.name}:</span>
                            {entity.roles?.map((role) => (
                              <Badge key={role.id} variant="secondary" className="text-xs">
                                {role.name}
                              </Badge>
                            )) || <span className="text-xs text-muted-foreground">No roles</span>}
                          </div>
                        ))}
                        {user.entities.length > 2 && (
                          <Badge variant="outline" className="text-xs">
                            +{user.entities.length - 2} more
                          </Badge>
                        )}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    {user.entities.length === 0 ? (
                      <span className="text-sm text-muted-foreground">No access</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {user.entities.map((entity) => (
                          <Badge 
                            key={entity.id} 
                            variant={entity.entity_type === "platform" ? "default" : "outline"} 
                            className="text-xs gap-1"
                          >
                            <Building2 className="h-3 w-3" />
                            {entity.name}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-muted-foreground">
                      {new Date(user.created_at).toLocaleDateString()}
                    </span>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => onEditUser(user)}>Edit User</DropdownMenuItem>
                        <DropdownMenuItem>Manage Roles</DropdownMenuItem>
                        <DropdownMenuItem>Manage Entity Access</DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-destructive">
                          Deactivate User
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        
        {/* Pagination */}
        {users && users.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <div className="text-sm text-muted-foreground">
              Showing {((currentPage - 1) * users.page_size) + 1} to{" "}
              {Math.min(currentPage * users.page_size, users.total)} of{" "}
              {users.total} users
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(currentPage - 1)}
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={currentPage === users.pages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function UsersPage() {
  const { selectedOrganization, isSystemContext } = useContextStore();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"create" | "edit">("create");
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  
  const handleCreateUser = () => {
    setDrawerMode("create");
    setSelectedUser(null);
    setDrawerOpen(true);
  };
  
  const handleEditUser = (user: User) => {
    setDrawerMode("edit");
    setSelectedUser(user);
    setDrawerOpen(true);
  };
  
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
                  <BreadcrumbPage>Users</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="mx-auto w-full max-w-7xl">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">User Management</h1>
                <div className="flex items-center gap-2 mt-1">
                  {!isSystemContext() && selectedOrganization ? (
                    <>
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                      <p className="text-sm text-muted-foreground">
                        Showing users with access to <span className="font-medium">{selectedOrganization.name}</span>
                      </p>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Manage all users, their roles, and entity access
                    </p>
                  )}
                </div>
              </div>
              <Button onClick={handleCreateUser}>
                <Plus className="mr-2 h-4 w-4" />
                Create User
              </Button>
            </div>
            
            <UsersContent onEditUser={handleEditUser} />
          </div>
        </div>
      </SidebarInset>
      
      <UserDrawer 
        open={drawerOpen} 
        onOpenChange={setDrawerOpen}
        mode={drawerMode}
        user={selectedUser}
        defaultEntityId={!isSystemContext() && selectedOrganization ? selectedOrganization.id : undefined}
      />
    </SidebarProvider>
  );
}