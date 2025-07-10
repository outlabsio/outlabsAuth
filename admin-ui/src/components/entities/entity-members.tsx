import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { 
  UserPlus, 
  Search, 
  MoreHorizontal,
  Shield,
  Clock,
  CalendarOff,
  UserCheck,
  UserX,
  AlertCircle,
  Users
} from "lucide-react";
import { format } from "date-fns";

interface EntityMember {
  id: string;
  user_id: string;
  user_email: string;
  user_name: string;
  entity_id: string;
  entity_name: string;
  roles: Array<{
    id: string;
    name: string;
    permissions: string[];
  }>;
  status: "active" | "suspended" | "revoked";
  valid_from?: string;
  valid_until?: string;
  created_at: string;
  updated_at?: string;
}

interface Role {
  id: string;
  name: string;
  description?: string;
  permissions: string[];
}

interface User {
  id: string;
  email: string;
  profile: {
    first_name: string;
    last_name: string;
  };
}

interface EntityMembersProps {
  entityId: string;
  entityName: string;
  canManageMembers: boolean;
}

async function fetchEntityMembers(entityId: string, includeInactive: boolean = false) {
  const params = new URLSearchParams();
  if (includeInactive) params.append("include_inactive", "true");
  
  const response = await authenticatedFetch(`/v1/entities/${entityId}/members?${params}`);
  return response.json();
}

async function fetchAvailableRoles(entityId: string) {
  const response = await authenticatedFetch(`/v1/entities/${entityId}/roles`);
  const data = await response.json();
  return data.items || [];
}

async function searchUsers(query: string, entityId?: string) {
  const params = new URLSearchParams();
  if (query) params.append("search", query);
  if (entityId) params.append("entity_id", entityId);
  
  const response = await authenticatedFetch(`/v1/users/?${params}`);
  const data = await response.json();
  return data.items || [];
}

async function addEntityMember(entityId: string, userId: string, roleId: string) {
  const response = await authenticatedFetch(`/v1/entities/${entityId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      role_id: roleId,
    }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to add member");
  }
  return response.json();
}

async function updateEntityMember(entityId: string, userId: string, updates: any) {
  const response = await authenticatedFetch(`/v1/entities/${entityId}/members/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to update member");
  }
  return response.json();
}

async function removeEntityMember(entityId: string, userId: string) {
  const response = await authenticatedFetch(`/v1/entities/${entityId}/members/${userId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to remove member");
  }
  return response.json();
}

function MemberStatusBadge({ status }: { status: string }) {
  const variants: Record<string, { icon: any; variant: any; label: string }> = {
    active: { icon: UserCheck, variant: "default", label: "Active" },
    suspended: { icon: UserX, variant: "secondary", label: "Suspended" },
    revoked: { icon: AlertCircle, variant: "destructive", label: "Revoked" },
  };
  
  const config = variants[status] || variants.active;
  const Icon = config.icon;
  
  return (
    <Badge variant={config.variant} className="gap-1">
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}

function AddMemberDialog({ 
  entityId, 
  entityName,
  onSuccess 
}: { 
  entityId: string; 
  entityName: string;
  onSuccess: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedRole, setSelectedRole] = useState<string>("");
  const queryClient = useQueryClient();
  
  // Fetch users - get users scoped to this entity
  const { data: users, isLoading: isSearching } = useQuery({
    queryKey: ["users-available", entityId],
    queryFn: () => searchUsers("", entityId), // Get users scoped to this entity
    enabled: open,
  });
  
  // Fetch available roles for this entity
  const { data: roles } = useQuery({
    queryKey: ["entity-roles", entityId],
    queryFn: () => fetchAvailableRoles(entityId),
    enabled: open,
  });
  
  // Add member mutation
  const addMemberMutation = useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string }) =>
      addEntityMember(entityId, userId, roleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity-members", entityId] });
      toast.success("Member added successfully");
      setOpen(false);
      setSearchQuery("");
      setSelectedUser(null);
      setSelectedRole("");
      onSuccess();
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  const handleAdd = () => {
    if (!selectedUser || !selectedRole) return;
    addMemberMutation.mutate({ userId: selectedUser.id, roleId: selectedRole });
  };
  
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <UserPlus className="mr-2 h-4 w-4" />
          Add User
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add User to {entityName}</DialogTitle>
          <DialogDescription>
            Search for a user and assign them a role within this entity.
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          {/* User Search */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Select User</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Filter users by name or email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            
            {/* User Results */}
            <div className="mt-2 max-h-48 overflow-y-auto rounded-md border">
              {isSearching ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  Loading users...
                </div>
              ) : users && users.length > 0 ? (
                <div className="p-1">
                  {(() => {
                    const filteredUsers = users.filter((user: User) => {
                      if (!searchQuery) return true;
                      const query = searchQuery.toLowerCase();
                      return (
                        user.email.toLowerCase().includes(query) ||
                        user.profile.first_name.toLowerCase().includes(query) ||
                        user.profile.last_name.toLowerCase().includes(query)
                      );
                    });
                    
                    if (filteredUsers.length === 0) {
                      return (
                        <div className="p-4 text-center text-sm text-muted-foreground">
                          No users match your filter
                        </div>
                      );
                    }
                    
                    return filteredUsers.map((user: User) => (
                      <button
                        key={user.id}
                        className={`flex w-full items-center gap-3 rounded-md p-2 text-left hover:bg-accent ${
                          selectedUser?.id === user.id ? "bg-accent" : ""
                        }`}
                        onClick={() => setSelectedUser(user)}
                      >
                        <Avatar className="h-8 w-8">
                          <AvatarFallback>
                            {user.profile.first_name?.[0]}{user.profile.last_name?.[0]}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">
                            {user.profile.first_name} {user.profile.last_name}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">
                            {user.email}
                          </p>
                        </div>
                      </button>
                    ));
                  })()}
                  </div>
                ) : (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                    No users found
                  </div>
                )}
              </div>
          </div>
          
          {/* Selected User Display */}
          {selectedUser && (
            <div className="rounded-lg bg-muted p-3">
              <p className="text-sm font-medium">Selected User</p>
              <p className="text-sm text-muted-foreground">
                {selectedUser.profile.first_name} {selectedUser.profile.last_name} ({selectedUser.email})
              </p>
            </div>
          )}
          
          {/* Role Selection */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Assign Role</label>
            <Select value={selectedRole} onValueChange={setSelectedRole}>
              <SelectTrigger>
                <SelectValue placeholder="Select a role" />
              </SelectTrigger>
              <SelectContent>
                {roles && roles.length > 0 ? (
                  roles.map((role: Role) => (
                    <SelectItem key={role.id} value={role.id}>
                      <div>
                        <p className="font-medium">{role.name}</p>
                        {role.description && (
                          <p className="text-xs text-muted-foreground">{role.description}</p>
                        )}
                      </div>
                    </SelectItem>
                  ))
                ) : (
                  <div className="p-2 text-sm text-muted-foreground text-center">
                    No roles available. Please create roles first.
                  </div>
                )}
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button 
            onClick={handleAdd} 
            disabled={!selectedUser || !selectedRole || addMemberMutation.isPending}
          >
            {addMemberMutation.isPending ? "Adding..." : "Add User"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function EntityMembers({ entityId, entityName, canManageMembers }: EntityMembersProps) {
  const [includeInactive, setIncludeInactive] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [memberToRemove, setMemberToRemove] = useState<EntityMember | null>(null);
  const queryClient = useQueryClient();
  
  // Fetch members
  const { data: membersData, isLoading, error } = useQuery({
    queryKey: ["entity-members", entityId, includeInactive],
    queryFn: () => fetchEntityMembers(entityId, includeInactive),
  });
  
  // Update member mutation
  const updateMemberMutation = useMutation({
    mutationFn: ({ userId, updates }: { userId: string; updates: any }) =>
      updateEntityMember(entityId, userId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity-members", entityId] });
      toast.success("Member updated successfully");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  // Remove member mutation
  const removeMemberMutation = useMutation({
    mutationFn: (userId: string) => removeEntityMember(entityId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity-members", entityId] });
      toast.success("Member removed successfully");
      setMemberToRemove(null);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  // Filter members
  const members = membersData?.items || [];
  const filteredMembers = members.filter((member: EntityMember) =>
    member.user_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    member.user_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    member.roles.some(role => role.name.toLowerCase().includes(searchQuery.toLowerCase()))
  );
  
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center space-x-4">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Users</CardTitle>
            <CardDescription>
              Manage users who have access to {entityName}
            </CardDescription>
          </div>
          {canManageMembers && (
            <AddMemberDialog 
              entityId={entityId} 
              entityName={entityName}
              onSuccess={() => {}}
            />
          )}
        </div>
      </CardHeader>
      <CardContent>
        {/* Filters */}
        <div className="mb-6 flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search users..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="include-inactive"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
              className="rounded border-gray-300"
            />
            <label htmlFor="include-inactive" className="text-sm">
              Show inactive users
            </label>
          </div>
        </div>
        
        {/* Members Table */}
        {filteredMembers.length === 0 ? (
          <div className="text-center py-8">
            <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Users Found</h3>
            <p className="text-muted-foreground">
              {searchQuery 
                ? "No users match your search criteria"
                : "This entity doesn't have any users yet"}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Valid Period</TableHead>
                <TableHead>Added</TableHead>
                {canManageMembers && <TableHead className="w-[50px]"></TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredMembers.map((member: EntityMember) => (
                <TableRow key={member.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar>
                        <AvatarFallback>
                          {member.user_name.split(' ').map(n => n[0]).join('')}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <div className="font-medium">{member.user_name}</div>
                        <div className="text-sm text-muted-foreground">{member.user_email}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    {member.roles.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {member.roles.map((role) => (
                          <Badge key={role.id} variant="outline">
                            {role.name}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <span className="text-sm text-muted-foreground">No roles assigned</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <MemberStatusBadge status={member.status} />
                  </TableCell>
                  <TableCell>
                    {member.valid_from || member.valid_until ? (
                      <div className="text-sm">
                        {member.valid_from && (
                          <div className="flex items-center gap-1 text-muted-foreground">
                            <Clock className="h-3 w-3" />
                            From: {format(new Date(member.valid_from), 'PP')}
                          </div>
                        )}
                        {member.valid_until && (
                          <div className="flex items-center gap-1 text-destructive">
                            <CalendarOff className="h-3 w-3" />
                            Until: {format(new Date(member.valid_until), 'PP')}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-sm text-muted-foreground">No restrictions</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-muted-foreground">
                      {format(new Date(member.created_at), 'PP')}
                    </span>
                  </TableCell>
                  {canManageMembers && (
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
                          <DropdownMenuItem 
                            onClick={() => {
                              // TODO: Open edit dialog
                              toast.info("Edit member coming soon");
                            }}
                          >
                            Change Role
                          </DropdownMenuItem>
                          {member.status === "active" ? (
                            <DropdownMenuItem
                              onClick={() => {
                                updateMemberMutation.mutate({
                                  userId: member.user_id,
                                  updates: { status: "suspended" },
                                });
                              }}
                            >
                              Suspend Access
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem
                              onClick={() => {
                                updateMemberMutation.mutate({
                                  userId: member.user_id,
                                  updates: { status: "active" },
                                });
                              }}
                            >
                              Reactivate Access
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => setMemberToRemove(member)}
                          >
                            Remove Member
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      
      {/* Remove Confirmation Dialog */}
      <AlertDialog open={!!memberToRemove} onOpenChange={() => setMemberToRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Member</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove {memberToRemove?.user_name} from {entityName}? 
              They will lose all access granted through this entity.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (memberToRemove) {
                  removeMemberMutation.mutate(memberToRemove.user_id);
                }
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Remove Member
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}