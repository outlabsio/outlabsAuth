import { createFileRoute, redirect } from "@tanstack/react-router";

// Helper function to query the system status
const getSystemStatus = async (): Promise<{ initialized: boolean }> => {
  const response = await fetch("/v1/system/status");
  if (!response.ok) {
    throw new Error("Failed to fetch system status");
  }
  return response.json();
};

export const Route = createFileRoute("/")({
  beforeLoad: async () => {
    try {
      // First check if user is authenticated
      const token = localStorage.getItem("access_token");
      if (token) {
        throw redirect({
          to: "/dashboard",
        });
      }

      // If not authenticated, check system status
      const status = await getSystemStatus();
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
        // Handle API offline case
        console.error("API is not reachable. Can't determine platform status.");
        // Redirect to login as a fallback
        throw redirect({
          to: "/login",
        });
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
      <p>Determining system status. You should be redirected shortly.</p>
    </div>
  );
}