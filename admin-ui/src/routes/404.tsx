import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/404")({
  component: () => {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-4xl font-bold mb-4">404 - Not Found</h1>
          <p className="text-muted-foreground">The page you are looking for does not exist.</p>
        </div>
      </div>
    );
  },
});
