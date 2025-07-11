import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface LoadingGridProps {
  count?: number;
  columns?: {
    default?: number;
    md?: number;
    lg?: number;
  };
}

export function LoadingGrid({ 
  count = 3,
  columns = { default: 1, md: 2, lg: 3 }
}: LoadingGridProps) {
  const gridCols = `grid-cols-${columns.default} md:grid-cols-${columns.md} lg:grid-cols-${columns.lg}`;
  
  return (
    <div className={`grid gap-4 ${gridCols}`}>
      {Array.from({ length: count }).map((_, i) => (
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

export function LoadingTableRows({ count = 5, columns = 4 }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <tr key={i}>
          {Array.from({ length: columns }).map((_, j) => (
            <td key={j} className="p-4">
              <Skeleton className="h-4 w-full" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}