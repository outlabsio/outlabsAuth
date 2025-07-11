/**
 * Example usage of the DataTable component
 * This file demonstrates how to use the DataTable with various features
 */

import { ColumnDef } from "@tanstack/react-table"
import {
  DataTable,
  DataTableColumnHeader,
  DataTableRowActions,
  createSelectColumn,
} from "@/components/ui/data-table"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { toast } from "sonner"

// Example data type
interface User {
  id: string
  email: string
  name: string
  role: string
  status: "active" | "inactive" | "pending"
  createdAt: string
}

// Example column definitions
export const userColumns: ColumnDef<User>[] = [
  // Selection column
  createSelectColumn<User>(),
  
  // Custom cell with avatar
  {
    accessorKey: "name",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Name" />
    ),
    cell: ({ row }) => {
      const user = row.original
      return (
        <div className="flex items-center gap-3">
          <Avatar className="h-8 w-8">
            <AvatarFallback>
              {user.name.split(' ').map(n => n[0]).join('')}
            </AvatarFallback>
          </Avatar>
          <div>
            <div className="font-medium">{user.name}</div>
            <div className="text-sm text-muted-foreground">{user.email}</div>
          </div>
        </div>
      )
    },
  },
  
  // Simple text column with sorting
  {
    accessorKey: "role",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Role" />
    ),
  },
  
  // Status column with badge
  {
    accessorKey: "status",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Status" />
    ),
    cell: ({ row }) => {
      const status = row.getValue("status") as string
      return (
        <Badge 
          variant={
            status === "active" ? "default" : 
            status === "pending" ? "secondary" : 
            "outline"
          }
        >
          {status}
        </Badge>
      )
    },
    // Filter function for status
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
  },
  
  // Date column
  {
    accessorKey: "createdAt",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Created" />
    ),
    cell: ({ row }) => {
      return new Date(row.getValue("createdAt")).toLocaleDateString()
    },
  },
  
  // Actions column
  {
    id: "actions",
    cell: ({ row }) => (
      <DataTableRowActions
        row={row}
        actions={[
          {
            label: "Edit",
            onClick: (user) => {
              toast.success(`Edit ${user.name}`)
            },
          },
          {
            label: "View Details",
            onClick: (user) => {
              toast.info(`View ${user.name}`)
            },
          },
          {
            label: "Delete",
            onClick: (user) => {
              toast.error(`Delete ${user.name}`)
            },
            destructive: true,
            separator: true,
          },
        ]}
      />
    ),
  },
]

// Example usage in a component
export function UserTableExample() {
  // Mock data
  const users: User[] = [
    {
      id: "1",
      name: "John Doe",
      email: "john@example.com",
      role: "Admin",
      status: "active",
      createdAt: "2024-01-01",
    },
    {
      id: "2",
      name: "Jane Smith",
      email: "jane@example.com",
      role: "User",
      status: "pending",
      createdAt: "2024-01-02",
    },
  ]

  return (
    <DataTable
      columns={userColumns}
      data={users}
      // Search configuration
      searchKey="name"
      searchPlaceholder="Search users..."
      // Pagination
      pageSize={10}
      pageSizeOptions={[10, 20, 50]}
      // Features
      showColumnVisibility={true}
      showPagination={true}
      showToolbar={true}
      // Custom empty state
      emptyState={
        <div className="text-center py-10">
          <p className="text-muted-foreground">No users found</p>
        </div>
      }
      // Additional filters (rendered in toolbar)
      filters={
        <div className="flex gap-2">
          {/* Add custom filters here */}
        </div>
      }
      // Actions (rendered in toolbar)
      actions={
        <div className="flex gap-2">
          {/* Add custom actions here */}
        </div>
      }
    />
  )
}