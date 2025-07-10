import { Outlet, createRootRoute } from "@tanstack/react-router";
import { AuthDebug } from "@/components/auth-debug";
import { useEffect, useState } from "react";

function RootComponent() {
  const [showDebug, setShowDebug] = useState(false);

  useEffect(() => {
    // Check if debug mode is enabled
    const checkDebugMode = () => {
      const debugMode = localStorage.getItem("auth-debug-mode") === "true";
      setShowDebug(debugMode);
    };

    checkDebugMode();

    // Listen for storage changes to update debug mode
    window.addEventListener("storage", checkDebugMode);

    // Also check periodically in case localStorage changes on same page
    const interval = setInterval(checkDebugMode, 1000);

    return () => {
      window.removeEventListener("storage", checkDebugMode);
      clearInterval(interval);
    };
  }, []);

  return (
    <>
      <Outlet />
      {showDebug && (
        <div className='fixed bottom-4 right-4 z-50 max-w-md max-h-[80vh] overflow-hidden'>
          <AuthDebug />
        </div>
      )}
    </>
  );
}

export const Route = createRootRoute({
  component: RootComponent,
});
