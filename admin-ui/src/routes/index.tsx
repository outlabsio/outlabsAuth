import { createFileRoute, redirect } from "@tanstack/react-router";

// Helper function to query the platform status
const getPlatformStatus = async (): Promise<{ initialized: boolean }> => {
  const response = await fetch("/v1/platform/status");
  if (!response.ok) {
    throw new Error("Failed to fetch platform status");
  }
  return response.json();
};

export const Route = createFileRoute("/")({
  beforeLoad: async () => {
    try {
      const status = await getPlatformStatus();
      if (status.initialized) {
        throw redirect({
          to: "/login",
        });
      } else {
        throw redirect({
          to: "/setup",
        });
      }
    } catch (error) {
      if (error instanceof Error && error.message.includes("Failed to fetch")) {
        // Handle API offline case, maybe redirect to an error page
        console.error("API is not reachable. Can't determine platform status.");
        // For now, we'll let it render the component which will show an error.
      }
      // Re-throw redirects
      throw error;
    }
  },
  component: Index,
});

function Index() {
  return (
    <div className='p-2'>
      <h3>Loading...</h3>
      <p>Determining platform status. You should be redirected shortly.</p>
    </div>
  );
}
