"use client";

import { BadgeCheck, Bell, ChevronsUpDown, CreditCard, LogOut, Sparkles, Bug } from "lucide-react";
import { useRouter } from "@tanstack/react-router";
import { useAuthStore } from "@/stores/auth-store";
import { useState, useEffect } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from "@/components/ui/sidebar";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

// Debug mode utilities
const getDebugMode = () => {
  try {
    const stored = localStorage.getItem("auth-debug-mode");
    return stored === "true";
  } catch {
    return false;
  }
};

const setDebugMode = (enabled: boolean) => {
  try {
    localStorage.setItem("auth-debug-mode", enabled.toString());
  } catch (e) {
    console.error("Failed to set debug mode:", e);
  }
};

export function NavUser({
  user,
}: {
  user: {
    name: string;
    email: string;
    avatar?: string;
  };
}) {
  const { isMobile } = useSidebar();
  const router = useRouter();
  const [debugModeEnabled, setDebugModeEnabled] = useState(getDebugMode());

  const logout = useAuthStore((state) => state.logout);

  const handleLogout = () => {
    logout();
  };

  const handleDebugToggle = (enabled: boolean) => {
    setDebugModeEnabled(enabled);
    setDebugMode(enabled);
  };

  // Update debug mode on mount and when it changes
  useEffect(() => {
    setDebugMode(debugModeEnabled);
  }, [debugModeEnabled]);

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size='lg' className='data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground'>
              <Avatar className='h-8 w-8 rounded-lg'>
                <AvatarImage src={user.avatar} alt={user.name} />
                <AvatarFallback className='rounded-lg'>{user.name.substring(0, 2).toUpperCase()}</AvatarFallback>
              </Avatar>
              <div className='grid flex-1 text-left text-sm leading-tight'>
                <span className='truncate font-semibold'>{user.name}</span>
                <span className='truncate text-xs'>{user.email}</span>
              </div>
              <ChevronsUpDown className='ml-auto size-4' />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent className='w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg' side={isMobile ? "bottom" : "right"} align='end' sideOffset={4}>
            <DropdownMenuLabel className='p-0 font-normal'>
              <div className='flex items-center gap-2 px-1 py-1.5 text-left text-sm'>
                <Avatar className='h-8 w-8 rounded-lg'>
                  <AvatarImage src={user.avatar} alt={user.name} />
                  <AvatarFallback className='rounded-lg'>{user.name.substring(0, 2).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className='grid flex-1 text-left text-sm leading-tight'>
                  <span className='truncate font-semibold'>{user.name}</span>
                  <span className='truncate text-xs'>{user.email}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem>
                <BadgeCheck className='mr-2 h-4 w-4' />
                Account
              </DropdownMenuItem>
              <DropdownMenuItem>
                <CreditCard className='mr-2 h-4 w-4' />
                Billing
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Bell className='mr-2 h-4 w-4' />
                Notifications
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />

            {/* Debug Mode Toggle */}
            <div className='px-2 py-2'>
              <div className='flex items-center justify-between'>
                <div className='flex items-center space-x-2'>
                  <Bug className='h-4 w-4 text-muted-foreground' />
                  <Label htmlFor='debug-mode-toggle' className='text-sm font-medium'>
                    Debug Mode
                  </Label>
                </div>
                <Switch id='debug-mode-toggle' checked={debugModeEnabled} onCheckedChange={handleDebugToggle} />
              </div>
              {debugModeEnabled && <p className='text-xs text-muted-foreground mt-1'>Prevents logout, captures auth logs</p>}
            </div>

            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut className='mr-2 h-4 w-4' />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
