import { create } from "zustand";
import { toast } from "sonner";

interface Notification {
  id: string;
  type: "success" | "error" | "info" | "warning";
  title: string;
  description?: string;
  duration?: number;
}

interface NotificationState {
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, "id">) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  
  addNotification: (notification) => {
    const id = Math.random().toString(36).substr(2, 9);
    const newNotification = { ...notification, id };
    
    set((state) => ({
      notifications: [...state.notifications, newNotification],
    }));
    
    // Show toast
    const toastOptions = {
      description: notification.description,
      duration: notification.duration,
    };
    
    switch (notification.type) {
      case "success":
        toast.success(notification.title, toastOptions);
        break;
      case "error":
        toast.error(notification.title, toastOptions);
        break;
      case "warning":
        toast.warning(notification.title, toastOptions);
        break;
      default:
        toast(notification.title, toastOptions);
    }
    
    // Auto-remove after duration
    if (notification.duration) {
      setTimeout(() => {
        get().removeNotification(id);
      }, notification.duration);
    }
  },
  
  removeNotification: (id) => {
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    }));
  },
  
  clearNotifications: () => {
    set({ notifications: [] });
  },
  
  success: (title, description) => {
    get().addNotification({ type: "success", title, description });
  },
  
  error: (title, description) => {
    get().addNotification({ type: "error", title, description });
  },
  
  info: (title, description) => {
    get().addNotification({ type: "info", title, description });
  },
  
  warning: (title, description) => {
    get().addNotification({ type: "warning", title, description });
  },
}));

// Hook for API error handling
export function useApiErrorHandler() {
  const { error } = useNotificationStore();
  
  return (err: unknown) => {
    if (err instanceof Error) {
      if (err.name === "ValidationError") {
        error("Validation Error", "The server response was invalid");
      } else if (err.name === "ApiError") {
        const apiError = err as any;
        error(
          `Request Failed`,
          apiError.data?.detail || apiError.message || "An unexpected error occurred"
        );
      } else {
        error("Error", err.message);
      }
    } else {
      error("Error", "An unexpected error occurred");
    }
  };
}