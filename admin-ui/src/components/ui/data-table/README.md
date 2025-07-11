# DataTable Component

A reusable, type-safe data table component built with TanStack Table v8 and ShadCN UI components.

## Features

- **Sorting**: Click column headers to sort
- **Filtering**: Global search and column-specific filters
- **Pagination**: Configurable page sizes and navigation
- **Column Visibility**: Show/hide columns dynamically
- **Row Selection**: Multi-select with checkbox column
- **Type Safety**: Full TypeScript support with generics
- **Responsive**: Works on mobile and desktop
- **Theme Support**: Automatic light/dark theme support
- **Loading State**: Built-in loading indicator
- **Empty State**: Customizable empty state

## Installation

The component requires TanStack Table v8:

```bash
bun add @tanstack/react-table
```

## Basic Usage

```tsx
import { DataTable, ColumnDef } from "@/components/ui/data-table"

interface User {
  id: string
  name: string
  email: string
  role: string
}

const columns: ColumnDef<User>[] = [
  {
    accessorKey: "name",
    header: "Name",
  },
  {
    accessorKey: "email",
    header: "Email",
  },
  {
    accessorKey: "role",
    header: "Role",
  },
]

function UsersTable({ users }: { users: User[] }) {
  return (
    <DataTable 
      columns={columns} 
      data={users}
      searchKey="name"
      searchPlaceholder="Search users..."
    />
  )
}
```

## Advanced Usage

### With Sortable Headers

```tsx
import { DataTableColumnHeader } from "@/components/ui/data-table"

const columns: ColumnDef<User>[] = [
  {
    accessorKey: "name",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Name" />
    ),
  },
]
```

### With Row Actions

```tsx
import { DataTableRowActions } from "@/components/ui/data-table"

const columns: ColumnDef<User>[] = [
  // ... other columns
  {
    id: "actions",
    cell: ({ row }) => (
      <DataTableRowActions
        row={row}
        actions={[
          {
            label: "Edit",
            onClick: (user) => console.log("Edit", user),
          },
          {
            label: "Delete",
            onClick: (user) => console.log("Delete", user),
            destructive: true,
            separator: true,
          },
        ]}
      />
    ),
  },
]
```

### With Row Selection

```tsx
import { createSelectColumn } from "@/components/ui/data-table"

const columns: ColumnDef<User>[] = [
  createSelectColumn<User>(),
  // ... other columns
]
```

### With Custom Filters

```tsx
import { DataTableFacetedFilter } from "@/components/ui/data-table"

function UsersTable() {
  return (
    <DataTable
      columns={columns}
      data={users}
      filters={
        <DataTableFacetedFilter
          column={table.getColumn("status")}
          title="Status"
          options={[
            { label: "Active", value: "active" },
            { label: "Inactive", value: "inactive" },
          ]}
        />
      }
    />
  )
}
```

## Props

### DataTable Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `columns` | `ColumnDef<TData, TValue>[]` | Required | Column definitions |
| `data` | `TData[]` | Required | Table data |
| `searchKey` | `string` | - | Key for global search |
| `searchPlaceholder` | `string` | "Search..." | Placeholder for search input |
| `filters` | `ReactNode` | - | Custom filter components |
| `actions` | `ReactNode` | - | Custom action buttons |
| `pageSize` | `number` | 10 | Initial page size |
| `pageSizeOptions` | `number[]` | [10, 20, 30, 40, 50] | Page size options |
| `className` | `string` | - | Class for table element |
| `containerClassName` | `string` | - | Class for container |
| `showColumnVisibility` | `boolean` | true | Show column visibility toggle |
| `showPagination` | `boolean` | true | Show pagination |
| `showToolbar` | `boolean` | true | Show toolbar |
| `isLoading` | `boolean` | false | Loading state |
| `emptyState` | `ReactNode` | - | Custom empty state |

## Examples

See `example-usage.tsx` for complete examples of various use cases.