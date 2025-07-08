import { useEffect } from 'react';
import { useRouter } from '@tanstack/react-router';
import { useAuthStore } from '@/stores/auth-store';

export function useRequireAuth() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.navigate({ to: '/login' });
    }
  }, [isAuthenticated, router]);

  return isAuthenticated;
}

export function useAuth() {
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const logout = useAuthStore((state) => state.logout);

  return {
    user,
    isAuthenticated,
    logout,
  };
}