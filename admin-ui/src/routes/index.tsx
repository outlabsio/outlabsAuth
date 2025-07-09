import { createFileRoute, redirect } from "@tanstack/react-router";
import { apiUrl } from "@/config";

// Helper function to query the system status
const getSystemStatus = async (): Promise<{ initialized: boolean }> => {
  console.log("Checking system status...");
  const response = await fetch(apiUrl("/system/status"));
  console.log("System status response:", response.status, response.ok);
  if (!response.ok) {
    throw new Error("Failed to fetch system status");
  }
  const data = await response.json();
  console.log("System status data:", data);
  return data;
};

export const Route = createFileRoute("/")({
  beforeLoad: async () => {
    try {
      // First check if user is authenticated
      const authStorage = localStorage.getItem("auth-storage");
      if (authStorage) {
        try {
          const authData = JSON.parse(authStorage);
          if (authData.state?.isAuthenticated && authData.state?.tokens?.access_token) {
            throw redirect({
              to: "/dashboard",
            });
          }
        } catch (e) {
          // Invalid auth storage, continue to check system status
        }
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