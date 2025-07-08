import { RouterProvider } from '@tanstack/react-router';
import { useAuthInitialization } from '@/hooks/use-auth-initialization';

interface AppProps {
  router: any;
}

export function App({ router }: AppProps) {
  // Initialize auth on app startup
  useAuthInitialization();
  
  return <RouterProvider router={router} />;
}